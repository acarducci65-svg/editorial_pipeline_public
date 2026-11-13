import json
import subprocess
import sys
from pathlib import Path

import pytest

from editorial_pipeline.cli.commands import main
from editorial_pipeline.cli.reports import digest

CONFIG = "examples/sample_blog/editorial.toml"
ROOT = Path("examples/sample_blog")


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


def test_gate_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    post = ROOT / "content/posts/post_01_valid.md"
    for token in (None, "", "wrong"):
        args = ["check-gate", "1", post.name, "--config", CONFIG]
        if token is not None:
            args += ["--token", token]
        assert main(args) == 2
        assert capsys.readouterr().err


def test_gate_emits_approval_receipt(capsys: pytest.CaptureFixture[str]) -> None:
    post = ROOT / "content/posts/post_01_valid.md"
    token = digest(post, ROOT)
    assert main(["check-gate", "1", post.name, "--config", CONFIG, "--token", token]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["gate"] == 1
    assert receipt["post"] == "content/posts/post_01_valid.md"
    assert receipt["status"] == "APPROVED"
    assert receipt["author"] == "human"
    assert receipt["timestamp"]
    assert receipt["token"] == token


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
    posix = "/" + "private/file"
    output = serialize({"finding": f"{windows} and {posix}"})
    assert windows not in output
    assert posix not in output
    assert json.loads(output)["finding"] == "[redacted] and [redacted]"


def test_cli_verify_facts_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify-facts", "post_01_valid", "--config", CONFIG, "--json"]) == 0
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


def test_cli_build_visual(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import shutil

    project = tmp_path / "blog"
    shutil.copytree(ROOT, project)
    assert (
        main(
            [
                "build-visual",
                "post_01_valid",
                "--config",
                str(project / "editorial.toml"),
                "--dry-run",
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
    draft.write_text(
        draft.read_text(encoding="utf-8") + "\nA literal statement in the draft.\n",
        encoding="utf-8",
    )
    evidence.write_text(json.dumps(data), encoding="utf-8")
    assert main(["verify-facts", draft.name, "--config", str(project / "editorial.toml")]) == 0
    findings = json.loads(capsys.readouterr().out)["findings"]
    warnings = [item for item in findings if item["code"] == "rag.claim_not_in_draft"]
    assert len(warnings) == 2
    assert all(item["state"] == "WARN" for item in warnings)
