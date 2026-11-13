import json
import re
from pathlib import Path

import pytest
import yaml

from editorial_pipeline.application import StyleChecker, aggregate_state
from editorial_pipeline.config import EditorialConfig, load_config
from editorial_pipeline.domain import VerificationState

ROOT = Path("examples/sample_blog")
POSTS = ROOT / "content" / "posts"


@pytest.fixture(scope="module")
def config() -> EditorialConfig:
    return load_config(ROOT / "editorial.toml")


@pytest.fixture(scope="module")
def checker(config: EditorialConfig) -> StyleChecker:
    return StyleChecker.from_config(config, ROOT)


def test_config_is_operative(config: EditorialConfig) -> None:
    config.validate_operative()
    assert config.register.active == "tech_blog"
    assert config.gates.gate1.required and config.gates.gate2.required
    assert config.project.base_url.endswith("example.org")


def test_resolved_paths_stay_inside_sandbox(config: EditorialConfig) -> None:
    root = ROOT.resolve()
    paths = config.resolve_paths(ROOT)
    assert all(path.is_relative_to(root) for path in paths.values())
    for key in (
        "paths.content",
        "paths.evidence",
        "paths.corrections",
        "author.profile",
        "manifesto.file",
        "register.directory",
        "transparency.templates.method",
        "transparency.templates.corrections",
        "transparency.templates.press",
    ):
        assert paths[key].exists(), key


def test_sandbox_templates_match_framework() -> None:
    pairs = [(ROOT / "templates/registers/tech_blog.yaml", Path("templates/registers"))]
    pairs += [(page, Path("templates/pages")) for page in (ROOT / "templates/pages").glob("*.md")]
    assert len(pairs) == 4
    for copy, origin in pairs:
        assert copy.read_bytes() == (origin / copy.name).read_bytes(), copy.name


def test_profile_and_manifest_are_filled() -> None:
    for name in ("author_profile.yaml", "editorial_manifest.yaml"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "{{" not in text, name
        assert isinstance(yaml.safe_load(text), dict)
    profile = yaml.safe_load((ROOT / "author_profile.yaml").read_text(encoding="utf-8"))
    assert "fittizi" in profile["credentials"]["display"]
    manifest = yaml.safe_load((ROOT / "editorial_manifest.yaml").read_text(encoding="utf-8"))
    core = {p["id"] for p in manifest["transparency_principles"] if p["core"]}
    assert core == {"TP1", "TP2", "TP3", "TP4", "TP5", "TP6"}


def test_valid_post_is_ok(checker: StyleChecker) -> None:
    findings = checker.scan_file(POSTS / "post_01_valid.md")
    assert findings == ()
    assert aggregate_state(findings) is VerificationState.OK


def test_post_with_cliches_is_blocked(checker: StyleChecker) -> None:
    findings = checker.scan_file(POSTS / "post_02_with_cliches.md")
    assert aggregate_state(findings) is VerificationState.BLOCK
    codes = {f.code for f in findings}
    assert codes >= {
        "style.empty_emphasis.forbidden_expression",
        "style.empty_emphasis.forbidden_pattern",
        "style.vague_attribution.forbidden_expression",
        "style.extra_forbidden.forbidden_expression",
        "style.content_specs.placeholder",
        "style.negative_parallelism.detection_pattern",
        "style.isolated_lines.isolated_closer",
        "style.invented_autobiography.first_person_memory",
        "style.decorative_bold.density",
    }
    assert {f.state for f in findings} == {VerificationState.WARN, VerificationState.BLOCK}
    messages = " ".join(f.message for f in findings).casefold()
    for phrase in (
        "nel panorama in continua evoluzione",
        "è fondamentale sottolineare",
        "non è la tecnologia, ma le persone",
    ):
        assert phrase in messages


def test_evidence_matches_posts() -> None:
    for post in sorted(POSTS.glob("*.md")):
        post_id = post.stem[:7]
        for name in ("sources.json", "factcheck.json"):
            data = json.loads((ROOT / "evidence" / post_id / name).read_text(encoding="utf-8"))
            assert data["post_id"] == post_id and data["sandbox"] is True
    factcheck = json.loads((ROOT / "evidence/post_02/factcheck.json").read_text(encoding="utf-8"))
    assert {c["outcome"] for c in factcheck["claims"]} == {"unsupported"}


_LEAK_PATTERNS = {
    "absolute_windows_path": re.compile(r"\b[A-Za-z]:[\\/]"),
    "absolute_posix_home": re.compile(r"/(?:home|Users)/"),
    "cloud_identifier": re.compile(r"notebook_id|conversation_id", re.IGNORECASE),
    "thesis_reference": re.compile(r"\btesi\b", re.IGNORECASE),
}
_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")


def test_zero_leak() -> None:
    files = [p for p in ROOT.rglob("*") if p.is_file()]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        for name, pattern in _LEAK_PATTERNS.items():
            assert not pattern.search(text), (name, path.name)
        for domain in _EMAIL.findall(text):
            assert domain in {"example.org", "blog.example.org", "example.com"}, path.name
