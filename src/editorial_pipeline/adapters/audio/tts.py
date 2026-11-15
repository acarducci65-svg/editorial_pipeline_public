"""DEPRECATED local MP3 output via optional edge-tts (Microsoft's online speech service).

Robotic single-voice synthesis is not fit for publication: Google NotebookLM Studio
(provider ``notebooklm``) is the required editorial standard for podcast production.
"""

import os
import re
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

from editorial_pipeline.adapters.audio.base import AudioProvider, AudioResult, AudioUnavailableError

TTS_DEPRECATION = (
    "Local TTS produces sub-standard robotic audio; Google NotebookLM Studio is the "
    "required editorial standard for podcast production. Use --provider notebooklm."
)


def _spoken_text(text: str) -> str:
    """Remove production notes and Markdown while retaining spoken prose."""
    # Avoid initializing the CLI dispatcher while the audio package is loading.
    from editorial_pipeline.cli.reports import _sanitize

    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->|```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(
            ("#", "Fonte:", "Riferimento:", "Copione da revisionare", "Bozza audio:")
        ):
            continue
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^([-+*]|\d+[.)])\s+", "", line)
        lines.append(re.sub(r"[*_`]+", "", line).strip())
    return str(_sanitize("\n".join(line for line in lines if line))).strip()


class LocalTtsAudioProvider(AudioProvider):
    """Deprecated: kept only for offline previews, never for publication."""

    def __init__(
        self, project_root: Path, voice: str = "it-IT-DiegoNeural", rate: str = "+0%"
    ) -> None:
        warnings.warn(TTS_DEPRECATION, DeprecationWarning, stacklevel=2)
        super().__init__(project_root)
        self.voice = voice
        self.rate = rate

    def build(
        self,
        post_id: str,
        draft_text: str,
        sources: list[dict[str, Any]],
        output_dir: Path,
        dry_run: bool = False,
    ) -> AudioResult:
        dest = self.destination(post_id, output_dir, "podcast.mp3")
        if dry_run:
            return AudioResult(
                status="DRY_RUN",
                provider="tts",
                audio_files=[self.result_path(dest)],
                details={"planned_voice": self.voice, "deprecated": True},
            )
        engine = shutil.which("edge-tts")
        if engine is None:
            raise AudioUnavailableError("Local TTS engine ('edge-tts') is unavailable")
        try:
            script = self.destination(post_id, output_dir, "podcast_script.md")
            if script.is_file():
                narration = script.read_text(encoding="utf-8")
            else:
                claims = [
                    str(claim["text"]) for source in sources for claim in source.get("claims", [])
                ]
                narration = "\n".join([draft_text, *claims])
            narration = _spoken_text(narration)
            if not narration:
                raise AudioUnavailableError("Local TTS requires non-empty narration")
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Preserve an existing recording if synthesis fails or produces no audio.
            with tempfile.TemporaryDirectory(prefix=".tts-", dir=dest.parent) as temporary:
                pending = Path(temporary) / "podcast.mp3"
                subprocess.run(
                    [
                        engine,
                        "--file",
                        "-",
                        f"--voice={self.voice}",
                        f"--rate={self.rate}",
                        "--write-media",
                        str(pending),
                    ],
                    input=narration,
                    encoding="utf-8",
                    capture_output=True,
                    shell=False,
                    check=True,
                    timeout=300,
                    cwd=self.root,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                if not pending.is_file() or pending.stat().st_size == 0:
                    raise AudioUnavailableError("Local TTS produced no audio")
                pending.replace(dest)
        except (OSError, UnicodeError, subprocess.SubprocessError):
            raise AudioUnavailableError(
                "Local TTS synthesis failed; check the engine and network"
            ) from None
        return AudioResult(
            status="BUILT",
            provider="tts",
            audio_files=[self.result_path(dest)],
            details={"voice": self.voice, "deprecated": True},
        )
