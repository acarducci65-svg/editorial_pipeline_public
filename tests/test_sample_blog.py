import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from editorial_pipeline.application import StyleChecker, aggregate_state
from editorial_pipeline.cli.commands import main
from editorial_pipeline.cli.reports import digest
from editorial_pipeline.config import EditorialConfig, load_config
from editorial_pipeline.domain import VerificationState
from editorial_pipeline.domain.gates import (
    RECEIPT_ADAPTER,
    Gate1Receipt,
    Gate2Receipt,
    GateReceipt,
)

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


def test_sample_report_uses_versioned_digests(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "--config", str(ROOT / "editorial.toml")]) == 1
    posts = json.loads(capsys.readouterr().out)["posts"]
    assert len(posts) == 2
    assert all(re.fullmatch(r"v1:[0-9a-f]{64}", post["digest"]) for post in posts)


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


CONFIG = str(ROOT / "editorial.toml")


@pytest.mark.parametrize("command", ["validate-draft", "verify-facts"])
def test_valid_post_has_zero_warn_and_block(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command, "post_01_valid.md", "--config", CONFIG]) == 0
    report = json.loads(capsys.readouterr().out)
    findings = report["posts"][0]["findings"] if "posts" in report else report["findings"]
    assert {f["state"] for f in findings} <= {"OK"}


def test_sample_evidence_is_bound_to_current_draft() -> None:
    folder = ROOT / "evidence/post_01"
    current = digest(POSTS / "post_01_valid.md", ROOT)
    factcheck = json.loads((folder / "factcheck.json").read_text(encoding="utf-8"))
    review = json.loads((folder / "draft-review.json").read_text(encoding="utf-8"))
    assert factcheck["draft_digest"] == review["draft_digest"] == current
    assert {c["outcome"] for c in factcheck["claims"]} <= {
        "grounded_primary",
        "verified_external",
    }
    config = load_config(ROOT / "editorial.toml")
    assert review["items"] == dict.fromkeys(config.humanizer.required_items, "pass")
    sources = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    primary = {s["key"] for s in sources["sources"] if s["primary"]}
    grounded = {c["source_key"] for c in factcheck["claims"] if c["outcome"] == "grounded_primary"}
    assert grounded and grounded <= primary


@pytest.mark.parametrize("gate,model", [(1, Gate1Receipt), (2, Gate2Receipt)])
def test_sample_receipts_follow_schema_v1(gate: int, model: type[GateReceipt]) -> None:
    path = ROOT / f"evidence/post_01/approvals/gate{gate}.json"
    receipt = RECEIPT_ADAPTER.validate_json(path.read_text(encoding="utf-8"))
    assert isinstance(receipt, model)
    assert receipt.schema_version == 1 and receipt.post_id == "post_01"


@pytest.mark.parametrize("gate", [1, 2])
def test_sample_receipts_are_valid(gate: int, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-gate", str(gate), "post_01_valid", "--config", CONFIG]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "RECEIPT_VALID" and result["gate"] == gate


def test_edited_draft_invalidates_sample_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    draft = project / "content/posts/post_01_valid.md"
    draft.write_text(draft.read_text(encoding="utf-8") + "\nRiga aggiunta.\n", encoding="utf-8")
    config = str(project / "editorial.toml")
    assert main(["verify-facts", "post_01_valid", "--config", config]) == 1
    codes = {f["code"] for f in json.loads(capsys.readouterr().out)["findings"]}
    assert {"rag.stale_factcheck", "humanizer.stale_review"} <= codes
    assert main(["check-gate", "1", "post_01_valid", "--config", config]) == 2
