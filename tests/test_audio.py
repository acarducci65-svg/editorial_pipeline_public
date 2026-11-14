import json
import shutil
from pathlib import Path

import pytest

from editorial_pipeline.cli.commands import main
from tests.test_cli import ROOT, _refresh_evidence, _write_gate_receipt
from tests.test_publish import snapshot


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "blog"
    shutil.copytree(ROOT, root)
    config = root / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("F5 = false", "F5 = true"),
        encoding="utf-8",
    )
    _refresh_evidence(root)
    return root


def run(root: Path, *args: str) -> int:
    return main(["build-audio", "post_01", "--config", str(root / "editorial.toml"), *args])


@pytest.mark.parametrize("dry", [False, True])
def test_disabled_f5_never_writes(
    project: Path, dry: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("F5 = true", "F5 = false"),
        encoding="utf-8",
    )
    before = snapshot(project)
    assert run(project, "--json", *(["--dry-run"] if dry else [])) == 1
    assert snapshot(project) == before
    assert "F5" in capsys.readouterr().err


@pytest.mark.parametrize("dry", [False, True])
def test_script_build(project: Path, dry: bool, capsys: pytest.CaptureFixture[str]) -> None:
    before = snapshot(project)
    assert run(project, "--json", *(["--dry-run"] if dry else [])) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == ("DRY_RUN" if dry else "BUILT")
    assert result["provider"] == "script_only"
    assert result["script_file"] == "dist/audio/post_01/podcast_script.md"
    assert result["audio_files"] == []
    assert str(project) not in output
    if dry:
        assert snapshot(project) == before
    else:
        script = (project / result["script_file"]).read_text(encoding="utf-8")
        assert all(word in script for word in ("Intro", "Segment", "Outro", "Licenza"))
        evidence = json.loads((project / "evidence/post_01/factcheck.json").read_text())
        assert all(claim["text"] in script for claim in evidence["claims"])


def test_gate2_binds_audio(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_gate_receipt(project, 1)
    _write_gate_receipt(project, 2)
    assert run(project) == 0
    capsys.readouterr()
    args = ["check-gate", "2", "post_01_valid", "--config", str(project / "editorial.toml")]
    assert main(args) == 2
    _write_gate_receipt(project, 2)
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert "dist/audio/post_01/podcast_script.md" in result["bundle"]["artifacts"]
    with (project / "dist/audio/post_01/podcast_script.md").open("a") as stream:
        stream.write("modified")
    assert main(args) == 2


@pytest.mark.parametrize("dry", [False, True])
def test_notebooklm_build(
    project: Path,
    dry: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import subprocess
    from unittest.mock import Mock

    monkeypatch.setenv("EDITORIAL_AUDIO_ID", "sandbox-corpus")
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which", lambda _: "nlm"
    )
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.time.sleep", lambda _: None)
    statuses = iter(["in_progress", "completed"])

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 60.0
        assert kwargs["cwd"] == project.resolve()
        if args[1:3] == ["audio", "create"]:
            assert args[3] == "sandbox-corpus"
            assert "--confirm" in args and "--json" in args
            return subprocess.CompletedProcess(args, 0, '{"artifact_id": "sandbox-audio"}', "")
        if args[1:3] == ["studio", "status"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    {"artifacts": [{"artifact_id": "sandbox-audio", "status": next(statuses)}]}
                ),
                "",
            )
        assert args[1:3] == ["download", "audio"]
        assert args[args.index("--id") + 1] == "sandbox-audio"
        (project / args[args.index("--output") + 1]).write_bytes(b"fake audio")
        return subprocess.CompletedProcess(args, 0, "private diagnostic", "")

    mocked = Mock(side_effect=execute)
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", mocked)
    before = snapshot(project)
    assert run(project, "--provider", "notebooklm", "--json", *(["--dry-run"] if dry else [])) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == ("DRY_RUN" if dry else "BUILT")
    assert result["audio_files"] == ["dist/audio/post_01/podcast.m4a"]
    assert "sandbox-corpus" not in output and "sandbox-audio" not in output
    assert "private diagnostic" not in output and str(project) not in output
    if dry:
        mocked.assert_not_called()
        assert snapshot(project) == before
    else:
        assert mocked.call_count == 4
        assert (project / result["audio_files"][0]).read_bytes() == b"fake audio"
        assert len(list((project / "dist/audio/post_01").iterdir())) == 1


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "corpus",
        "auth",
        "exit",
        "timeout",
        "os",
        "unicode",
        "json",
        "shape",
        "artifact",
        "status",
        "failed",
        "pending",
        "empty",
    ],
)
def test_notebooklm_errors_are_protected(
    project: Path,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import subprocess
    from unittest.mock import Mock

    from editorial_pipeline.adapters.audio import AudioUnavailableError, NotebookLMAdapter

    private = f"credential=private-value {project} sandbox-corpus"
    monkeypatch.setenv("EDITORIAL_AUDIO_ID", "sandbox-corpus")
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which",
        lambda _: None if failure == "missing" else "nlm",
    )
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.time.sleep", lambda _: None)
    if failure == "corpus":
        monkeypatch.delenv("EDITORIAL_AUDIO_ID")

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if failure in {"auth", "exit"}:
            return subprocess.CompletedProcess(
                args, 1, private, "login " + private if failure == "auth" else private
            )
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 60, output=private, stderr=private)
        if failure == "os":
            raise OSError(private)
        if failure == "unicode":
            raise UnicodeError(private)
        if failure == "json":
            return subprocess.CompletedProcess(args, 0, private, "")
        if failure == "shape":
            return subprocess.CompletedProcess(args, 0, "[]", "")
        if args[1:3] == ["audio", "create"]:
            return subprocess.CompletedProcess(
                args, 0, "{}" if failure == "artifact" else '{"artifact_id": "sandbox-audio"}', ""
            )
        if args[1:3] == ["studio", "status"]:
            response = {"artifacts": [{"artifact_id": "sandbox-audio", "status": "completed"}]}
            if failure == "status":
                response = {"artifacts": []}
            elif failure in {"failed", "pending"}:
                response["artifacts"][0]["status"] = (
                    "failed" if failure == "failed" else "in_progress"
                )
            return subprocess.CompletedProcess(args, 0, json.dumps(response), "")
        return subprocess.CompletedProcess(args, 0, "", "")

    mocked = Mock(side_effect=execute)
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", mocked)
    provider = NotebookLMAdapter(project)
    with pytest.raises(AudioUnavailableError) as exc:
        provider.build("post_01", "Draft", [], project / "dist/audio/post_01")
    assert private not in str(exc.value)
    assert "script_only" in str(exc.value)
    assert run(project, "--provider", "notebooklm") == 1
    output = capsys.readouterr()
    assert private not in output.err and str(project) not in output.err
    assert not output.out
    assert not list((project / "dist").rglob("*.m4a"))
    if failure in {"missing", "corpus"}:
        mocked.assert_not_called()


@pytest.mark.parametrize("entry", ["editorial", "editorial-pipeline"])
def test_both_entrypoints(
    project: Path,
    entry: str,
) -> None:
    import subprocess

    before = snapshot(project)
    result = subprocess.run(
        [
            entry,
            "build-audio",
            "post_01",
            "--config",
            str(project / "editorial.toml"),
            "--dry-run",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "DRY_RUN"
    assert snapshot(project) == before


@pytest.mark.parametrize("mode", ["legacy", "section", "override", "unknown", "absent"])
def test_provider_configuration(
    project: Path,
    mode: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EDITORIAL_AUDIO_ID", raising=False)
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace(
        '[providers.audio]\nadapter = "none"', '[providers.audio]\nadapter = "notebooklm"'
    )
    if mode == "absent":
        text = text.replace('[providers.audio]\nadapter = "notebooklm"', "")
    if mode in {"section", "override"}:
        text += '\n[audio]\nprovider = "script_only"\n'
    if mode == "unknown":
        text = text.replace(
            '[providers.audio]\nadapter = "notebooklm"', '[providers.audio]\nadapter = "unknown"'
        )
    config.write_text(text, encoding="utf-8")
    assert run(
        project,
        "--dry-run",
        "--json",
        *(["--provider", "notebooklm"] if mode == "override" else []),
    ) == (1 if mode == "unknown" else 0)
    output = capsys.readouterr()
    if mode != "unknown":
        assert json.loads(output.out)["provider"] == (
            "notebooklm" if mode in {"legacy", "override"} else "script_only"
        )
    else:
        assert "Unsupported audio provider" in output.err


@pytest.mark.parametrize("problem", ["stale", "missing", "blocked", "mismatch"])
def test_invalid_evidence_never_writes(project: Path, problem: str) -> None:
    factcheck = project / "evidence/post_01/factcheck.json"
    data = json.loads(factcheck.read_text(encoding="utf-8"))
    if problem == "missing":
        factcheck.unlink()
    else:
        if problem == "stale":
            data["draft_digest"] = "stale"
        elif problem == "blocked":
            data["claims"][0]["outcome"] = "unsupported"
        else:
            data["post_id"] = "other"
        factcheck.write_text(json.dumps(data), encoding="utf-8")
    before = snapshot(project)
    assert run(project) == 1
    assert snapshot(project) == before


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_timeout_validation(project: Path, value: float) -> None:
    from pydantic import ValidationError

    from editorial_pipeline.adapters.audio import NotebookLMAdapter
    from editorial_pipeline.config.models import AudioConfig

    with pytest.raises(ValueError, match="timeout"):
        NotebookLMAdapter(project, timeout=value)
    with pytest.raises(ValidationError):
        AudioConfig(timeout_seconds=value)


@pytest.mark.parametrize("post_id", ["..", ".", "../escape", "bad/name", "bad\\name", ""])
def test_invalid_adapter_post_identifiers(project: Path, post_id: str) -> None:
    from editorial_pipeline.adapters.audio import ScriptOnlyAdapter

    before = snapshot(project)
    with pytest.raises(ValueError):
        ScriptOnlyAdapter(project).build(post_id, "Draft", [], project / "dist/audio/post")
    assert snapshot(project) == before


def test_adapter_rejects_external_output(project: Path) -> None:
    from editorial_pipeline.adapters.audio import ScriptOnlyAdapter

    with pytest.raises(ValueError, match="inside"):
        ScriptOnlyAdapter(project).build("post", "", [], project.parent / "outside")


@pytest.mark.parametrize("overlap", ["reports", "nested_reports", "content"])
def test_audio_output_must_be_bound_by_gate2(project: Path, overlap: str) -> None:
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    if overlap == "content":
        text = text.replace('dist = "dist"', 'dist = "content/posts"')
    else:
        reports = "dist/audio" if overlap == "reports" else "dist/audio/post_01/podcast_script.md"
        text = text.replace('reports = "dist/reports"', f'reports = "{reports}"')
    config.write_text(text, encoding="utf-8")
    before = snapshot(project)
    assert run(project) == 1
    assert snapshot(project) == before


def test_script_direct_adapter_fallback_title(project: Path) -> None:
    from editorial_pipeline.adapters.audio import AudioResult, ScriptOnlyAdapter

    result = ScriptOnlyAdapter(project).build("post", "No heading", [], project / "dist/audio/post")
    assert result.script_file is not None
    assert "Podcast: post" in (project / result.script_file).read_text(encoding="utf-8")
    result.audio_files.append("one")
    result.details["one"] = 1
    fresh = AudioResult(status="SKIPPED", provider="script_only")
    assert not fresh.audio_files and not fresh.details


def test_notebooklm_offline_dry_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    monkeypatch.delenv("EDITORIAL_AUDIO_ID", raising=False)
    mocked = Mock(side_effect=AssertionError("dry-run must remain offline"))
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", mocked)
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.shutil.which", mocked)
    before = snapshot(project)
    assert run(project, "--provider", "notebooklm", "--dry-run") == 0
    assert snapshot(project) == before
    mocked.assert_not_called()


def test_filename_input_and_custom_dist(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace('dist = "dist"', 'dist = "output"'),
        encoding="utf-8",
    )
    assert main(["build-audio", "post_01_valid.md", "--config", str(config), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["script_file"] == "output/audio/post_01/podcast_script.md"
    assert (project / result["script_file"]).is_file()


@pytest.mark.parametrize("failure", ["missing", "empty", "error", "status_shape"])
def test_download_failure_preserves_existing_audio(
    project: Path,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    from unittest.mock import Mock

    from editorial_pipeline.adapters.audio import AudioUnavailableError, NotebookLMAdapter

    target = project / "dist/audio/post_01/podcast.m4a"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"previous audio")
    before = snapshot(project)
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which", lambda _: "nlm"
    )

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args[3] == "configured-corpus"
        assert kwargs["timeout"] == 5
        if args[1:3] == ["audio", "create"]:
            return subprocess.CompletedProcess(args, 0, '{"artifact_id": "sandbox-audio"}', "")
        if args[1:3] == ["studio", "status"]:
            response = (
                {}
                if failure == "status_shape"
                else {"artifacts": [{"artifact_id": "sandbox-audio", "status": "completed"}]}
            )
            return subprocess.CompletedProcess(args, 0, json.dumps(response), "")
        if failure == "empty":
            (project / args[args.index("--output") + 1]).write_bytes(b"")
        elif failure == "error":
            (project / args[args.index("--output") + 1]).write_bytes(b"partial")
            return subprocess.CompletedProcess(args, 1, "", "private-value")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.subprocess.run", Mock(side_effect=execute)
    )
    provider = NotebookLMAdapter(project, corpus_id="configured-corpus", timeout=5)
    with pytest.raises(AudioUnavailableError):
        provider.build("post_01", "Draft", [], target.parent)
    assert snapshot(project) == before


def test_audio_section_passes_runtime_options(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import patch

    from editorial_pipeline.adapters.audio import AudioResult

    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + '\n[audio]\nprovider = "notebooklm"\ncorpus_id_env = "TEST_AUDIO_CORPUS"\ntimeout_seconds = 12\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_AUDIO_CORPUS", "configured-corpus")
    with patch("editorial_pipeline.cli.commands.NotebookLMAdapter") as adapter:
        adapter.return_value.build.return_value = AudioResult(
            status="DRY_RUN",
            provider="notebooklm",
            audio_files=["dist/audio/post_01/podcast.m4a"],
        )
        assert run(project, "--dry-run") == 0
    adapter.assert_called_once_with(project.resolve(), None, "TEST_AUDIO_CORPUS", 12.0)
    passed_sources = adapter.return_value.build.call_args.args[2]
    assert len(passed_sources) == 2
    assert sum(len(source["claims"]) for source in passed_sources) == 3


def test_audio_symlink_escape_is_rejected(project: Path) -> None:
    from editorial_pipeline.adapters.audio import ScriptOnlyAdapter

    destination = project / "dist/audio"
    destination.parent.mkdir(exist_ok=True)
    try:
        destination.symlink_to(project / "content", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require elevated permissions on Windows")
    before = snapshot(project)
    with pytest.raises(ValueError, match="symlinks"):
        ScriptOnlyAdapter(project).build("post", "", [], destination / "post")
    assert snapshot(project) == before
