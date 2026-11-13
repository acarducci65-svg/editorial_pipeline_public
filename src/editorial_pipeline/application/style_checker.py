"""Deterministic style and de-aizing linter driven by a style register.

The checker never rewrites text and never approves anything: it reports
``Finding`` objects that a human reviewer (or the Gate 1 workflow) acts upon.

Text normalisation follows docs/humanizer_guide.md: YAML frontmatter, code,
URLs and Markdown markup are blanked out (line numbers are preserved),
typographic apostrophes, quotes and spaces are unified, matching is
case-insensitive.
"""

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from editorial_pipeline.config.models import EditorialConfig
from editorial_pipeline.domain.models import Finding, VerificationState
from editorial_pipeline.domain.registers import RULE_TO_CLI_KEY, StyleRegister, load_register

_TYPOGRAPHIC = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "ʼ": "'",
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        " ": " ",
        " ": " ",
        " ": " ",
    }
)
_FRONTMATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_CODE_FENCE = re.compile(r"^([ \t]*)(```|~~~).*?^\1\2[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK_TARGET = re.compile(r"\]\([^)\n]*\)")
_URL = re.compile(r"https?://\S+")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
_MARKUP = re.compile(r"[*_#>\[\]]")
_WORD = re.compile(r"\w+(?:'\w+)*")

_SEVERITY = {"error": VerificationState.BLOCK, "warning": VerificationState.WARN}


def _blank(match: re.Match[str]) -> str:
    """Replace a span with whitespace, keeping its newlines (and so line numbers)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub(_blank, text.replace("\r\n", "\n"), count=1)


def visible_text(text: str) -> str:
    """Drop frontmatter, code, URLs and link targets; keep Markdown markup and line layout."""
    text = strip_frontmatter(text).translate(_TYPOGRAPHIC)
    text = _CODE_FENCE.sub(_blank, text)
    text = _INLINE_CODE.sub(_blank, text)
    text = _LINK_TARGET.sub(lambda m: "]" + _blank(m)[1:], text)
    return _URL.sub(_blank, text)


def normalize(text: str) -> str:
    """Return the visible prose of a Markdown draft, same line layout as the input."""
    return _MARKUP.sub(" ", visible_text(text))


def phrase_regex(phrase: str) -> re.Pattern[str]:
    """Literal, case-insensitive match on word boundaries; any whitespace run matches."""
    words = phrase.translate(_TYPOGRAPHIC).split()
    body = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def aggregate_state(findings: Iterable[Finding]) -> VerificationState:
    """``BLOCK`` if any finding blocks, else ``WARN`` if any warns, else ``OK``."""
    states = {finding.state for finding in findings}
    if VerificationState.BLOCK in states:
        return VerificationState.BLOCK
    if VerificationState.WARN in states:
        return VerificationState.WARN
    return VerificationState.OK


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


class StyleChecker:
    """Scan drafts against one style register plus project-level extra expressions.

    Severity mapping (``review_metrics`` of the register; defaults in brackets):

    - ``forbidden_expressions`` / ``forbidden_patterns``: ``forbidden_expression_count``
      (``vague_attribution_count`` for the ``vague_attribution`` rule) [BLOCK];
    - ``extra_forbidden`` and ``content_specs.forbidden_placeholders``: always BLOCK;
    - ``negative_parallelism.detection_patterns``:
      ``negative_parallelism_per_1000_words`` [WARN], one finding per occurrence;
    - ``isolated_lines.forbidden_closers``: ``isolated_line_count`` [WARN];
    - ``invented_autobiography`` spy verbs: WARN (needs human evidence, never auto-fixed);
    - ``decorative_bold`` density over ``max_per_80_words``: ``bold_per_80_words`` [WARN].
    """

    def __init__(self, register: StyleRegister, extra_forbidden: Sequence[str] = ()) -> None:
        self.register = register
        self.extra_forbidden = tuple(extra_forbidden)

    @classmethod
    def from_path(cls, path: Path | str, extra_forbidden: Sequence[str] = ()) -> "StyleChecker":
        return cls(load_register(path), extra_forbidden)

    @classmethod
    def from_config(cls, config: EditorialConfig, project_root: Path) -> "StyleChecker":
        """Load ``<register.directory>/<register.active>.yaml`` from a project."""
        directory = config.resolve_paths(project_root)["register.directory"]
        return cls.from_path(
            directory / f"{config.register.active}.yaml", config.register.extra_forbidden
        )

    # ------------------------------------------------------------------ helpers

    def _severity(self, metric: str, default: VerificationState) -> VerificationState:
        severity = self.register.metric_severity(metric)
        return default if severity is None else _SEVERITY[severity]

    def _finding(
        self,
        rule_key: str,
        kind: str,
        state: VerificationState,
        line: int,
        matched: str,
        suggestion: str = "",
    ) -> Finding:
        cli_key = RULE_TO_CLI_KEY.get(rule_key, rule_key)
        message = f"[{self.register.id}/{rule_key}] riga {line}: «{matched}»"
        if suggestion:
            message += f" — {suggestion}"
        return Finding(code=f"style.{cli_key}.{kind}", message=message, state=state)

    def _scan_regex(
        self,
        text: str,
        regex: re.Pattern[str],
        rule_key: str,
        kind: str,
        state: VerificationState,
        suggestion: str = "",
    ) -> list[Finding]:
        return [
            self._finding(
                rule_key,
                kind,
                state,
                _line_of(text, match.start()),
                " ".join(match.group(0).split()),
                suggestion,
            )
            for match in regex.finditer(text)
        ]

    # --------------------------------------------------------------------- scan

    def scan_text(self, text: str) -> tuple[Finding, ...]:
        """Return every finding for ``text`` in a stable order (by rule, then position)."""
        raw = strip_frontmatter(text)
        visible = visible_text(text)
        prose = _MARKUP.sub(" ", visible)
        findings: list[Finding] = []

        for rule_key, rule in self.register.humanizer_rules.items():
            metric = (
                "vague_attribution_count"
                if rule_key == "vague_attribution"
                else "forbidden_expression_count"
            )
            state = self._severity(metric, VerificationState.BLOCK)
            for expression in rule.forbidden_expressions:
                findings += self._scan_regex(
                    prose,
                    phrase_regex(expression.text),
                    rule_key,
                    "forbidden_expression",
                    state,
                    expression.suggestion,
                )
            for pattern in rule.forbidden_patterns:
                findings += self._scan_regex(
                    prose,
                    re.compile(pattern.pattern, re.IGNORECASE),
                    rule_key,
                    "forbidden_pattern",
                    state,
                    pattern.suggestion,
                )
            parallelism = self._severity(
                "negative_parallelism_per_1000_words", VerificationState.WARN
            )
            for detection in rule.detection_patterns:
                findings += self._scan_regex(
                    prose,
                    re.compile(detection, re.IGNORECASE),
                    rule_key,
                    "detection_pattern",
                    parallelism,
                    "Strutture binarie: tenere solo se giustificate nella prova testuale.",
                )
            for verb in rule.spy_verbs_first_person_present:
                findings += self._scan_regex(
                    prose,
                    phrase_regex(verb),
                    rule_key,
                    "first_person_memory",
                    VerificationState.WARN,
                    "Ricordo in prima persona: serve una fonte in first_person.allowed_sources.",
                )
            findings += self._scan_closers(prose, rule_key, rule.forbidden_closers)
            if rule.max_per_80_words is not None:
                findings += self._scan_bold(raw, rule_key, rule.max_per_80_words)

        for phrase in self.extra_forbidden:
            findings += self._scan_regex(
                prose,
                phrase_regex(phrase),
                "extra_forbidden",
                "forbidden_expression",
                VerificationState.BLOCK,
                "Espressione vietata dal progetto (editorial.toml, register.extra_forbidden).",
            )
        # Placeholders such as "[verificare]" contain markup: match before stripping it.
        for placeholder in self.register.content_specs.forbidden_placeholders:
            findings += self._scan_regex(
                visible,
                phrase_regex(placeholder),
                "content_specs",
                "placeholder",
                VerificationState.BLOCK,
                "Segnaposto da risolvere prima del Gate 1.",
            )
        return tuple(findings)

    def _scan_closers(self, prose: str, rule_key: str, closers: Sequence[str]) -> list[Finding]:
        if not closers:
            return []
        state = self._severity("isolated_line_count", VerificationState.WARN)
        wanted = {closer.strip().casefold() for closer in closers}
        return [
            self._finding(
                rule_key,
                "isolated_closer",
                state,
                number,
                line.strip(),
                "Riga isolata a effetto: integrarla nel periodo o toglierla.",
            )
            for number, line in enumerate(prose.split("\n"), start=1)
            if line.strip().casefold() in wanted
        ]

    def _scan_bold(self, raw: str, rule_key: str, limit: float) -> list[Finding]:
        text = _CODE_FENCE.sub(_blank, raw)
        bold = len(_BOLD.findall(text))
        words = len(_WORD.findall(normalize(raw)))
        if bold == 0 or bold * 80 <= limit * max(words, 1):
            return []
        density = bold * 80 / max(words, 1)
        return [
            Finding(
                code="style.decorative_bold.density",
                message=(
                    f"[{self.register.id}/{rule_key}] {bold} grassetti su {words} parole "
                    f"({density:.2f} ogni 80, massimo {limit:g})."
                ),
                state=self._severity("bold_per_80_words", VerificationState.WARN),
            )
        ]

    def scan_file(self, path: Path | str) -> tuple[Finding, ...]:
        return self.scan_text(Path(path).read_text(encoding="utf-8"))

    def check(self, text: str) -> VerificationState:
        return aggregate_state(self.scan_text(text))
