"""Optional NotebookLM fact checking through the nlm CLI."""

import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

from editorial_pipeline.adapters.rag.base import RagProvider, RagUnavailableError
from editorial_pipeline.domain.models import Finding, VerificationState

USAGE_LIMIT_MESSAGE = (
    "NotebookLM RAG: usage limit reached. Wait before retrying or use --provider manual."
)
_RATE_LIMIT_MARKERS = (
    "usage limit",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "too many requests",
    "quota",
    "resource_exhausted",
    "429",
)


def _is_rate_limited(*texts: str) -> bool:
    return any(marker in text.casefold() for text in texts for marker in _RATE_LIMIT_MARKERS)


def _json_error_text(output: str) -> str | None:
    """Return the error text of an nlm JSON error payload, or None if it is not one."""
    try:
        payload = json.loads(output)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if not (isinstance(status, str) and status.casefold() == "error") and "error" not in payload:
        return None
    parts = [payload.get(key) for key in ("error", "detail", "message", "status")]
    return " ".join(json.dumps(part) if not isinstance(part, str) else part for part in parts)


class NotebookLMAdapter(RagProvider):
    def __init__(
        self,
        corpus_id: str | None = None,
        corpus_id_env: str = "EDITORIAL_RAG_ID",
        timeout: float = 60.0,
        cli_path: str = "nlm",
        max_claims_per_turn: int = 8,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("NotebookLM timeout must be finite and positive")
        if max_claims_per_turn <= 0:
            raise ValueError("NotebookLM max_claims_per_turn must be positive")
        self._corpus_id = corpus_id
        self._corpus_id_env = corpus_id_env
        self._timeout = timeout
        self._cli_path = cli_path
        self._max_claims_per_turn = max_claims_per_turn

    def capabilities(self) -> set[str]:
        return {"fact_check"}

    def verify(self, claims: list[str], evidence_path: Path) -> list[Finding]:
        if len(claims) > self._max_claims_per_turn:
            raise RagUnavailableError(
                f"RAG claims count ({len(claims)}) exceeds maximum allowed per turn "
                f"({self._max_claims_per_turn}). Reduce claims to key factual assertions "
                "or configure max_claims_per_turn."
            )
        if not claims:
            return []
        corpus = self._corpus_id or os.environ.get(self._corpus_id_env)
        if not corpus or not corpus.strip():
            raise RagUnavailableError("RAG corpus is not configured")
        if shutil.which(self._cli_path) is None:
            raise RagUnavailableError("NotebookLM CLI ('nlm') is unavailable")
        findings = []
        for index, claim in enumerate(claims, 1):
            if index > 1:
                time.sleep(0.5)
            question = f"Verifica se la seguente affermazione e' supportata dalle fonti: '{claim}'"
            args = [
                self._cli_path,
                "query",
                "notebook",
                corpus,
                question,
                "--json",
                "--timeout",
                str(self._timeout),
                "--new-conversation",
            ]
            try:
                result = subprocess.run(
                    args,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self._timeout + 10,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                raise RagUnavailableError(
                    f"NotebookLM query timed out after {self._timeout}s"
                ) from None
            except OSError:
                raise RagUnavailableError("NotebookLM CLI could not be executed") from None
            except UnicodeError:
                raise RagUnavailableError("NotebookLM returned an invalid text response") from None
            if result.returncode != 0:
                # Abort the whole batch: further queries would only burn more quota.
                if _is_rate_limited(result.stderr, result.stdout):
                    raise RagUnavailableError(USAGE_LIMIT_MESSAGE)
                if any(word in result.stderr.casefold() for word in ("login", "auth", "cookie")):
                    raise RagUnavailableError(
                        "NotebookLM authentication required (run 'nlm login')"
                    )
                # stderr may contain credentials, corpus IDs and host paths. Discard it.
                raise RagUnavailableError(
                    f"NotebookLM query failed: CLI exit code {result.returncode}"
                )
            error_text = _json_error_text(result.stdout)
            if error_text is not None:
                if _is_rate_limited(error_text):
                    raise RagUnavailableError(USAGE_LIMIT_MESSAGE)
                # The error payload may echo corpus IDs or host paths. Discard it.
                raise RagUnavailableError("NotebookLM query failed: CLI reported an error")
            findings.append(self._finding(result.stdout, index))
        return findings

    @staticmethod
    def _finding(output: str, index: int) -> Finding:
        try:
            payload = json.loads(output)
        except ValueError:
            raise RagUnavailableError("NotebookLM returned an invalid JSON response") from None
        if not isinstance(payload, dict):
            raise RagUnavailableError("NotebookLM returned an invalid JSON response")
        answer = payload.get("answer", payload.get("text", payload.get("content")))
        citations = payload.get("citations", payload.get("sources"))
        if isinstance(citations, dict):
            # nlm >= 0.15 maps citation numbers to source identifiers.
            citations = list(citations.values())
        if not isinstance(answer, str) or (
            citations is not None and not isinstance(citations, list)
        ):
            raise RagUnavailableError("NotebookLM returned an invalid JSON response")
        normalized = answer.casefold()
        negative = (
            "not supported",
            "unsupported",
            "no evidence",
            "not enough information",
            "cannot verify",
            "insufficient evidence",
            "contradict",
            "non supportat",
            "non e supportat",
            "non è supportat",
            "nessuna evidenza",
            "non ci sono prove",
        )
        uncertain = ("partial", "uncertain", "inconclusive", "parzial", "incert", "may be")
        if not citations or not any(citations) or any(phrase in normalized for phrase in negative):
            state, reason = VerificationState.BLOCK, "not supported by notebook sources"
        elif not answer.strip() or any(phrase in normalized for phrase in uncertain):
            state, reason = VerificationState.WARN, "requires review of notebook evidence"
        else:
            state, reason = VerificationState.OK, "supported by notebook sources"
        # Do not copy untrusted model output or potentially private claims into reports.
        return Finding("rag.claim", f"Claim {index}: {reason}", state)
