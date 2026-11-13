"""RAG provider interfaces and factory."""

from pathlib import Path

from editorial_pipeline.adapters.rag.base import (
    EvidenceMissingError,
    InvalidEvidenceError,
    RagProvider,
    RagUnavailableError,
)
from editorial_pipeline.adapters.rag.local import LocalRagProvider
from editorial_pipeline.adapters.rag.notebooklm import NotebookLMAdapter
from editorial_pipeline.config.models import EditorialConfig


def get_rag_provider(
    name: str, config: EditorialConfig | None = None, root: Path | None = None
) -> RagProvider:
    if name == "local":
        return LocalRagProvider()
    if name == "notebooklm":
        env = config.providers.rag.corpus_id_env if config is not None else "EDITORIAL_RAG_ID"
        return NotebookLMAdapter(corpus_id_env=env)
    raise ValueError("Unknown RAG provider")


__all__ = [
    "EvidenceMissingError",
    "InvalidEvidenceError",
    "LocalRagProvider",
    "NotebookLMAdapter",
    "RagProvider",
    "RagUnavailableError",
    "get_rag_provider",
]
