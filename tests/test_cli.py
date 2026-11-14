import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from editorial_pipeline import __version__
from editorial_pipeline.cli.commands import _carousel, _post, main
from editorial_pipeline.cli.reports import _sanitize, digest, serialize
from editorial_pipeline.config import load_config

CONFIG = "examples/sample_blog/editorial.toml"
ROOT = Path("examples/sample_blog")


def test_install_skill_copies_source_from_any_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Path("skills/editorial-pipeline").resolve()
    monkeypatch.chdir(tmp_path)
    assert main(["install-skill", "agent/skills"]) == 0
    target = tmp_path / "agent/skills/editorial-pipeline"
    for file in source.rglob("*"):
        if file.is_file():
            assert (target / file.relative_to(source)).read_bytes() == file.read_bytes()
    assert "activate" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("force", [False, True])
def test_install_skill_existing_destination(tmp_path: Path, force: bool) -> None:
    target = tmp_path / "editorial-pipeline"
    (target / "references").mkdir(parents=True)
    skill = target / "SKILL.md"
    reference = target / "references/gates_and_evidence.md"
    skill.write_bytes(b"original skill")
    reference.write_bytes(b"original reference")
    assert main(["install-skill", str(tmp_path)] + (["--force"] if force else [])) == (
        0 if force else 1
    )
    if force:
        source = Path("skills/editorial-pipeline")
        assert skill.read_bytes() == (source / "SKILL.md").read_bytes()
        assert reference.read_bytes() == (source / "references/gates_and_evidence.md").read_bytes()
    else:
        assert skill.read_bytes() == b"original skill"
        assert reference.read_bytes() == b"original reference"


@pytest.mark.parametrize("flag", ["--version", "-v"])
def test_version(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([flag])
    assert exc.value.code == 0
    output = capsys.readouterr()
    assert output.out.strip() == f"editorial-pipeline {__version__}"
    assert not output.err


def test_streams_without_reconfigure(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in stdout.getvalue()


def test_utf8_output_and_errors_on_pipes(tmp_path: Path) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(
        '"é" = 1\n' + text.replace("schema_version = 1", 'schema_version = "bad"'),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "ascii:strict"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "editorial_pipeline",
            "validate-draft",
            "post_02_with_cliches.md",
            "--config",
            CONFIG,
        ],
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 1
    assert "«" in result.stdout.decode("utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "editorial_pipeline", "status", "--config", str(config)],
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 1
    assert "schema_version" in result.stderr.decode("utf-8")
    assert "é" in result.stderr.decode("utf-8")
    assert str(tmp_path).encode() not in result.stderr


@pytest.mark.parametrize(
    "route",
    [
        "/metodo/",
        "/correzioni/",
        "/per-chi-scrive/",
        "https://example.org/" + "home/page",
        "content/posts/a.md",
    ],
)
def test_sanitize_preserves_routes(route: str) -> None:
    assert _sanitize(route) == route
    assert json.loads(serialize({route: [route]})) == {route: [route]}


@pytest.mark.parametrize(
    "path",
    [
        "C:" + chr(92) + "fixture" + chr(92) + "draft.md",
        "D:" + "/fixture/draft.md",
        chr(92) * 2 + "server" + chr(92) + "share" + chr(92) + "draft.md",
        "/" + "home/fixture/draft.md",
        "/" + "Users/fixture/draft.md",
        "/tmp/fixture/draft.md",
    ],
)
def test_sanitize_masks_filesystem_paths(path: str) -> None:
    assert _sanitize(path) == "[redacted]"
    assert _sanitize(f"Invalid value: {path}") == "Invalid value: [redacted]"


@pytest.mark.parametrize("case", ["validation", "placeholder", "register", "register_validation"])
def test_clean_configuration_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    if case == "validation":
        text = text.replace("schema_version = 1", 'schema_version = "bad"')
        expected = ["schema_version", "Input should be 1"]
    elif case == "placeholder":
        text = text.replace('name = "Appunti di Bottega Digitale"', 'name = "{{PROJECT_NAME}}"')
        expected = ["project.name", "PROJECT_NAME"]
    else:
        register = project / "templates/registers/tech_blog.yaml"
        register.write_text(
            "- invalid\n" if case == "register" else "schema_version: 2\n", encoding="utf-8"
        )
        expected = (
            ["Register YAML must be a mapping"]
            if case == "register"
            else ["schema_version", "Input should be 1", "register", "Field required"]
        )
    config.write_text(text, encoding="utf-8")
    assert main(["status", "--config", str(config)]) == 1
    output = capsys.readouterr()
    assert all(item in output.err for item in expected)
    assert not output.out
    assert "Traceback" not in output.err
    assert "input_value" not in output.err
    assert str(tmp_path) not in output.err


def test_digest_normalizes_line_endings_and_versions_hash(tmp_path: Path) -> None:
    post = tmp_path / "draft.md"
    post.write_bytes(b"Title\n\nBody\n")
    lf_digest = digest(post, tmp_path)
    post.write_bytes(b"Title\r\n\r\nBody\r\n")
    assert digest(post, tmp_path) == lf_digest
    assert re.fullmatch(r"v1:[0-9a-f]{64}", lf_digest)
    post.write_bytes(b"Title\n\nChanged body\n")
    assert digest(post, tmp_path) != lf_digest
    other = tmp_path / "other.md"
    other.write_bytes(b"Title\n\nBody\n")
    assert digest(other, tmp_path) != lf_digest


@pytest.mark.parametrize("duplicate_name", ["post_01_valid.md", "post_01_other.md"])
@pytest.mark.parametrize(
    "command",
    ["status", "validate-all", "validate-draft", "check-gate", "verify-facts", "build-visual"],
)
def test_post_id_collision_blocks_commands_without_side_effects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, duplicate_name: str
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    nested = project / "content/posts/nested"
    nested.mkdir()
    (nested / duplicate_name).write_text("Duplicate post", encoding="utf-8")
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    args = [command]
    if command == "check-gate":
        args += ["1"]
    if command not in ("status", "validate-all"):
        args += ["post_01_valid.md"]
    args += ["--config", str(project / "editorial.toml")]
    assert main(args) == 1
    output = capsys.readouterr()
    assert "collision" in output.err.lower()
    assert not output.out
    assert str(tmp_path) not in output.err
    after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert after == before


def test_post_resolution_raises_on_duplicate_id(tmp_path: Path) -> None:
    posts = tmp_path / "posts"
    posts.mkdir()
    (posts / "post_01_first.md").touch()
    (posts / "post_01_second.md").touch()
    with pytest.raises(ValueError, match="post_id collision"):
        _post("post_01_first.md", tmp_path, posts)


def test_valid_draft(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-draft", "post_01_valid.md", "--config", CONFIG, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["posts"][0]["state"] == "OK"
    assert data["posts"][0]["rel_path"] == "content/posts/post_01_valid.md"


def test_invalid_draft(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-draft", "post_02_with_cliches.md", "--config", CONFIG]) == 1
    assert "style.empty_emphasis" in capsys.readouterr().out


def test_status_and_all(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "--config", CONFIG]) == 1
    assert len(json.loads(capsys.readouterr().out)["posts"]) == 2
    assert main(["validate-all", "--config", CONFIG, "--json"]) == 1
    assert len(json.loads(capsys.readouterr().out)["posts"]) == 2


def _without_receipts(tmp_path: Path) -> str:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    shutil.rmtree(project / "evidence/post_01/approvals")
    return str(project / "editorial.toml")


def test_gate_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    post = ROOT / "content/posts/post_01_valid.md"
    config = _without_receipts(tmp_path)
    for token in (None, "", "wrong"):
        args = ["check-gate", "1", post.name, "--config", config]
        if token is not None:
            args += ["--token", token]
        assert main(args) == 2
        assert capsys.readouterr().err


def test_gate_token_cannot_replace_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    post = ROOT / "content/posts/post_01_valid.md"
    token = digest(post, ROOT)
    config = _without_receipts(tmp_path)
    assert main(["check-gate", "1", post.name, "--config", config, "--token", token]) == 2
    assert capsys.readouterr().err


def test_init_and_missing_project(tmp_path: Path) -> None:
    target = tmp_path / "project"
    assert main(["init", str(target)]) == 0
    assert (target / "editorial.toml").is_file()
    assert (target / "content/posts").is_dir()
    assert (target / "templates/registers/tech_blog.yaml").is_file()
    assert main(["init", str(target)]) == 1
    assert main(["status", "--config", str(tmp_path / "missing")]) == 1


def test_subprocess_report_is_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "editorial_pipeline",
            "validate-draft",
            "post_01_valid.md",
            "--config",
            CONFIG,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert str(ROOT.resolve()) not in result.stdout
    assert json.loads(result.stdout)["posts"][0]["state"] == "OK"


def test_report_redacts_host_paths() -> None:
    from editorial_pipeline.cli.reports import serialize

    windows = "Z:" + chr(92) + "private" + chr(92) + "file"
    posix = "/" + "tmp/fixture/file"
    output = serialize({"finding": f"{windows} and {posix}"})
    assert windows not in output
    assert posix not in output
    assert json.loads(output)["finding"] == "[redacted] and [redacted]"


def _refresh_evidence(project: Path) -> None:
    from editorial_pipeline.config import load_config

    post = project / "content/posts/post_01_valid.md"
    folder = project / "evidence/post_01"
    data = json.loads((folder / "factcheck.json").read_text(encoding="utf-8"))
    data["draft_digest"] = digest(post, project)
    (folder / "factcheck.json").write_text(json.dumps(data), encoding="utf-8")
    config = load_config(project / "editorial.toml")
    review = {
        "post_id": "post_01",
        "draft_digest": data["draft_digest"],
        "items": dict.fromkeys(config.humanizer.required_items, "pass"),
    }
    (folder / "draft-review.json").write_text(json.dumps(review), encoding="utf-8")


def test_cli_verify_facts_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    _refresh_evidence(project)
    assert (
        main(
            ["verify-facts", "post_01_valid", "--config", str(project / "editorial.toml"), "--json"]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    provider_findings = [item for item in report["findings"] if item["code"] == "rag.claim"]
    assert len(provider_findings) == 3
    assert all(item["state"] == "OK" for item in provider_findings)


def test_cli_verify_facts_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import shutil

    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    shutil.rmtree(project / "evidence" / "post_01")
    assert main(["verify-facts", "post_01_valid", "--config", str(project / "editorial.toml")]) == 1
    assert str(tmp_path) not in capsys.readouterr().err


def test_cli_build_visual(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from editorial_pipeline.adapters.visual import playwright_builder

    monkeypatch.setattr(
        playwright_builder,
        "_load_sync_playwright",
        lambda: pytest.fail("HTML-only must not load Playwright"),
    )
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns("dist"))
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("F4_visual = false", "F4_visual = true"),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "build-visual",
                "post_01_valid",
                "--config",
                str(project / "editorial.toml"),
                "--html-only",
                "--aspect-ratio",
                "1:1",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    manifest = json.loads(output)
    assert str(tmp_path) not in output
    assert manifest["digest"]
    assert (project / "dist/social/post_01/manifest.json").is_file()
    assert (project / "dist/social/post_01/slide_01.html").is_file()
    assert {p.suffix for p in (project / "dist").rglob("*") if p.is_file()} == {".html", ".json"}


def test_cli_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for name in (
        "init",
        "status",
        "validate-draft",
        "validate-all",
        "check-gate",
        "verify-facts",
        "build-visual",
    ):
        assert name in output


def test_recursive_discovery_excludes_underscore_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import shutil

    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'content = "content/posts"', 'content = "content"'
        ),
        encoding="utf-8",
    )
    (project / "content/posts/_template.md").write_text("template", encoding="utf-8")
    for command in ("status", "validate-all"):
        assert main([command, "--config", str(config)]) == 1
        paths = [item["rel_path"] for item in json.loads(capsys.readouterr().out)["posts"]]
        assert paths == ["content/posts/post_01_valid.md", "content/posts/post_02_with_cliches.md"]


def test_verify_facts_warns_for_claim_absent_from_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import shutil

    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    draft = project / "content/posts/post_01_valid.md"
    evidence = project / "evidence/post_01/factcheck.json"
    data = json.loads(evidence.read_text(encoding="utf-8"))
    data["claims"][0]["text"] = "A literal statement in the draft."
    data["claims"][1]["text"] = "A statement absent from the draft."
    data["claims"][2]["text"] = "Another statement absent from the draft."
    draft.write_text(
        draft.read_text(encoding="utf-8") + "\nA literal statement in the draft.\n",
        encoding="utf-8",
    )
    evidence.write_text(json.dumps(data), encoding="utf-8")
    _refresh_evidence(project)
    assert main(["verify-facts", draft.name, "--config", str(project / "editorial.toml")]) == 0
    findings = json.loads(capsys.readouterr().out)["findings"]
    warnings = [item for item in findings if item["code"] == "rag.claim_not_in_draft"]
    assert len(warnings) == 2
    assert all(item["state"] == "WARN" for item in warnings)


@pytest.mark.parametrize(
    "adapter,expected", [("manual", 0), ("none", 1), ("notebooklm", 1), ("unknown", 1)]
)
def test_verify_facts_respects_adapter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    adapter: str,
    expected: int,
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    _refresh_evidence(project)
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace(
        '[providers.rag]\nadapter = "local"', f'[providers.rag]\nadapter = "{adapter}"'
    )
    config.write_text(text, encoding="utf-8")
    monkeypatch.delenv("EDITORIAL_RAG_ID", raising=False)
    assert main(["verify-facts", "post_01_valid", "--config", str(config)]) == expected
    output = capsys.readouterr()
    if adapter == "none":
        assert json.loads(output.out)["findings"][0]["code"] == "rag.unavailable"


def test_verify_facts_stale_draft_returns_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    _refresh_evidence(project)
    post = project / "content/posts/post_01_valid.md"
    post.write_text(post.read_text(encoding="utf-8") + "!", encoding="utf-8")
    assert main(["verify-facts", post.name, "--config", str(project / "editorial.toml")]) == 1
    report = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in report["findings"] if f["state"] == "BLOCK"}
    assert {"rag.stale_factcheck", "humanizer.stale_review"} <= codes


def _write_gate_receipt(project: Path, gate: int) -> Path:
    folder = project / "evidence/post_01/approvals"
    folder.mkdir(exist_ok=True)
    bundle: dict[str, Any] = {
        "draft_digest": digest(project / "content/posts/post_01_valid.md", project)
    }
    if gate == 1:
        for key, name in [
            ("sources", "sources"),
            ("factcheck", "factcheck"),
            ("review", "draft-review"),
        ]:
            bundle[f"{key}_digest"] = digest(folder.parent / f"{name}.json", project)
    else:
        bundle["gate1_digest"] = digest(folder / "gate1.json", project)
        paths = load_config(project / "editorial.toml").resolve_paths(project)
        reports = paths.get("paths.reports")
        bundle["artifacts"] = {
            p.relative_to(project).as_posix(): digest(p, project)
            for p in (project / "dist").rglob("*")
            if p.is_file()
            and p.name != ".gitkeep"
            and (reports is None or not p.resolve().is_relative_to(reports))
        }
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "gate": gate,
        "post_id": "post_01",
        "role": "Direttore",
        "decision": "approved",
        "timestamp": "2026-11-14T12:00:00+01:00",
        "excerpt": f"Approvo Gate {gate} #post_01" + ("; publish" if gate == 2 else ""),
        "bundle": bundle,
    }
    if gate == 2:
        receipt["allowed_actions"] = ["publish"]
    path = folder / f"gate{gate}.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


@pytest.fixture
def gate_project(tmp_path: Path) -> Path:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    _refresh_evidence(project)
    kit = project / "dist/social/post_01/kit.txt"
    kit.parent.mkdir(parents=True, exist_ok=True)
    kit.write_text("Promotional kit", encoding="utf-8")
    _write_gate_receipt(project, 1)
    _write_gate_receipt(project, 2)
    return project


@pytest.mark.parametrize("gate", [1, 2])
def test_gate_validates_receipt_without_writing(
    gate_project: Path, capsys: pytest.CaptureFixture[str], gate: int
) -> None:
    before = {p: p.read_bytes() for p in gate_project.rglob("*") if p.is_file()}
    assert (
        main(
            [
                "check-gate",
                str(gate),
                "post_01_valid",
                "--config",
                str(gate_project / "editorial.toml"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == "RECEIPT_VALID"
    assert result["gate"] == gate
    assert result["post_id"] == "post_01"
    assert result["post"] == "content/posts/post_01_valid.md"
    assert "author" not in result and "token" not in result
    assert str(gate_project) not in output
    assert {p: p.read_bytes() for p in gate_project.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("reports_dir", ["dist/reports", "dist/audit"])
@pytest.mark.parametrize("extra", [".gitkeep", "social/post_01/.gitkeep", "report"])
def test_gate2_ignores_placeholders_and_configured_reports(
    gate_project: Path,
    capsys: pytest.CaptureFixture[str],
    reports_dir: str,
    extra: str,
) -> None:
    config = gate_project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace('"dist/reports"', f'"{reports_dir}"'),
        encoding="utf-8",
    )
    ignored = gate_project / (
        f"{reports_dir}/nested/check.json" if extra == "report" else f"dist/{extra}"
    )
    ignored.parent.mkdir(parents=True, exist_ok=True)
    ignored.write_text("Internal bookkeeping", encoding="utf-8")
    assert main(["check-gate", "2", "post_01_valid", "--config", str(config)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "RECEIPT_VALID"
    assert ignored.relative_to(gate_project).as_posix() not in result["bundle"]["artifacts"]


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "invalid_json",
        "decision",
        "role",
        "post_id",
        "timestamp",
        "schema",
        "forbidden",
        "conditional",
        "negated",
        "draft",
        "sources",
        "factcheck",
        "review",
        "style_block",
        "evidence_block",
        "gate2_without_gate1",
        "gate2_stale_gate1",
        "gate2_action",
        "gate2_empty",
        "gate2_unmentioned",
        "gate2_partial_action",
        "gate2_duplicate_action",
        "gate2_draft",
        "gate2_wrong_gate",
        "gate1_wrong_gate",
        "invalid_encoding",
        "sources_changed",
        "factcheck_changed",
        "review_changed",
        "draft_changed",
        "kit_changed",
        "kit_added",
        "kit_removed",
        "kit_empty",
        "gate1_changed",
    ],
)
def test_gate_rejects_invalid_receipts(
    gate_project: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    project = gate_project
    gate = 2 if case.startswith(("gate2", "kit", "gate1_changed")) else 1
    receipt = project / f"evidence/post_01/approvals/gate{gate}.json"
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if case == "missing":
        receipt.unlink()
    elif case == "invalid_json":
        receipt.write_text("{", encoding="utf-8")
    elif case == "invalid_encoding":
        receipt.write_bytes(b"\xff")
    elif case in {"gate1_wrong_gate", "gate2_wrong_gate"}:
        other_gate = 1 if gate == 2 else 2
        receipt.write_bytes((receipt.parent / f"gate{other_gate}.json").read_bytes())
    elif case in {"sources_changed", "factcheck_changed", "review_changed", "draft_changed"}:
        name = {
            "sources_changed": "sources",
            "factcheck_changed": "factcheck",
            "review_changed": "draft-review",
        }.get(case)
        if name is not None:
            changed = project / f"evidence/post_01/{name}.json"
            changed.write_text(changed.read_text(encoding="utf-8") + " ", encoding="utf-8")
        else:
            changed = project / "content/posts/post_01_valid.md"
            changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            _refresh_evidence(project)
    elif case in {"decision", "role", "post_id", "schema", "timestamp"}:
        key, value = {
            "decision": ("decision", "rejected"),
            "role": ("role", "agent"),
            "post_id": ("post_id", "other"),
            "schema": ("schema_version", 2),
            "timestamp": ("timestamp", "2026-11-14T12:00:00"),
        }[case]
        data[key] = value
        receipt.write_text(json.dumps(data), encoding="utf-8")
    elif case in {"forbidden", "conditional", "negated"}:
        data["excerpt"] += {
            "forbidden": " automatically approved",
            "conditional": " solo se il kit passa",
            "negated": " non approvo",
        }[case]
        receipt.write_text(json.dumps(data), encoding="utf-8")
    elif case in {"draft", "sources", "factcheck", "review"}:
        data["bundle"][f"{case}_digest"] = "v1:" + "0" * 64
        receipt.write_text(json.dumps(data), encoding="utf-8")
    elif case == "style_block":
        post = project / "content/posts/post_01_valid.md"
        post.write_text(post.read_text(encoding="utf-8") + "\nTODO\n", encoding="utf-8")
        _refresh_evidence(project)
        _write_gate_receipt(project, 1)
    elif case == "evidence_block":
        (project / "evidence/post_01/sources.json").unlink()
    elif case == "gate2_without_gate1":
        (receipt.parent / "gate1.json").unlink()
    elif case == "gate2_stale_gate1":
        p = project / "evidence/post_01/sources.json"
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    elif case.startswith("gate2"):
        data["allowed_actions"] = (
            [] if case == "gate2_empty" else ["delete" if case == "gate2_action" else "publish"]
        )
        if case == "gate2_unmentioned":
            data["excerpt"] = "Approvo Gate 2 #post_01"
        elif case == "gate2_partial_action":
            data["excerpt"] = "Approvo Gate 2 #post_01; unpublish"
        elif case == "gate2_duplicate_action":
            data["allowed_actions"] = ["publish", "publish"]
        elif case == "gate2_draft":
            data["bundle"]["draft_digest"] = "v1:" + "0" * 64
        receipt.write_text(json.dumps(data), encoding="utf-8")
    elif case == "gate1_changed":
        p = receipt.parent / "gate1.json"
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    else:
        kit = project / "dist/social/post_01/kit.txt"
        if case == "kit_added":
            kit.with_name("extra.txt").write_text("extra", encoding="utf-8")
        elif case in {"kit_removed", "kit_empty"}:
            kit.unlink()
            if case == "kit_empty":
                for artifact in (project / "dist").rglob("*"):
                    if artifact.is_file():
                        artifact.unlink()
                data["bundle"]["artifacts"] = {}
                receipt.write_text(json.dumps(data), encoding="utf-8")
        else:
            kit.write_text("changed", encoding="utf-8")
    assert (
        main(
            ["check-gate", str(gate), "post_01_valid", "--config", str(project / "editorial.toml")]
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.err and not output.out
    assert str(project) not in output.err
    if case == "style_block":
        assert "BLOCK" in output.err and "rag.stale_factcheck" not in output.err
    elif case == "evidence_block":
        assert "BLOCK" in output.err
    elif case in {
        "draft",
        "sources",
        "factcheck",
        "review",
        "sources_changed",
        "factcheck_changed",
        "review_changed",
        "draft_changed",
        "gate2_stale_gate1",
    }:
        assert "stale receipt bundle" in output.err
    elif case in {
        "gate2_action",
        "gate2_unmentioned",
        "gate2_partial_action",
        "gate2_duplicate_action",
    }:
        assert "actions not permitted or absent" in output.err
    elif case in {"forbidden", "conditional", "negated"}:
        assert "unconditional human approval" in output.err


@pytest.mark.parametrize("html_only", [False, True])
@pytest.mark.parametrize("existing", [False, True])
def test_visual_dry_run_preserves_dist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], existing: bool, html_only: bool
) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns("dist"))
    dist = project / "dist"
    if existing:
        dist.mkdir(exist_ok=True)
        (dist / "keep.txt").write_bytes(b"keep")
    dirs = {p.relative_to(project) for p in project.rglob("*") if p.is_dir()}
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("F4_visual = false", "F4_visual = true"),
        encoding="utf-8",
    )
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert (
        main(
            [
                "build-visual",
                "post_01_valid",
                "--dry-run",
                "--config",
                str(project / "editorial.toml"),
            ]
            + (["--html-only"] if html_only else [])
        )
        == 0
    )
    plan = json.loads(capsys.readouterr().out)
    assert plan["dry_run"] is True and plan["files"]
    assert any(f.endswith(".png") for f in plan["files"]) is not html_only
    assert before == {
        p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    assert dirs == {p.relative_to(project) for p in project.rglob("*") if p.is_dir()}


@pytest.mark.parametrize("flag", ["--dry-run", "--html-only", ""])
def test_visual_disabled(tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: str) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns("dist"))
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("F4_visual = true", "F4_visual = false"),
        encoding="utf-8",
    )
    args = ["build-visual", "post_01_valid", "--config", str(config)]
    assert main(args + ([flag] if flag else [])) == 1
    assert "Phase F4_visual is disabled in editorial.toml" in capsys.readouterr().err
    assert not (project / "dist/social").exists()


def test_carousel_code_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    post = tmp_path / "post.md"
    post.write_text(
        "# **Title**\n## [Section](https://example.org) `code`\n"
        "```python\n# commento\n## fake section\n```\n" + "x" * 801,
        encoding="utf-8",
    )
    spec = _carousel(post, "post", "Author", "4:5")
    assert spec.title == "Title"
    assert len(spec.slides) == 1
    assert spec.slides[0].title == "Section code"
    assert "# commento" in spec.slides[0].text
    assert "800" in capsys.readouterr().err


def test_manifest_deprecated_phrase_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    config = project / "editorial.toml"
    from editorial_pipeline.config import load_config

    manifest = project / load_config(config).manifesto.file
    manifest.write_text(
        'deprecated_phrases:\n  - phrase: "promessa impossibile"\n'
        '    replacement: "descrivere i limiti"\n',
        encoding="utf-8",
    )
    post = project / "content/posts/post_01_valid.md"
    post.write_text(
        post.read_text(encoding="utf-8") + "\nPromessa impossibile.\n", encoding="utf-8"
    )
    assert main(["validate-draft", "post_01_valid", "--config", str(config)]) == 1
    assert "style.manifesto.deprecated_phrase" in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        "```python\n# commento\n```\n",
        "~~~~python\n```\n# commento\n~~~~\n",
        "````python\n```\n# commento\n````\n",
    ],
)
def test_carousel_leading_code_and_closing_fence(tmp_path: Path, source: str) -> None:
    post = tmp_path / "post.md"
    post.write_text(source + "## **Real**\nBody", encoding="utf-8")
    spec = _carousel(post, "post", "Author", "4:5")
    assert spec.title == "post"
    assert spec.slides[0].text == source.strip()
    assert spec.slides[1].title == "Real"


def test_carousel_empty_post(tmp_path: Path) -> None:
    post = tmp_path / "post.md"
    post.write_text("", encoding="utf-8")
    spec = _carousel(post, "post", "Author", "4:5")
    assert spec.slides[0].title == "post" and spec.slides[0].text == ""
