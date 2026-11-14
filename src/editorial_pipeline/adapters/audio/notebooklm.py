"""Optional nlm audio creation, bounded polling and local artifact download."""

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from editorial_pipeline.adapters.audio.base import AudioProvider, AudioResult, AudioUnavailableError


def unavailable(reason: str) -> AudioUnavailableError:
    return AudioUnavailableError(
        f"NotebookLM audio: {reason}. Retry or use --provider script_only."
    )


class NotebookLMAdapter(AudioProvider):
    def __init__(
        self,
        project_root: Path,
        corpus_id: str | None = None,
        corpus_id_env: str = "EDITORIAL_AUDIO_ID",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(project_root)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("NotebookLM timeout must be finite and positive")
        self._corpus_id = corpus_id
        self._corpus_id_env = corpus_id_env
        self._timeout = timeout

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

    def build(
        self,
        post_id: str,
        draft_text: str,
        sources: list[dict[str, Any]],
        output_dir: Path,
        dry_run: bool = False,
    ) -> AudioResult:
        path = self.destination(post_id, output_dir, "podcast.m4a")
        result = AudioResult(
            status="DRY_RUN" if dry_run else "BUILT",
            provider="notebooklm",
            audio_files=[self.result_path(path)],
        )
        if dry_run:
            return result
        corpus = self._corpus_id or os.environ.get(self._corpus_id_env)
        if not corpus or not corpus.strip() or corpus.startswith("-"):
            raise unavailable("notebook corpus is not configured")
        if shutil.which("nlm") is None:
            raise unavailable("CLI 'nlm' is unavailable")
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
                "--confirm",
                "--json",
                "--focus",
                "Genera un podcast solo sulle seguenti affermazioni verificate. "
                "Non aggiungere fatti non supportati:\n" + claims,
            ]
        )
        artifact = created.get("artifact_id")
        if not isinstance(artifact, str) or not artifact.strip() or artifact.startswith("-"):
            raise unavailable("missing audio artifact in response")
        for _ in range(30):
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
            artifacts = payload.get("artifacts")
            if not isinstance(artifacts, list):
                raise unavailable("invalid studio status response")
            selected = [
                item
                for item in artifacts
                if isinstance(item, dict) and item.get("artifact_id") == artifact
            ]
            if len(selected) != 1:
                raise unavailable("audio artifact absent from studio status")
            status = selected[0].get("status")
            if status == "completed":
                break
            if status not in ("in_progress", "queued"):
                raise unavailable("audio generation failed")
            time.sleep(2)
        else:
            raise unavailable("generation still pending after bounded polling")
        # Download to a temporary file so errors never replace an existing artifact.
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".audio-", dir=path.parent) as temporary:
            downloaded = Path(temporary) / "podcast.m4a"
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
