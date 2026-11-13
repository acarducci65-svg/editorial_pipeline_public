from datetime import datetime, timezone

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
    approval = HumanApproval("director", datetime.now(timezone.utc), "receipt", "human")
    assert GateDecision(1, post_id, approval).approval == approval
    with pytest.raises(GhostApprovalForbiddenError):
        GateDecision(3, post_id, approval)
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
