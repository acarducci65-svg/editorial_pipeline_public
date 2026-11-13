import runpy
import subprocess
import sys


def test_module_reports_scaffold_status(capsys):
    runpy.run_module("editorial_pipeline.__main__")
    runpy.run_module("editorial_pipeline", run_name="__main__")
    assert "not yet implemented" in capsys.readouterr().out


def test_module_entrypoint_runs():
    result = subprocess.run(
        [sys.executable, "-m", "editorial_pipeline"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "not yet implemented" in result.stdout
