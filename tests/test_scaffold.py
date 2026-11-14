import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from editorial_pipeline.cli.commands import main


def test_install_skill_packaged_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "package"
    skill = package / "_skills/editorial-pipeline"
    (skill / "references/nested").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"packaged skill")
    (skill / "references/nested/guide.md").write_bytes(b"packaged guide")
    monkeypatch.setattr("editorial_pipeline.cli.commands.resources.files", lambda _: package)
    target = tmp_path / "agent"
    assert main(["install-skill", str(target)]) == 0
    assert (target / "editorial-pipeline/SKILL.md").read_bytes() == b"packaged skill"
    assert (
        target / "editorial-pipeline/references/nested/guide.md"
    ).read_bytes() == b"packaged guide"


def test_install_skill_missing_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("editorial_pipeline.cli.commands.resources.files", lambda _: tmp_path)
    monkeypatch.setattr(
        "editorial_pipeline.cli.commands.__file__", str(tmp_path / "src/pkg/cli/commands.py")
    )
    target = tmp_path / "agent"
    assert main(["install-skill", str(target)]) == 1
    assert not target.exists()
    assert str(tmp_path) not in capsys.readouterr().err


def test_module_reports_help(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["editorial_pipeline", "--help"])
    for module in ("editorial_pipeline.__main__", "editorial_pipeline"):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module(module, run_name="__main__")
        assert exc.value.code == 0
        assert "usage:" in capsys.readouterr().out


def test_module_entrypoint_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "editorial_pipeline", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
