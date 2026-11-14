import re
from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, model_validator

Digest = Annotated[str, Field(pattern=r"^v1:[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1, pattern=r"\S")]


class ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Gate1Bundle(ReceiptModel):
    draft_digest: Digest
    sources_digest: Digest
    factcheck_digest: Digest
    review_digest: Digest


class Gate2Bundle(ReceiptModel):
    draft_digest: Digest
    gate1_digest: Digest
    artifacts: Annotated[dict[NonEmpty, Digest], Field(min_length=1)]


class Receipt(ReceiptModel):
    schema_version: Literal[1]
    post_id: NonEmpty
    role: NonEmpty
    decision: Literal["approved"]
    timestamp: AwareDatetime
    excerpt: NonEmpty

    @model_validator(mode="before")
    @classmethod
    def integer_identifiers(cls, value: object) -> object:
        if isinstance(value, dict):
            for key in ("schema_version", "gate"):
                if type(value.get(key)) is not int:
                    raise ValueError("receipt schema_version and gate must be integers")
            # A model pre-validator materializes JSON values before strict
            # datetime parsing; parse only ISO strings, never numeric epochs.
            if isinstance(value.get("timestamp"), str):
                value = dict(value)
                value["timestamp"] = datetime.fromisoformat(
                    value["timestamp"].replace("Z", "+00:00")
                )
        return value


class Gate1Receipt(Receipt):
    gate: Literal[1]
    bundle: Gate1Bundle


class Gate2Receipt(Receipt):
    gate: Literal[2]
    bundle: Gate2Bundle
    allowed_actions: Annotated[list[NonEmpty], Field(min_length=1)]


GateReceipt = Gate1Receipt | Gate2Receipt
RECEIPT_ADAPTER: TypeAdapter[GateReceipt] = TypeAdapter(
    Annotated[GateReceipt, Field(discriminator="gate")]
)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def mentions(excerpt: str, phrase: str) -> bool:
    """Match a complete phrase, never a prefix of an identifier or action."""
    return bool(
        re.search(
            r"(?<![\w-])" + re.escape(_normalized(phrase)) + r"(?![\w-])", _normalized(excerpt)
        )
    )


def validate_excerpt(
    excerpt: str, approval_phrase: str, post_id: str, forbidden_excerpts: list[str]
) -> None:
    text = _normalized(excerpt)
    phrase = approval_phrase.replace("{unit_id}", post_id)
    # Fail closed on negation or conditions anywhere in the supplied declaration.
    ambiguous = re.search(
        r"\b(non|not|never|unless|if|provided|pending|conditional|"
        r"se|qualora|purché|salvo|condizione|condizionat\w*)\b|"
        r"\b(do not|don't|only when|a patto)\b",
        text,
    )
    if (
        not phrase.strip()
        or not mentions(text, phrase)
        or ambiguous
        or any(_normalized(item) in text for item in forbidden_excerpts if item.strip())
    ):
        raise GhostApprovalForbiddenError("receipt excerpt lacks unconditional human approval")


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
