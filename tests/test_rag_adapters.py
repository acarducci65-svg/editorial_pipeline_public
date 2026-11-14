import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

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
    assert remote.capabilities() == {"fact_check"}
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


def test_remote_cli_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EDITORIAL_RAG_ID", "temporary-value")
    monkeypatch.setattr("editorial_pipeline.adapters.rag.notebooklm.shutil.which", lambda _: None)
    with pytest.raises(RagUnavailableError, match="CLI"):
        NotebookLMAdapter().verify(["claim"], tmp_path)


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


@pytest.fixture
def nlm(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.delenv("EDITORIAL_RAG_ID", raising=False)
    monkeypatch.setattr("editorial_pipeline.adapters.rag.notebooklm.shutil.which", lambda _: "nlm")
    run = Mock(
        return_value=subprocess.CompletedProcess(
            [], 0, '{"answer":"Supported", "citations":[{"id":"source"}]}', ""
        )
    )
    monkeypatch.setattr("subprocess.run", run)
    return run


def test_remote_empty_and_missing_corpus(nlm: Mock, tmp_path: Path) -> None:
    assert NotebookLMAdapter().verify([], tmp_path) == []
    with pytest.raises(RagUnavailableError, match="corpus is not configured"):
        NotebookLMAdapter().verify(["claim"], tmp_path)
    nlm.assert_not_called()


@pytest.mark.parametrize("field", ["answer", "text", "content"])
@pytest.mark.parametrize("references", ["citations", "sources"])
def test_remote_supported(nlm: Mock, tmp_path: Path, field: str, references: str) -> None:
    nlm.return_value.stdout = json.dumps(
        {field: "Supported by the document", references: ["source"]}
    )
    adapter = NotebookLMAdapter(corpus_id="test-corpus", timeout=12.5, cli_path="custom-nlm")
    result = adapter.verify(["claim; echo unsafe", "second claim"], tmp_path)
    assert [f.state for f in result] == [VerificationState.OK, VerificationState.OK]
    assert all(f.code == "rag.claim" for f in result)
    args, kwargs = nlm.call_args_list[0]
    assert args[0] == [
        "custom-nlm",
        "query",
        "notebook",
        "test-corpus",
        "Verifica se la seguente affermazione e' supportata dalle fonti: 'claim; echo unsafe'",
        "--json",
        "--timeout",
        "12.5",
    ]
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "timeout": 22.5,
        "shell": False,
    }
    assert nlm.call_count == 2


@pytest.mark.parametrize("explicit", [None, "explicit-corpus"])
def test_remote_corpus_precedence(
    nlm: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, explicit: str | None
) -> None:
    monkeypatch.setenv("TEST_RAG_CORPUS", "environment-corpus")
    NotebookLMAdapter(corpus_id=explicit, corpus_id_env="TEST_RAG_CORPUS").verify(
        ["claim"], tmp_path
    )
    assert nlm.call_args.args[0][3] == (explicit or "environment-corpus")


@pytest.mark.parametrize(
    "answer,citations,state",
    [
        ("The claim is not supported", ["source"], VerificationState.BLOCK),
        ("No evidence was found", ["source"], VerificationState.BLOCK),
        ("Non supportato dalle fonti", ["source"], VerificationState.BLOCK),
        ("Supported", [], VerificationState.BLOCK),
        ("Supported", None, VerificationState.BLOCK),
        ("Partially supported", ["source"], VerificationState.WARN),
        ("Uncertain evidence", ["source"], VerificationState.WARN),
        ("", ["source"], VerificationState.WARN),
        # nlm >= 0.15 maps citation numbers to source identifiers.
        ("Supported", {"1": "source"}, VerificationState.OK),
        ("Supported", {}, VerificationState.BLOCK),
        ("Non supportato dalle fonti", {"1": "source"}, VerificationState.BLOCK),
    ],
)
def test_remote_classification(
    nlm: Mock, tmp_path: Path, answer: str, citations: object, state: VerificationState
) -> None:
    nlm.return_value.stdout = json.dumps({"answer": answer, "citations": citations})
    assert NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)[0].state is state


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        "[]",
        "null",
        "{}",
        '{"answer":42}',
        '{"answer":"Supported","citations":"invalid"}',
    ],
)
def test_remote_invalid_output(nlm: Mock, tmp_path: Path, output: str) -> None:
    nlm.return_value.stdout = output
    with pytest.raises(RagUnavailableError, match="invalid JSON response"):
        NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)


@pytest.mark.parametrize("error", ["Please LOGIN", "Authentication expired", "Invalid cookie"])
def test_remote_auth(nlm: Mock, tmp_path: Path, error: str) -> None:
    nlm.return_value = subprocess.CompletedProcess([], 1, "", error)
    with pytest.raises(RagUnavailableError, match="nlm login"):
        NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)


def test_remote_error_privacy(nlm: Mock, tmp_path: Path) -> None:
    nlm.return_value = subprocess.CompletedProcess(
        [], 2, "private stdout", "private stderr test-corpus"
    )
    with pytest.raises(RagUnavailableError, match="query failed") as caught:
        NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)
    assert "private" not in str(caught.value)
    assert "test-corpus" not in str(caught.value)


@pytest.mark.parametrize(
    "error,message",
    [
        (subprocess.TimeoutExpired("nlm", 60), "timed out after 60.0s"),
        (FileNotFoundError("private details"), "could not be executed"),
        (UnicodeError("private output"), "invalid text response"),
    ],
)
def test_remote_process_exceptions(
    nlm: Mock, tmp_path: Path, error: Exception, message: str
) -> None:
    nlm.side_effect = error
    with pytest.raises(RagUnavailableError, match=message):
        NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)


def test_remote_factory_config(nlm: Mock, tmp_path: Path) -> None:
    from editorial_pipeline.config import load_config
    from editorial_pipeline.config.models import RagConfig

    config = load_config(Path("examples/sample_blog/editorial.toml"))
    defaults = RagConfig()
    assert defaults.corpus_id is None
    assert defaults.corpus_id_env == "EDITORIAL_RAG_ID"
    assert defaults.timeout_seconds == 60.0
    config = config.model_copy(
        update={"rag": RagConfig(provider="notebooklm", corpus_id="test-corpus", timeout_seconds=9)}
    )
    provider = get_rag_provider("notebooklm", config, tmp_path)
    provider.verify(["claim"], tmp_path)
    assert nlm.call_args.args[0][3] == "test-corpus"
    assert nlm.call_args.kwargs["timeout"] == 19


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_remote_rejects_invalid_timeout(timeout: float) -> None:
    from pydantic import ValidationError

    from editorial_pipeline.config.models import RagConfig

    with pytest.raises(ValueError, match="finite and positive"):
        NotebookLMAdapter(timeout=timeout)
    with pytest.raises(ValidationError):
        RagConfig(timeout_seconds=timeout)


@pytest.mark.parametrize("provider", ["local", "manual", "none", "notebooklm"])
def test_rag_configuration_loads(tmp_path: Path, provider: str) -> None:
    from editorial_pipeline.config import load_config

    text = Path("examples/sample_blog/editorial.toml").read_text(encoding="utf-8")
    path = tmp_path / "editorial.toml"
    path.write_text(
        text
        + f'\n[rag]\nprovider = "{provider}"\ncorpus_id_env = "TEST_RAG_CORPUS"\ntimeout_seconds = 15\n',
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.rag is not None
    assert config.rag.provider == provider
    assert config.rag.corpus_id_env == "TEST_RAG_CORPUS"


def test_remote_factory_legacy_env(
    nlm: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from editorial_pipeline.config import load_config

    config = load_config(Path("examples/sample_blog/editorial.toml"))
    monkeypatch.setenv(config.providers.rag.corpus_id_env, "environment-corpus")
    get_rag_provider("notebooklm", config).verify(["claim"], tmp_path)
    assert nlm.call_args.args[0][3] == "environment-corpus"


@pytest.mark.parametrize("configured", [True, False])
def test_remote_cli_queries_claims(
    nlm: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    configured: bool,
) -> None:
    import shutil

    from editorial_pipeline.cli.commands import main

    project = tmp_path / "blog"
    shutil.copytree(Path("examples/sample_blog"), project)
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    if configured:
        text += '\n[rag]\nprovider = "notebooklm"\ncorpus_id_env = "TEST_RAG_CORPUS"\ntimeout_seconds = 8\n'
        monkeypatch.setenv("TEST_RAG_CORPUS", "environment-corpus")
    else:
        text = text.replace(
            '[providers.rag]\nadapter = "local"', '[providers.rag]\nadapter = "notebooklm"'
        )
        monkeypatch.setenv("EDITORIAL_RAG_ID", "environment-corpus")
    config.write_text(text, encoding="utf-8")
    result = main(["verify-facts", "post_01_valid.md", "--config", str(config)])
    assert result == 0, capsys.readouterr()
    assert nlm.call_count > 0
    assert all(call.args[0][3] == "environment-corpus" for call in nlm.call_args_list)
    checks = json.loads((project / "evidence/post_01/factcheck.json").read_text(encoding="utf-8"))
    assert nlm.call_count == len(checks["claims"])


@pytest.mark.parametrize(
    "answer,citations",
    [
        ("The claim is contradicted by the sources", ["source"]),
        ("There is insufficient evidence", ["source"]),
        ("L'affermazione non e supportata dalle fonti", ["source"]),
        ("Supported", [None, "", {}]),
    ],
)
def test_remote_denials_and_empty_references(
    nlm: Mock, tmp_path: Path, answer: str, citations: list[object]
) -> None:
    nlm.return_value.stdout = json.dumps({"answer": answer, "citations": citations})
    assert (
        NotebookLMAdapter("test-corpus").verify(["claim"], tmp_path)[0].state
        is VerificationState.BLOCK
    )


def test_remote_cli_invalid_evidence(
    nlm: Mock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import shutil

    from editorial_pipeline.cli.commands import main

    project = tmp_path / "blog"
    shutil.copytree(Path("examples/sample_blog"), project)
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + '\n[rag]\nprovider = "notebooklm"\n', encoding="utf-8"
    )
    (project / "evidence/post_01/factcheck.json").write_text("invalid", encoding="utf-8")
    assert main(["verify-facts", "post_01_valid.md", "--config", str(config)]) == 1
    assert '"rag.schema"' in capsys.readouterr().out
    nlm.assert_not_called()
