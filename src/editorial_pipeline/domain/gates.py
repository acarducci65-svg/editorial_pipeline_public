from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from typing import Literal


class GhostApprovalForbiddenError(ValueError):
    """An automated or incomplete approval cannot cross a human gate."""


@dataclass(frozen=True)
class HumanApproval:
    author: str
    timestamp: datetime
    token: str
    source: Literal["human"]

    def __post_init__(self) -> None:
        if (
            self.source != "human"
            or not self.author.strip()
            or not self.token.strip()
            or not isinstance(self.timestamp, datetime)
            or self.timestamp.utcoffset() is None
        ):
            raise GhostApprovalForbiddenError(
                "explicit human approval, timestamp and token required"
            )

    def bind_evidence(self, evidence_digest: str) -> None:
        """Verify that the human receipt token matches the supplied evidence digest."""
        if (
            self.source != "human"
            or not evidence_digest.strip()
            or not compare_digest(self.token.encode("utf-8"), evidence_digest.encode("utf-8"))
        ):
            raise GhostApprovalForbiddenError("human approval does not match evidence")
