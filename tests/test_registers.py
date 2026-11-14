from pathlib import Path

import pytest
from pydantic import ValidationError

from editorial_pipeline.application import StyleChecker, aggregate_state
from editorial_pipeline.application.style_checker import normalize, phrase_regex
from editorial_pipeline.domain import Finding, VerificationState
from editorial_pipeline.domain.registers import (
    CLI_KEYS,
    RULE_TO_CLI_KEY,
    StyleRegister,
    load_register,
)

REGISTERS = Path("templates/registers")
REGISTER_IDS = ("academic_essay", "cultural_newsletter", "investigative", "tech_blog")

CLEAN_TEXT = """---
title: "Nota di prova"
---

# Una nota di prova

Il comando elenca i file della cartella corrente e ne stampa la dimensione.
La documentazione ufficiale descrive le opzioni disponibili nella versione 2.4.
Per ogni opzione riportiamo un esempio e il risultato atteso.
"""


def _minimal(**rules: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "register": {"id": "mini", "name": "Mini", "language": "it"},
        "humanizer_rules": rules,
    }


@pytest.fixture(scope="module")
def registers() -> dict[str, StyleRegister]:
    return {rid: load_register(REGISTERS / f"{rid}.yaml") for rid in REGISTER_IDS}


def test_all_four_registers_parse(registers: dict[str, StyleRegister]) -> None:
    assert sorted(p.stem for p in REGISTERS.glob("*.yaml")) == sorted(REGISTER_IDS)
    for rid, register in registers.items():
        assert register.id == rid
        assert register.name
        assert register.forbidden_expressions
        assert register.forbidden_patterns
        assert register.register_specific
        assert "register_specific" not in register.humanizer_rules
        assert set(CLI_KEYS) <= set(register.humanizer_rules)
        assert register.metric_severity("forbidden_expression_count") == "error"
        assert register.metric_severity("missing_metric") is None
        assert set(register.checklist_mapping.values()) <= set(CLI_KEYS) | {"evidence_path"}


@pytest.mark.parametrize("rid", REGISTER_IDS)
def test_clean_text_is_ok(rid: str) -> None:
    checker = StyleChecker.from_path(REGISTERS / f"{rid}.yaml")
    assert checker.scan_text(CLEAN_TEXT) == ()
    assert checker.check(CLEAN_TEXT) is VerificationState.OK


@pytest.mark.parametrize("rid", REGISTER_IDS)
def test_every_forbidden_expression_blocks(rid: str, registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers[rid])
    for rule_key, expression in registers[rid].forbidden_expressions:
        text = f"Premessa neutra.\n\nIn breve, {expression.text.upper()} e poi altro.\n"
        findings = checker.scan_text(text)
        expected = f"style.{RULE_TO_CLI_KEY.get(rule_key, rule_key)}.forbidden_expression"
        assert any(f.code == expected and f.state is VerificationState.BLOCK for f in findings), (
            rid,
            expression.text,
        )
        assert any("riga 3" in f.message for f in findings)


def test_forbidden_pattern_and_suggestion(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["tech_blog"])
    (finding,) = checker.scan_text("Il parser è estremamente veloce.")
    assert finding.code == "style.empty_emphasis.forbidden_pattern"
    assert finding.state is VerificationState.BLOCK
    assert "estremamente veloce" in finding.message
    assert "Un numero" in finding.message


def test_negative_parallelism_warns(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["investigative"])
    findings = checker.scan_text("Non è un caso che il bilancio sia stato rivisto.")
    assert [f.code for f in findings] == ["style.negative_parallelism.detection_pattern"]
    assert aggregate_state(findings) is VerificationState.WARN


def test_isolated_closer_and_first_person(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["tech_blog"])
    text = "Abbiamo aggiunto la cache.\n\nFatto.\n\nPoi ho scoperto un bug nel parser.\n"
    codes = {f.code: f.state for f in checker.scan_text(text)}
    assert codes == {
        "style.isolated_lines.isolated_closer": VerificationState.WARN,
        "style.invented_autobiography.first_person_memory": VerificationState.WARN,
    }


def test_decorative_bold_density(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["tech_blog"])
    sparse = "Una **avvertenza** in mezzo a molte parole " + "di testo " * 60
    assert checker.scan_text(sparse) == ()
    dense = "**Uno** **due** **tre** parole."
    (finding,) = checker.scan_text(dense)
    assert finding.code == "style.decorative_bold.density"
    assert finding.state is VerificationState.WARN


def test_placeholders_and_extra_forbidden(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["investigative"], extra_forbidden=["a tutto tondo"])
    findings = checker.scan_text("Dato [verificare] e analisi a  tutto\ntondo.")
    assert {f.code for f in findings} == {
        "style.content_specs.placeholder",
        "style.extra_forbidden.forbidden_expression",
    }
    assert aggregate_state(findings) is VerificationState.BLOCK


def test_word_boundaries_and_normalization(registers: dict[str, StyleRegister]) -> None:
    checker = StyleChecker(registers["tech_blog"])
    # Inside a longer word, in code, in URLs and link targets: never a finding.
    text = (
        "Il termine seamlessly non conta.\n"
        "`game changer` in codice inline.\n"
        "```text\nin conclusione\n```\n"
        "Vedi https://example.org/game-changer e [la guida](https://example.org/seamless).\n"
    )
    assert checker.scan_text(text) == ()
    # Typographic apostrophe and non-breaking space are unified.
    (finding,) = checker.scan_text("Un design all’avanguardia per tutti.")
    assert "all'avanguardia" in finding.message


def test_normalize_keeps_line_numbers() -> None:
    text = "---\na: 1\n---\n```py\nx = 1\n```\nTesto **forte** [link](http://x.y)\n"
    result = normalize(text)
    assert result.count("\n") == text.count("\n")
    assert result.splitlines()[6].split() == ["Testo", "forte", "link"]
    assert phrase_regex("game  changer").search("un Game\nChanger qui")


def test_severity_follows_review_metrics() -> None:
    data = _minimal(
        empty_emphasis={"forbidden_expressions": [{"text": "epocale"}]},
        vague_attribution={"forbidden_expressions": [{"text": "si dice che"}]},
    )
    data["review_metrics"] = [
        {"metric": "forbidden_expression_count", "threshold": 0, "severity": "warning"},
    ]
    checker = StyleChecker(StyleRegister.model_validate(data))
    states = {f.code: f.state for f in checker.scan_text("Svolta epocale; si dice che regga.")}
    assert states == {
        "style.empty_emphasis.forbidden_expression": VerificationState.WARN,
        "style.vague_attribution.forbidden_expression": VerificationState.BLOCK,
    }


def test_invalid_registers(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        StyleRegister.model_validate(
            _minimal(empty_emphasis={"forbidden_patterns": [{"pattern": "(unclosed"}]})
        )
    with pytest.raises(ValidationError):
        StyleRegister.model_validate(_minimal(negative_parallelism={"detection_patterns": ["[a-"]}))
    with pytest.raises(ValidationError):
        StyleRegister.model_validate("not a mapping")
    wrong_name = tmp_path / "other.yaml"
    wrong_name.write_text(
        (REGISTERS / "tech_blog.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="does not match"):
        load_register(wrong_name)
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("just text\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Register YAML must be a mapping"):
        load_register(scalar)


@pytest.mark.parametrize("content", ["- item\n", "42\n", "null\n", "", "false\n"])
def test_non_mapping_register_is_controlled(tmp_path: Path, content: str) -> None:
    path = tmp_path / "mini.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="^Register YAML must be a mapping$"):
        load_register(path)


def test_blank_extra_forbidden_does_not_create_findings() -> None:
    checker = StyleChecker(StyleRegister.model_validate(_minimal()), ["", " \t\n", "epocale"])
    assert checker.scan_text("Testo normale.\n\n") == ()
    (finding,) = checker.scan_text("Una svolta epocale.")
    assert finding.code == "style.extra_forbidden.forbidden_expression"
    assert "epocale" in finding.message


def test_aggregate_state() -> None:
    warn = Finding("a", "a", VerificationState.WARN)
    block = Finding("b", "b", VerificationState.BLOCK)
    assert aggregate_state(()) is VerificationState.OK
    assert aggregate_state([warn]) is VerificationState.WARN
    assert aggregate_state([warn, block]) is VerificationState.BLOCK


@pytest.mark.parametrize(
    "metric,rules,text,threshold",
    [
        (
            "forbidden_expression_count",
            {"empty_emphasis": {"forbidden_expressions": [{"text": "epocale"}]}},
            "epocale",
            1,
        ),
        (
            "vague_attribution_count",
            {"vague_attribution": {"forbidden_expressions": [{"text": "si dice"}]}},
            "si dice",
            1,
        ),
        (
            "negative_parallelism_per_1000_words",
            {"negative_parallelism": {"detection_patterns": ["non conta"]}},
            "non conta " + "parola " * 998,
            1,
        ),
        ("isolated_line_count", {"isolated_lines": {"forbidden_closers": ["Fatto."]}}, "Fatto.", 1),
        (
            "bold_per_80_words",
            {"decorative_bold": {"max_per_80_words": 0}},
            "**uno** " + "parola " * 79,
            1,
        ),
        ("code_fence_without_language", {}, "```\n# commento\n```\n", 1),
    ],
)
def test_metric_threshold_boundary(
    metric: str, rules: dict[str, object], text: str, threshold: float
) -> None:
    data = _minimal(**rules)
    data["review_metrics"] = [{"metric": metric, "threshold": threshold, "severity": "error"}]
    assert StyleChecker(StyleRegister.model_validate(data)).scan_text(text) == ()
    data["review_metrics"] = [{"metric": metric, "threshold": threshold / 2, "severity": "error"}]
    findings = StyleChecker(StyleRegister.model_validate(data)).scan_text(text)
    assert findings and all(f.state is VerificationState.BLOCK for f in findings)


def test_code_fence_language_counts_openings_only() -> None:
    data = _minimal()
    data["review_metrics"] = [
        {"metric": "code_fence_without_language", "threshold": 0, "severity": "warning"}
    ]
    checker = StyleChecker(StyleRegister.model_validate(data))
    assert checker.scan_text("```python\n```\n~~~text\n~~~\n") == ()
    findings = checker.scan_text("---\na: ```\n---\n````\n```\n````\n~~~\nx\n~~~\n")
    assert len(findings) == 2
    assert all(f.state is VerificationState.WARN for f in findings)


def test_metric_threshold_aggregates_rules_without_relaxing_project_bans() -> None:
    data = _minimal(
        empty_emphasis={"forbidden_expressions": [{"text": "epocale"}]},
        chatbot_tics={"forbidden_expressions": [{"text": "rivoluzionario"}]},
    )
    data["review_metrics"] = [
        {"metric": "forbidden_expression_count", "threshold": 1, "severity": "warning"}
    ]
    checker = StyleChecker(StyleRegister.model_validate(data), ["vietato"])
    assert checker.scan_text("epocale") == ()
    findings = checker.scan_text("epocale rivoluzionario vietato")
    assert [f.state for f in findings] == [
        VerificationState.WARN,
        VerificationState.WARN,
        VerificationState.BLOCK,
    ]


@pytest.mark.parametrize(
    "manifest_text",
    [
        'deprecated_phrases: ["frase vietata", "  "]\n',
        'deprecated_phrases_en: ["frase vietata"]\n',
        'deprecated_phrases:\n  - phrase: "frase vietata"\n    replacement: "fonte"\n',
    ],
)
def test_manifest_prose_only(tmp_path: Path, manifest_text: str) -> None:
    import shutil

    from editorial_pipeline.config import load_config

    root = tmp_path / "blog"
    shutil.copytree("examples/sample_blog", root)
    config = load_config(root / "editorial.toml")
    (root / config.manifesto.file).write_text(manifest_text, encoding="utf-8")
    checker = StyleChecker.from_config(config, root)
    assert (
        checker.scan_text(
            "---\ntitle: frase vietata\n---\n```text\nfrase vietata\n```\n`frase vietata`"
        )
        == ()
    )
    (finding,) = checker.scan_text("FRASE VIETATA")
    assert finding.code == "style.manifesto.deprecated_phrase"
    assert finding.state is VerificationState.BLOCK


def test_manifest_invalid_mapping_and_missing_file(tmp_path: Path) -> None:
    import shutil

    from editorial_pipeline.config import load_config

    root = tmp_path / "blog"
    shutil.copytree("examples/sample_blog", root)
    config = load_config(root / "editorial.toml")
    path = root / config.manifesto.file
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Manifesto YAML must be a mapping"):
        StyleChecker.from_config(config, root)
    path.unlink()
    assert StyleChecker.from_config(config, root).scan_text("Testo normale.") == ()
