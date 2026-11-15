"""Optional nlm audio creation, bounded polling and local artifact download."""

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from .base import AudioProvider, AudioResult, AudioUnavailableError


def unavailable(reason: str) -> AudioUnavailableError:
    return AudioUnavailableError(
        f"NotebookLM audio: {reason}. Retry or use --provider script_only."
    )


AudioFormat = Literal["m4a", "mp3"]
AUDIO_FORMATS: tuple[AudioFormat, ...] = ("m4a", "mp3")
PENDING_STATUSES = ("in_progress", "queued")


def valid_artifact_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("-")


class NotebookLMAdapter(AudioProvider):
    """Google NotebookLM Studio Audio Overview: the editorial standard for podcasts."""

    def __init__(
        self,
        project_root: Path,
        corpus_id: str | None = None,
        corpus_id_env: str = "EDITORIAL_AUDIO_ID",
        timeout: float = 60.0,
        language: str = "it",
        audio_format: AudioFormat = "m4a",
        poll_attempts: int = 120,
        poll_interval: float = 5.0,
    ) -> None:
        super().__init__(project_root)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("NotebookLM timeout must be finite and positive")
        if not language.isalpha() or not 2 <= len(language) <= 8:
            raise ValueError("NotebookLM language must be a short alphabetic code")
        if audio_format not in AUDIO_FORMATS:
            raise ValueError("NotebookLM audio format must be 'm4a' or 'mp3'")
        if (
            isinstance(poll_attempts, bool)
            or not isinstance(poll_attempts, int)
            or poll_attempts <= 0
        ):
            raise ValueError("NotebookLM poll_attempts must be a positive integer")
        if not math.isfinite(poll_interval) or poll_interval <= 0:
            raise ValueError("NotebookLM poll_interval must be finite and positive")
        self._corpus_id = corpus_id
        self._corpus_id_env = corpus_id_env
        self._timeout = timeout
        self.language = language
        self.audio_format: AudioFormat = audio_format
        self.poll_attempts = poll_attempts
        self.poll_interval = float(poll_interval)

    @property
    def filename(self) -> str:
        return f"podcast.{self.audio_format}"

    def preflight(self) -> str:
        """Return the configured notebook, or raise before any network call."""
        corpus = self._corpus_id or os.environ.get(self._corpus_id_env)
        if not corpus or not corpus.strip() or corpus.startswith("-"):
            raise unavailable("notebook corpus is not configured")
        if shutil.which("nlm") is None:
            raise unavailable("CLI 'nlm' is unavailable")
        return corpus

    def _run(self, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["nlm", *args],
                cwd=self.root,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise unavailable("CLI request timed out") from None
        except (OSError, UnicodeError):
            raise unavailable("CLI could not be executed or decoded") from None
        if result.returncode != 0:
            # Raw stdout/stderr can contain credentials, host paths and cloud IDs.
            if any(word in result.stderr.casefold() for word in ("auth", "login", "cookie")):
                raise unavailable("authentication required; run 'nlm login'")
            raise unavailable("CLI request failed")
        return result.stdout

    def _json(self, args: list[str]) -> dict[str, Any]:
        output = self._run(args)
        try:
            payload = json.loads(output)
        except ValueError:
            raise unavailable("invalid JSON response") from None
        if not isinstance(payload, dict):
            raise unavailable("invalid JSON response")
        return payload

    def _artifacts(self, payload: dict[str, Any]) -> list[Any]:
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list):
            raise unavailable("invalid studio status response")
        return artifacts

    def _existing_artifact(self, corpus: str) -> tuple[str, str] | None:
        """Return a reusable audio artifact (id, status) already present in Studio."""
        payload = self._json(["studio", "status", corpus, "--json", "--mcp-compatible"])
        pending: tuple[str, str] | None = None
        for item in self._artifacts(payload):
            if not isinstance(item, dict) or not valid_artifact_id(item.get("artifact_id")):
                continue
            if item.get("type", "audio") != "audio":
                continue
            status = item.get("status")
            if status == "completed":
                return item["artifact_id"], status
            if status in PENDING_STATUSES and pending is None:
                pending = (item["artifact_id"], status)
        return pending

    def _create_artifact(self, corpus: str, sources: list[dict[str, Any]]) -> str:
        claims = "\n".join(
            f"{claim['text']} (fonte {source['key']}, {claim['locator']})"
            for source in sources
            for claim in source.get("claims", [])
        )
        created = self._json(
            [
                "audio",
                "create",
                corpus,
                "--language",
                self.language,
                "--confirm",
                "--json",
                "--focus",
                "Genera un podcast solo sulle seguenti affermazioni verificate. "
                "Non aggiungere fatti non supportati:\n" + claims,
            ]
        )
        artifact = created.get("artifact_id")
        if not isinstance(artifact, str) or not valid_artifact_id(artifact):
            raise unavailable("missing audio artifact in response")
        return artifact

    def _wait_completed(self, corpus: str, artifact: str) -> None:
        """Poll a single Studio artifact until completion, within the bounded window."""
        for attempt in range(self.poll_attempts):
            payload = self._json(
                [
                    "studio",
                    "status",
                    corpus,
                    "--json",
                    "--mcp-compatible",
                    "--artifact-id",
                    artifact,
                ]
            )
            selected = [
                item
                for item in self._artifacts(payload)
                if isinstance(item, dict) and item.get("artifact_id") == artifact
            ]
            if len(selected) != 1:
                raise unavailable("audio artifact absent from studio status")
            status = selected[0].get("status")
            if status == "completed":
                return
            if status not in PENDING_STATUSES:
                raise unavailable("audio generation failed")
            if attempt + 1 < self.poll_attempts:
                time.sleep(self.poll_interval)
        raise unavailable("generation still pending after bounded polling")

    def build(
        self,
        post_id: str,
        draft_text: str,
        sources: list[dict[str, Any]],
        output_dir: Path,
        dry_run: bool = False,
    ) -> AudioResult:
        path = self.destination(post_id, output_dir, self.filename)
        result = AudioResult(
            status="DRY_RUN" if dry_run else "BUILT",
            provider="notebooklm",
            audio_files=[self.result_path(path)],
            details={"language": self.language, "format": self.audio_format},
        )
        if dry_run:
            return result
        corpus = self.preflight()
        existing = self._existing_artifact(corpus)
        if existing is None:
            artifact = self._create_artifact(corpus, sources)
            self._wait_completed(corpus, artifact)
        else:
            artifact, status = existing
            if status != "completed":
                self._wait_completed(corpus, artifact)
        # Download to a temporary file so errors never replace an existing artifact.
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".audio-", dir=path.parent) as temporary:
            downloaded = Path(temporary) / self.filename
            self._run(
                [
                    "download",
                    "audio",
                    corpus,
                    "--id",
                    artifact,
                    "--output",
                    self.result_path(downloaded),
                    "--no-progress",
                ]
            )
            if not downloaded.is_file() or downloaded.stat().st_size == 0:
                raise unavailable("download did not produce an audio file")
            downloaded.replace(path)
        return result


# Explicit alias: NotebookLM is the only audio engine fit for publication.
NotebookLMAudioAdapter = NotebookLMAdapter
