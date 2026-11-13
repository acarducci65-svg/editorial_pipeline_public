"""Style register model (``templates/registers/*.yaml``).

A register declares, per de-aizing checklist rule, the expressions and regular
expressions a draft must not contain. The model is deliberately tolerant of
extra descriptive keys (``allowed_uses``, ``rule``, ``source_protection``...)
because those are guidance for human reviewers, not machine checks.
"""

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CLI_KEYS: tuple[str, ...] = (
    "empty_emphasis",
    "negative_parallelism",
    "isolated_lines",
    "vague_attribution",
    "decorative_bold",
    "invented_autobiography",
)
"""The six machine-checkable checklist keys (see docs/humanizer_guide.md, section 3)."""

RULE_TO_CLI_KEY: dict[str, str] = {key: key for key in CLI_KEYS} | {
    "chatbot_tics": "empty_emphasis",
}


def _compile(pattern: str) -> str:
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        raise ValueError(f"invalid regular expression {pattern!r}: {error}") from error
    return pattern


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ForbiddenExpression(_Closed):
    text: str = Field(min_length=1)
    suggestion: str = ""


class ForbiddenPattern(_Closed):
    pattern: str = Field(min_length=1)
    suggestion: str = ""

    _check = field_validator("pattern")(_compile)


class HumanizerRule(_Open):
    """One checklist rule. Only the fields below are evaluated by the linter."""

    forbidden_expressions: tuple[ForbiddenExpression, ...] = ()
    forbidden_patterns: tuple[ForbiddenPattern, ...] = ()
    detection_patterns: tuple[str, ...] = ()
    forbidden_closers: tuple[str, ...] = ()
    spy_verbs_first_person_present: tuple[str, ...] = ()
    max_per_80_words: float | None = None

    @field_validator("detection_patterns")
    @classmethod
    def _check_detection(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_compile(item) for item in value)


class RegisterSpecificRule(_Open):
    id: str
    rule: str
    evidence: str = ""


class RegisterInfo(_Open):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    language: str
    description: str = ""


class ContentSpecs(_Open):
    forbidden_placeholders: tuple[str, ...] = ()


class ReviewMetric(_Closed):
    metric: str
    threshold: float
    severity: Literal["error", "warning"]


class StyleRegister(_Open):
    schema_version: Literal[1]
    info: RegisterInfo = Field(alias="register")
    content_specs: ContentSpecs = ContentSpecs()
    humanizer_rules: dict[str, HumanizerRule]
    register_specific: tuple[RegisterSpecificRule, ...] = ()
    review_metrics: tuple[ReviewMetric, ...] = ()
    checklist_mapping: dict[str, str] = {}

    @model_validator(mode="before")
    @classmethod
    def _split_register_specific(cls, data: Any) -> Any:
        """``register_specific`` is a list nested among the rule mappings: lift it out."""
        if isinstance(data, dict) and isinstance(data.get("humanizer_rules"), dict):
            rules = dict(data["humanizer_rules"])
            specific = rules.pop("register_specific", None)
            data = {**data, "humanizer_rules": rules}
            if specific is not None:
                data["register_specific"] = specific
        return data

    @property
    def id(self) -> str:
        return self.info.id

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def forbidden_expressions(self) -> tuple[tuple[str, ForbiddenExpression], ...]:
        """All forbidden expressions as ``(rule_key, expression)`` pairs."""
        return tuple(
            (key, item)
            for key, rule in self.humanizer_rules.items()
            for item in rule.forbidden_expressions
        )

    @property
    def forbidden_patterns(self) -> tuple[tuple[str, ForbiddenPattern], ...]:
        """All forbidden regular expressions as ``(rule_key, pattern)`` pairs."""
        return tuple(
            (key, item)
            for key, rule in self.humanizer_rules.items()
            for item in rule.forbidden_patterns
        )

    def metric_severity(self, metric: str) -> Literal["error", "warning"] | None:
        for item in self.review_metrics:
            if item.metric == metric:
                return item.severity
        return None


def load_register(path: Path | str) -> StyleRegister:
    """Load and validate a register YAML file; ``register.id`` must match the file name."""
    source = Path(path)
    with source.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise TypeError(f"register file {source.name} is not a mapping")
    register = StyleRegister.model_validate(data)
    if register.id != source.stem:
        raise ValueError(f"register id {register.id!r} does not match file name {source.name!r}")
    return register
