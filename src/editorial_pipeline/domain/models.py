from dataclasses import dataclass
from enum import Enum
from typing import NewType

from editorial_pipeline.domain.gates import HumanApproval

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


@dataclass(frozen=True)
class EvidenceBundle:
    post_id: PostId
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    gate: int
    post_id: PostId
    approval: HumanApproval

    def __post_init__(self) -> None:
        from editorial_pipeline.domain.gates import GhostApprovalForbiddenError

        if self.gate not in (1, 2) or not isinstance(self.approval, HumanApproval):
            raise GhostApprovalForbiddenError("gate requires a human approval")
