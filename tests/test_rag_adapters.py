import json
from pathlib import Path

import pytest

from editorial_pipeline.adapters.rag import (
    EvidenceMissingError,
    InvalidEvidenceError,
    LocalRagProvider,
    NotebookLMAdapter,
    RagUnavailableError,
    get_rag_provider,
)
from editorial_pipeline.domain.models import VerificationState

EVIDENCE = Path("examples/sample_blog/evidence")


def test_sample_claims() -> None:
    for post, expected in [("post_01", VerificationState.OK), ("post_02", VerificationState.BLOCK)]:
        folder = EVIDENCE / post
        data = json.loads((folder / "factcheck.json").read_text(encoding="utf-8"))
        findings = LocalRagProvider().verify([c["text"] for c in data["claims"]], folder)
        assert findings and all(f.state is expected for f in findings)


def test_missing_and_invalid_evidence(tmp_path: Path) -> None:
    provider = LocalRagProvider()
    with pytest.raises(EvidenceMissingError):
        provider.verify(["claim"], tmp_path / "missing")
    (tmp_path / "sources.json").write_text('{"sources": []}', encoding="utf-8")
    with pytest.raises(EvidenceMissingError):
        provider.verify(["claim"], tmp_path)
    (tmp_path / "factcheck.json").write_text("bad", encoding="utf-8")
    with pytest.raises(InvalidEvidenceError):
        provider.verify(["claim"], tmp_path)


def test_unknown_claim_and_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = get_rag_provider("local")
    assert provider.capabilities() == {"local_evidence", "fact_check"}
    assert provider.verify(["unknown"], EVIDENCE / "post_01")[0].state is VerificationState.BLOCK
    monkeypatch.delenv("EDITORIAL_RAG_ID", raising=False)
    remote = get_rag_provider("notebooklm")
    assert isinstance(remote, NotebookLMAdapter)
    with pytest.raises(RagUnavailableError):
        remote.verify(["claim"], EVIDENCE / "post_01")
    with pytest.raises(ValueError):
        get_rag_provider("unknown")


def test_check_outcomes_and_source_requirements(tmp_path: Path) -> None:
    sources = {"post_id": "p", "sources": [{"key": "s"}]}
    checks = {
        "post_id": "p",
        "claims": [
            {"text": "a", "outcome": "verified", "source_key": "s", "locator": "page 1"},
            {"text": "b", "outcome": "verified", "source_key": [], "locator": "page 1"},
            {"text": "c", "outcome": "grounded_secondary"},
            {"text": "d", "outcome": "disputed"},
            {"text": "e", "outcome": "verified", "source_key": "s", "locator": ""},
        ],
    }
    (tmp_path / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    (tmp_path / "factcheck.json").write_text(json.dumps(checks), encoding="utf-8")
    findings = LocalRagProvider().verify(list("abcde"), tmp_path)
    assert [f.state for f in findings] == [
        VerificationState.OK,
        VerificationState.BLOCK,
        VerificationState.WARN,
        VerificationState.BLOCK,
        VerificationState.BLOCK,
    ]


def test_remote_unavailable_even_when_cli_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EDITORIAL_RAG_ID", "temporary-value")
    monkeypatch.setattr("editorial_pipeline.adapters.rag.notebooklm.shutil.which", lambda _: None)
    with pytest.raises(RagUnavailableError, match="CLI"):
        NotebookLMAdapter().verify([], tmp_path)
    monkeypatch.setattr("editorial_pipeline.adapters.rag.notebooklm.shutil.which", lambda _: "nlm")
    with pytest.raises(RagUnavailableError, match="not implemented"):
        NotebookLMAdapter().verify([], tmp_path)
