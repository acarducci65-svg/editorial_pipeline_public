"""Port for building social visual artifacts (carousels) from editorial content."""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ASPECT_RATIOS: dict[str, tuple[int, int]] = {"4:5": (1080, 1350), "1:1": (1080, 1080)}
_POST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class VisualBuildError(RuntimeError):
    """A visual artifact could not be built."""


class TemplateNotFoundError(VisualBuildError):
    """The requested visual template is missing."""


@dataclass(frozen=True)
class Slide:
    number: int
    title: str
    text: str
    highlight: str | None = None

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("slide number must be positive")
        if not self.title.strip():
            raise ValueError("slide title must not be empty")


@dataclass(frozen=True)
class CarouselSpec:
    post_id: str
    title: str
    subtitle: str
    author: str
    slides: list[Slide]
    aspect_ratio: str = "4:5"

    def __post_init__(self) -> None:
        if not _POST_ID.fullmatch(self.post_id):
            raise ValueError("post_id must be a safe identifier (letters, digits, '-', '_')")
        if self.aspect_ratio not in ASPECT_RATIOS:
            raise ValueError("unsupported aspect ratio")
        if not self.slides:
            raise ValueError("a carousel needs at least one slide")
        numbers = [slide.number for slide in self.slides]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("slides must be numbered consecutively from 1")

    @property
    def size(self) -> tuple[int, int]:
        return ASPECT_RATIOS[self.aspect_ratio]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_digest(files: list[dict[str, str]]) -> str:
    """Digest over the sorted ``path:sha256`` pairs, independent of file order."""
    lines = sorted(f"{entry['path']}:{entry['sha256']}" for entry in files)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArtifactManifest:
    post_id: str
    artifact_type: str
    files: list[dict[str, str]]
    digest: str
    notes: list[str] = field(default_factory=list)

    def verify(self) -> bool:
        return self.digest == manifest_digest(self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "artifact_type": self.artifact_type,
            "files": [dict(entry) for entry in self.files],
            "digest": self.digest,
            "notes": list(self.notes),
        }


class VisualBuilder(ABC):
    @abstractmethod
    def build_carousel(self, spec: CarouselSpec, output_dir: Path) -> ArtifactManifest:
        """Build the carousel artifacts under ``output_dir`` and describe them."""
