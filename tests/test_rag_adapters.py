import json
from pathlib import Path
from typing import Any

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
    assert any(
        f.state is VerificationState.BLOCK
        for f in provider.verify(["unknown"], EVIDENCE / "post_01")
    )
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
            {
                "claim_id": "A",
                "text": "a",
                "outcome": "verified_external",
                "source_key": "s",
                "locator": "page 1",
            },
            {
                "claim_id": "B",
                "text": "b",
                "outcome": "verified_external",
                "source_key": "unknown",
                "locator": "page 1",
            },
            {
                "claim_id": "C",
                "text": "c",
                "outcome": "grounded_secondary",
                "source_key": "s",
                "locator": "p1",
            },
            {"claim_id": "D", "text": "d", "outcome": "disputed"},
            {
                "claim_id": "E",
                "text": "e",
                "outcome": "verified_external",
                "source_key": "s",
                "locator": "",
            },
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


@pytest.mark.parametrize(
    "change,code",
    [
        ("valid", ""),
        ("draft", "rag.stale_factcheck"),
        ("review_digest", "humanizer.stale_review"),
        ("review_missing", "humanizer.review"),
        ("review_fail", "humanizer.review"),
        ("review_item", "humanizer.review"),
        ("primary", "rag.source"),
        ("local_copy", "rag.source"),
        ("circular", "rag.source"),
        ("outcome", "rag.claim"),
        ("duplicate", "rag.schema"),
        ("post_id", "rag.schema"),
        ("both_post_id", "rag.schema"),
        ("review_post_id", "humanizer.review"),
        ("review_schema", "humanizer.review"),
        ("missing_digest", "rag.stale_factcheck"),
        ("local_path", "rag.source"),
        ("traversal", "rag.source"),
        ("local_present", ""),
    ],
)
def test_unified_evidence_blocks(tmp_path: Path, change: str, code: str) -> None:
    from editorial_pipeline.application.evidence_verifier import EvidenceVerifier
    from editorial_pipeline.cli.reports import digest
    from editorial_pipeline.config import load_config

    config = load_config(Path("examples/sample_blog/editorial.toml"))
    post = tmp_path / "draft.md"
    post.write_text("Use `x[1]` for the ‘value’. [12]", encoding="utf-8")
    sources: dict[str, Any] = {"post_id": "p", "sources": [{"key": "s", "primary": True}]}
    checks: dict[str, Any] = {
        "post_id": "p",
        "draft_digest": digest(post, tmp_path),
        "claims": [
            {
                "claim_id": "C1",
                "text": "Use `x[1]` for the 'value'.",
                "outcome": "grounded_primary",
                "source_key": "s",
                "locator": "p1",
            }
        ],
    }
    review: dict[str, Any] = {
        "post_id": "p",
        "draft_digest": digest(post, tmp_path),
        "items": dict.fromkeys(config.humanizer.required_items, "pass"),
    }
    if change == "draft":
        post.write_text(post.read_text(encoding="utf-8") + "!", encoding="utf-8")
    elif change == "review_digest":
        review["draft_digest"] = "old"
    elif change == "review_fail":
        review["items"][config.humanizer.required_items[0]] = "fail"
    elif change == "review_item":
        review["items"].pop(config.humanizer.required_items[0])
    elif change == "primary":
        sources["sources"][0]["primary"] = False
    elif change == "local_copy":
        sources["sources"][0]["local_copy"] = "missing.md"
    elif change == "circular":
        sources["sources"][0]["tags"] = ["self_draft"]
    elif change == "outcome":
        checks["claims"][0]["outcome"] = "verified"
    elif change == "duplicate":
        checks["claims"] *= 2
    elif change == "post_id":
        sources["post_id"] = "other"
    elif change == "both_post_id":
        sources["post_id"] = checks["post_id"] = "other"
    elif change == "review_post_id":
        review["post_id"] = "other"
    elif change == "review_schema":
        review["items"] = []
    elif change == "missing_digest":
        checks.pop("draft_digest")
    elif change == "local_path":
        sources["sources"][0]["local_path"] = "missing.md"
    elif change == "traversal":
        sources["sources"][0]["local_copy"] = "../outside.md"
    elif change == "local_present":
        (tmp_path / "copy.md").write_text("Evidence", encoding="utf-8")
        sources["sources"][0]["local_copy"] = "copy.md"
    for name, data in [("sources", sources), ("factcheck", checks), ("draft-review", review)]:
        if name == "draft-review" and change == "review_missing":
            continue
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    findings = EvidenceVerifier(config, tmp_path).verify(post, "p", tmp_path)
    if change in ("valid", "local_present"):
        assert findings and all(f.state is VerificationState.OK for f in findings)
    else:
        assert any(f.code == code and f.state is VerificationState.BLOCK for f in findings)


def test_claim_normalization_preserves_code() -> None:
    from editorial_pipeline.application.evidence_verifier import normalize_claim

    assert normalize_claim("Use  ‘value’\n[12] with `x[1]`") == "Use 'value' with `x[1]`"
    assert normalize_claim("Use `x[1]`") != normalize_claim("Use `x[2]`")
    assert normalize_claim("Use ``x  [1]``") == "Use ``x  [1]``"


@pytest.mark.parametrize(
    "allowed,blocking,state",
    [
        (["verified"], [], VerificationState.OK),
        (["verified"], ["verified"], VerificationState.BLOCK),
        ([], [], VerificationState.BLOCK),
    ],
)
def test_local_factory_uses_configured_outcomes(
    tmp_path: Path,
    allowed: list[str],
    blocking: list[str],
    state: VerificationState,
) -> None:
    from editorial_pipeline.config import load_config

    config = load_config(Path("examples/sample_blog/editorial.toml"))
    config = config.model_copy(
        update={
            "factcheck": config.factcheck.model_copy(
                update={"allowed_outcomes": allowed, "blocking_outcomes": blocking}
            )
        }
    )
    (tmp_path / "sources.json").write_text(
        json.dumps({"post_id": "p", "sources": [{"key": "s"}]}), encoding="utf-8"
    )
    (tmp_path / "factcheck.json").write_text(
        json.dumps(
            {
                "post_id": "p",
                "claims": [
                    {
                        "id": "C1",
                        "text": "claim",
                        "outcome": "verified",
                        "source_key": "s",
                        "locator": "p1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    provider = get_rag_provider("local", config, tmp_path)
    assert provider.verify(["claim"], tmp_path)[0].state is state


@pytest.mark.parametrize(
    "kind",
    ["duplicate_source", "conflicting_id", "empty_claims", "bad_type", "bad_json", "blank_claim"],
)
def test_local_rejects_invalid_schema(tmp_path: Path, kind: str) -> None:
    sources: dict[str, Any] = {"post_id": "p", "sources": [{"key": "s"}]}
    checks: dict[str, Any] = {
        "post_id": "p",
        "claims": [
            {
                "claim_id": "C1",
                "text": "claim",
                "outcome": "verified_external",
                "source_key": "s",
                "locator": "p1",
            }
        ],
    }
    if kind == "duplicate_source":
        sources["sources"] *= 2
    elif kind == "conflicting_id":
        checks["claims"][0]["id"] = "C2"
    elif kind == "empty_claims":
        checks["claims"] = []
    elif kind == "bad_type":
        sources["sources"][0]["primary"] = "true"
    elif kind == "blank_claim":
        checks["claims"][0]["text"] = "  "
    (tmp_path / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    (tmp_path / "factcheck.json").write_text(
        "bad" if kind == "bad_json" else json.dumps(checks), encoding="utf-8"
    )
    with pytest.raises(InvalidEvidenceError):
        LocalRagProvider().verify(["claim"], tmp_path)


def test_claim_citation_before_punctuation() -> None:
    from editorial_pipeline.application.evidence_verifier import normalize_claim

    assert normalize_claim("A statement [12]. Use `a[1]` [2].") == "A statement. Use `a[1]`."
