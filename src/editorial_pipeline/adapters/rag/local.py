"""Offline verification against recorded evidence, without semantic inference."""

import json
from pathlib import Path
from typing import Any

from editorial_pipeline.adapters.rag.base import (
    EvidenceMissingError,
    InvalidEvidenceError,
    RagProvider,
)
from editorial_pipeline.domain.models import Finding, VerificationState


def _read(path: Path, field: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceMissingError("Required evidence file is missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidEvidenceError("Cannot read evidence file") from exc
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise InvalidEvidenceError("Invalid evidence structure")
    if not all(isinstance(item, dict) for item in data[field]):
        raise InvalidEvidenceError("Invalid evidence entries")
    return data


class LocalRagProvider(RagProvider):
    def capabilities(self) -> set[str]:
        return {"local_evidence", "fact_check"}

    def verify(self, claims: list[str], evidence_path: Path) -> list[Finding]:
        sources = _read(evidence_path / "sources.json", "sources")
        checks = _read(evidence_path / "factcheck.json", "claims")
        if sources.get("post_id") != checks.get("post_id"):
            raise InvalidEvidenceError("Evidence post identifiers do not match")
        source_keys = {
            s.get("key")
            for s in sources["sources"]
            if isinstance(s.get("key"), str) and s.get("key")
        }
        findings = []
        for claim in claims:
            matches = [c for c in checks["claims"] if c.get("text") == claim]
            state = VerificationState.BLOCK
            if len(matches) == 1:
                check = matches[0]
                outcome = check.get("outcome")
                if (
                    outcome in ("verified", "verified_external", "grounded_primary")
                    and isinstance(check.get("source_key"), str)
                    and check.get("source_key") in source_keys
                    and isinstance(check.get("locator"), str)
                    and check["locator"].strip()
                ):
                    state = VerificationState.OK
                elif outcome == "grounded_secondary":
                    state = VerificationState.WARN
            findings.append(Finding("rag.claim", "Claim evidence: " + state.value, state))
        return findings
