"""Port for evidence-based claim verification."""

from abc import ABC, abstractmethod
from pathlib import Path

from editorial_pipeline.domain.models import Finding


class RagUnavailableError(RuntimeError):
    """The requested RAG provider is unavailable."""


class InvalidEvidenceError(ValueError):
    """Evidence cannot be interpreted safely."""


class EvidenceMissingError(FileNotFoundError):
    """A required evidence file is missing."""


class RagProvider(ABC):
    @abstractmethod
    def capabilities(self) -> set[str]:
        """Return supported operations."""

    @abstractmethod
    def verify(self, claims: list[str], evidence_path: Path) -> list[Finding]:
        """Check claims against evidence."""
