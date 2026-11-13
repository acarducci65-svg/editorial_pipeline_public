import runpy
import subprocess
import sys

import pytest


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
