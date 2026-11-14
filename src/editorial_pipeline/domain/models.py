from dataclasses import dataclass
from enum import Enum
from typing import NewType

from editorial_pipeline.domain.gates import Gate1Receipt, Gate2Receipt, GateReceipt

PostId = NewType("PostId", str)


class VerificationState(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class Post:
    id: PostId
    title: str
    body: str


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    state: VerificationState


@dataclass(frozen=True)
class ChecklistState:
    findings: tuple[Finding, ...] = ()

    @property
    def blocked(self) -> bool:
        return any(finding.state == VerificationState.BLOCK for finding in self.findings)


@dataclass(frozen=True)
class EvidenceBundle:
    post_id: PostId
    findings: tuple[Finding, ...] = ()

    @property
    def checklist(self) -> ChecklistState:
        return ChecklistState(self.findings)


@dataclass(frozen=True)
class GateDecision:
    """A gate result references a formal receipt for this exact gate and post."""

    gate: int
    post_id: PostId
    receipt: GateReceipt

    def __post_init__(self) -> None:
        from editorial_pipeline.domain.gates import GhostApprovalForbiddenError

        if (
            not isinstance(self.receipt, (Gate1Receipt, Gate2Receipt))
            or self.gate != self.receipt.gate
            or self.post_id != self.receipt.post_id
        ):
            raise GhostApprovalForbiddenError("gate requires a matching formal receipt")
