"""Optional NotebookLM adapter; no remote operation is assumed."""

import os
import shutil
from pathlib import Path

from editorial_pipeline.adapters.rag.base import RagProvider, RagUnavailableError
from editorial_pipeline.domain.models import Finding


class NotebookLMAdapter(RagProvider):
    def __init__(
        self, corpus_id: str | None = None, corpus_id_env: str = "EDITORIAL_RAG_ID"
    ) -> None:
        self._corpus_id = corpus_id
        self._corpus_id_env = corpus_id_env

    def capabilities(self) -> set[str]:
        return {"fact_check"}

    def verify(self, claims: list[str], evidence_path: Path) -> list[Finding]:
        if not (self._corpus_id or os.environ.get(self._corpus_id_env)):
            raise RagUnavailableError("RAG corpus is not configured")
        if shutil.which("nlm") is None:
            raise RagUnavailableError("NotebookLM CLI is unavailable")
        raise RagUnavailableError("NotebookLM verification is not implemented")
