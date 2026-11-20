import json
from datetime import datetime, timezone
from typing import Any

import pytest

from editorial_pipeline.domain.gates import GhostApprovalForbiddenError, HumanApproval


def test_human_approval_requires_explicit_human_evidence() -> None:
    approval = HumanApproval(
        author="director", timestamp=datetime.now(timezone.utc), token="receipt", source="human"
    )
    assert approval.author == "director"
    with pytest.raises(GhostApprovalForbiddenError):
        HumanApproval(
            author="agent",
            timestamp=datetime.now(timezone.utc),
            token="receipt",
            source="automated",  # type: ignore[arg-type]
        )


def test_domain_models_and_gate_validation() -> None:
    from dataclasses import FrozenInstanceError

    from editorial_pipeline.domain import (
        ChecklistState,
        EvidenceBundle,
        Finding,
        GateDecision,
        Post,
        PostId,
        VerificationState,
    )

    post_id = PostId("sample")
    post = Post(post_id, "Title", "Body")
    finding = Finding("source", "Checked", VerificationState.OK)
    assert ChecklistState((finding,)).findings == EvidenceBundle(post_id, (finding,)).findings
    with pytest.raises(FrozenInstanceError):
        post.title = "Changed"  # type: ignore[misc]
    from editorial_pipeline.domain.gates import Gate1Receipt

    receipt = Gate1Receipt.model_validate_json(
        '{"schema_version":1,"gate":1,"post_id":"sample","role":"director",'
        '"decision":"approved","timestamp":"2026-11-14T12:00:00+01:00",'
        '"excerpt":"Approvo Gate 1 #sample","bundle":{'
        + ",".join(
            f'"{key}_digest":"v1:{"a" * 64}"' for key in ("draft", "sources", "factcheck", "review")
        )
        + "}}"
    )
    assert GateDecision(1, post_id, receipt).receipt == receipt
    with pytest.raises(GhostApprovalForbiddenError):
        GateDecision(3, post_id, receipt)
    with pytest.raises(GhostApprovalForbiddenError):
        GateDecision(1, PostId("other"), receipt)
    with pytest.raises(GhostApprovalForbiddenError):
        GateDecision(2, post_id, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(("author", "token"), [("", "receipt"), ("director", "")])
def test_reject_incomplete_approval(author: str, token: str) -> None:
    with pytest.raises(GhostApprovalForbiddenError):
        HumanApproval(author, datetime.now(timezone.utc), token, "human")


def test_reject_naive_timestamp() -> None:
    with pytest.raises(GhostApprovalForbiddenError):
        HumanApproval("director", datetime(2026, 1, 1), "receipt", "human")


def test_approval_binds_matching_evidence() -> None:
    approval = HumanApproval("director", datetime.now(timezone.utc), "digest", "human")
    approval.bind_evidence("digest")
    for digest in ("", "other"):
        with pytest.raises(GhostApprovalForbiddenError):
            approval.bind_evidence(digest)


@pytest.mark.parametrize(
    "excerpt",
    [
        "Non approvo Gate 1 #post_01",
        "Approvo Gate 1 #post_01 solo se tutto passa",
        "Approvo Gate 1 #post_01; automatically approved",
        "Approvo Gate 1 #post_01; auto-review",
        "Approvo Gate 1 #post_01; stop hook",
        "I do not approve. Approvo Gate 1 #post_01",
        "Approvo Gate 1 #post_01 if checks pass",
        "Approvo Gate 1 #post_010",
        "Approvo Gate 1 #other",
    ],
)
def test_receipt_excerpt_rejects_ghost_or_ambiguous_approval(excerpt: str) -> None:
    from editorial_pipeline.domain.gates import validate_excerpt

    with pytest.raises(GhostApprovalForbiddenError):
        validate_excerpt(
            excerpt,
            "Approvo Gate 1 #{unit_id}",
            "post_01",
            ["automatically approved", "auto-review", "stop hook"],
        )


def test_receipt_excerpt_normalizes_case_and_whitespace() -> None:
    from editorial_pipeline.domain.gates import validate_excerpt

    validate_excerpt("  APPROVO   Gate 1   #post_01. ", "Approvo Gate 1 #{unit_id}", "post_01", [])


@pytest.mark.parametrize(
    "approval_phrase",
    ["Approvo Gate 1 #{unit_id}", "Approvo Gate 1 #{{UNIT_ID}}"],
)
def test_receipt_excerpt_resolves_unit_id_placeholders(approval_phrase: str) -> None:
    from editorial_pipeline.domain.gates import validate_excerpt

    validate_excerpt("Approvo Gate 1 #post_01", approval_phrase, "post_01", [])
    with pytest.raises(GhostApprovalForbiddenError):
        validate_excerpt("Approvo Gate 1 #other", approval_phrase, "post_01", [])
    with pytest.raises(GhostApprovalForbiddenError):
        validate_excerpt("Approvo Gate 1 #{{UNIT_ID}}", approval_phrase, "post_01", [])
    with pytest.raises(GhostApprovalForbiddenError):
        validate_excerpt("Non approvo Gate 1 #post_01", approval_phrase, "post_01", [])
    with pytest.raises(GhostApprovalForbiddenError):
        validate_excerpt(
            "Approvo Gate 1 #post_01; stop hook", approval_phrase, "post_01", ["stop hook"]
        )


def test_example_config_uses_resolvable_approval_phrases_and_gate2_actions() -> None:
    import sys
    from pathlib import Path

    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - exercised only on Python 3.10
        import tomli as tomllib

    from editorial_pipeline.domain.gates import validate_excerpt

    example = Path(__file__).resolve().parents[1] / "editorial.example.toml"
    config = tomllib.loads(example.read_text(encoding="utf-8"))
    gate1 = config["gates"]["gate1"]
    gate2 = config["gates"]["gate2"]

    assert gate1["approval_phrase"] == "Approvo Gate 1 #{unit_id}"
    assert gate2["approval_phrase"] == "Approvo Gate 2 #{unit_id}"
    for action in ("publish", "schedule", "sync", "export_markdown", "archive"):
        assert action in gate2["allowed_actions"]

    validate_excerpt("Approvo Gate 1 #ep_01", gate1["approval_phrase"], "ep_01", [])
    validate_excerpt("Approvo Gate 2 #ep_01", gate2["approval_phrase"], "ep_01", [])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", "1"),
        ("gate", True),
        ("gate", 1.0),
        ("gate", "1"),
        ("timestamp", "2026-11-14T12:00:00"),
        ("timestamp", 1234567890),
        ("post_id", ""),
        ("role", " "),
        ("excerpt", ""),
        ("unexpected", "field"),
    ],
)
def test_receipt_schema_rejects_invalid_types(field: str, value: object) -> None:
    from pydantic import ValidationError

    from editorial_pipeline.domain.gates import RECEIPT_ADAPTER

    data: dict[str, Any] = {
        "schema_version": 1,
        "gate": 1,
        "post_id": "sample",
        "role": "director",
        "decision": "approved",
        "timestamp": "2026-11-14T12:00:00+01:00",
        "excerpt": "Approvo Gate 1 #sample",
        "bundle": {
            f"{key}_digest": "v1:" + "a" * 64 for key in ("draft", "sources", "factcheck", "review")
        },
    }
    data[field] = value
    with pytest.raises(ValidationError):
        RECEIPT_ADAPTER.validate_json(json.dumps(data))
