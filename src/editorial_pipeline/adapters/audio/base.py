"""Audio generation port; generating assets never grants publication approval."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from editorial_pipeline.config.models import relative_path


class AudioResult(BaseModel):
    status: Literal["BUILT", "DRY_RUN", "SKIPPED"]
    provider: str
    audio_files: list[str] = Field(default_factory=list)
    script_file: str | None = None
    duration_seconds: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AudioUnavailableError(RuntimeError):
    """Audio provider unavailable; messages must never include raw diagnostics."""


class AudioProvider(ABC):
    def __init__(self, project_root: Path) -> None:
        self.root = project_root.resolve()

    def destination(self, post_id: str, output_dir: Path, filename: str) -> Path:
        relative_path(post_id)
        if post_id in {".", ".."} or "/" in post_id or "\\" in post_id:
            raise ValueError("invalid audio post identifier")
        path = output_dir / filename
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("audio output must remain inside the project")
        if any(p.is_symlink() for p in (path, *path.parents) if p != self.root):
            raise ValueError("audio output must not contain symlinks")
        return path

    def result_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    @abstractmethod
    def build(
        self,
        post_id: str,
        draft_text: str,
        sources: list[dict[str, Any]],
        output_dir: Path,
        dry_run: bool = False,
    ) -> AudioResult:
        """Build from validated source/claim records supplied by the caller."""
