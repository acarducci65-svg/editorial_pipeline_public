"""Offline adapter using the shared evidence validation rules."""

from pathlib import Path

from editorial_pipeline.adapters.rag.base import (
    EvidenceMissingError,
    InvalidEvidenceError,
    RagProvider,
)
from editorial_pipeline.application.evidence_verifier import (
    DEFAULT_POLICY,
    EvidenceError,
    load_records,
    normalize_claim,
    verify_records,
)
from editorial_pipeline.config.models import EditorialConfig
from editorial_pipeline.domain.models import Finding, VerificationState


class LocalRagProvider(RagProvider):
    def __init__(self, config: EditorialConfig | None = None, root: Path | None = None) -> None:
        self.policy = config.factcheck if config is not None else DEFAULT_POLICY
        self.root = root

    def capabilities(self) -> set[str]:
        return {"local_evidence", "fact_check"}

    def verify(self, claims: list[str], evidence_path: Path) -> list[Finding]:
        if any(not (evidence_path / name).is_file() for name in ("sources.json", "factcheck.json")):
            raise EvidenceMissingError("Required evidence file is missing")
        try:
            sources, checks = load_records(evidence_path)
        except EvidenceError as exc:
            raise InvalidEvidenceError("Invalid evidence schema or identifiers") from exc
        findings = verify_records(
            sources, checks, self.root or evidence_path.parent.parent, self.policy
        )
        for index, text in enumerate(claims, 1):
            matches = [c for c in checks.claims if normalize_claim(c.text) == normalize_claim(text)]
            if len(matches) != 1:
                findings.append(
                    Finding(
                        "rag.claim",
                        f"Requested claim {index}: absent or ambiguous recorded claim_id",
                        VerificationState.BLOCK,
                    )
                )
        return findings
