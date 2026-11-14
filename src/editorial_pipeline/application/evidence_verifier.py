"""Deterministic evidence validation; never grants human approval."""

import re
from pathlib import Path, PureWindowsPath
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from editorial_pipeline.config.models import EditorialConfig, Factcheck
from editorial_pipeline.domain.models import Finding, VerificationState


def normalize_claim(text: str) -> str:
    """Normalize prose while preserving backtick-delimited code verbatim."""
    parts = re.split(r"(`+)(.*?)(\1)", text, flags=re.DOTALL)
    quotes = str.maketrans(
        {
            "\u2018": "'",
            "\u2019": "'",
            "\u02bc": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u00ab": '"',
            "\u00bb": '"',
        }
    )
    for index in range(0, len(parts), 4):
        parts[index] = re.sub(
            r"\s+", " ", re.sub(r"\s*\[\d+\]", "", parts[index]).translate(quotes)
        )
    return "".join(parts).strip()


class EvidenceError(ValueError):
    """Invalid schema or unreadable evidence (details intentionally omitted)."""


class _Model(BaseModel):
    model_config = ConfigDict(strict=True)
    post_id: str = Field(min_length=1, pattern=r"\S")


class Source(BaseModel):
    model_config = ConfigDict(strict=True)
    key: str = Field(min_length=1, pattern=r"\S")
    primary: bool = False
    tags: list[str] = Field(default_factory=list)
    local_copy: str | None = None
    local_path: str | None = None


class Claim(BaseModel):
    model_config = ConfigDict(strict=True)
    claim_id: str = Field(min_length=1, pattern=r"\S")
    text: str = Field(min_length=1, pattern=r"\S")
    outcome: str = Field(min_length=1, pattern=r"\S")
    source_key: str | None = None
    locator: str | None = None

    @model_validator(mode="before")
    @classmethod
    def legacy_id(cls, value: object) -> object:
        if isinstance(value, dict) and "id" in value:
            value = dict(value)
            if "claim_id" in value and value["claim_id"] != value["id"]:
                raise ValueError("Conflicting claim identifiers")
            value["claim_id"] = value["id"]
        return value


class Sources(_Model):
    sources: list[Source]


class FactcheckEvidence(_Model):
    draft_digest: str = ""
    claims: list[Claim] = Field(min_length=1)


class Review(_Model):
    draft_digest: str = ""
    items: dict[str, str]


M = TypeVar("M", bound=BaseModel)


def read_evidence(path: Path, model: type[M]) -> M:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise EvidenceError("Missing, unreadable or invalid evidence") from exc


def load_records(evidence: Path) -> tuple[Sources, FactcheckEvidence]:
    sources = read_evidence(evidence / "sources.json", Sources)
    checks = read_evidence(evidence / "factcheck.json", FactcheckEvidence)
    if (
        sources.post_id != checks.post_id
        or len({s.key for s in sources.sources}) != len(sources.sources)
        or len({c.claim_id for c in checks.claims}) != len(checks.claims)
    ):
        raise EvidenceError("Mismatched post identifiers or duplicate evidence identifiers")
    return sources, checks


def block(code: str, message: str) -> Finding:
    return Finding(code, message, VerificationState.BLOCK)


DEFAULT_POLICY = Factcheck(
    allowed_outcomes=["grounded_primary", "verified_external", "grounded_secondary"],
    blocking_outcomes=["unsupported", "contradicted"],
    promotion_outcomes=[],
    require_locator_for_promotion=True,
    circular_source_tags=["self_draft"],
)


def verify_records(
    sources: Sources,
    checks: FactcheckEvidence,
    root: Path,
    policy: Factcheck,
) -> list[Finding]:
    findings: list[Finding] = []
    invalid: set[str] = set()
    by_key = {s.key: s for s in sources.sources}
    for source in sources.sources:
        reasons = []
        if set(source.tags) & set(policy.circular_source_tags):
            reasons.append("circular source tag")
        for local in (source.local_copy, source.local_path):
            if local is not None:
                path = (root / local).resolve()
                if (
                    not local.strip()
                    or Path(local).is_absolute()
                    or bool(PureWindowsPath(local).drive)
                    or not path.is_relative_to(root.resolve())
                    or not path.is_file()
                ):
                    reasons.append("local copy missing or outside project")
        if reasons:
            invalid.add(source.key)
            findings.append(block("rag.source", f"Source {source.key}: {', '.join(reasons)}"))
    for claim in checks.claims:
        matched_source = by_key.get(claim.source_key or "")
        reason = "recorded evidence and locator present"
        state = VerificationState.OK
        if (
            claim.outcome in policy.blocking_outcomes
            or claim.outcome not in policy.allowed_outcomes
        ):
            reason, state = (
                f"outcome {claim.outcome} is blocked or not configured",
                VerificationState.BLOCK,
            )
        elif (
            matched_source is None
            or matched_source.key in invalid
            or not claim.locator
            or not claim.locator.strip()
        ):
            reason, state = "missing or invalid source/locator", VerificationState.BLOCK
        elif claim.outcome == "grounded_primary" and not matched_source.primary:
            findings.append(
                block("rag.source", f"claim_id={claim.claim_id}: source is not primary")
            )
            reason, state = "grounded_primary requires a primary source", VerificationState.BLOCK
        elif claim.outcome == "grounded_secondary":
            reason, state = "secondary evidence requires review", VerificationState.WARN
        findings.append(Finding("rag.claim", f"claim_id={claim.claim_id}: {reason}", state))
    return findings


class EvidenceVerifier:
    def __init__(self, config: EditorialConfig, root: Path) -> None:
        self.config = config
        self.root = root

    def verify(self, post: Path, post_id: str, evidence: Path) -> list[Finding]:
        findings: list[Finding] = []
        from editorial_pipeline.cli.reports import digest

        current = digest(post, self.root)
        try:
            sources, checks = load_records(evidence)
            if checks.post_id != post_id:
                raise EvidenceError("Evidence post_id differs from draft")
            if checks.draft_digest != current:
                findings.append(
                    block("rag.stale_factcheck", "Factcheck digest differs from current draft")
                )
            findings.extend(verify_records(sources, checks, self.root, self.config.factcheck))
            draft = normalize_claim(post.read_text(encoding="utf-8"))
            for claim in checks.claims:
                text = normalize_claim(claim.text)
                if not text or text not in draft:
                    findings.append(
                        Finding(
                            "rag.claim_not_in_draft",
                            f"claim_id={claim.claim_id}: no normalized match in draft",
                            VerificationState.WARN,
                        )
                    )
        except EvidenceError:
            findings.append(
                block(
                    "rag.schema", "Invalid sources/factcheck schema, identifiers or missing files"
                )
            )
        try:
            review = read_evidence(evidence / "draft-review.json", Review)
            if review.post_id != post_id:
                raise EvidenceError("Review post_id differs from draft")
            if review.draft_digest != current:
                findings.append(
                    block("humanizer.stale_review", "Review digest differs from current draft")
                )
                findings.append(
                    block("humanizer.review", "F2b review must be repeated on current draft")
                )
            for item in self.config.humanizer.required_items:
                if review.items.get(item) != "pass":
                    findings.append(
                        block("humanizer.review", f"Required F2b item {item}: missing or not pass")
                    )
        except EvidenceError:
            findings.append(
                block("humanizer.review", "Missing or invalid F2b review schema or post_id")
            )
        return findings
