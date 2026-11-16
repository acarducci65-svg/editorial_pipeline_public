import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from editorial_pipeline.cli.commands import main
from editorial_pipeline.config.models import AudioConfig
from tests.test_cli import ROOT, _refresh_evidence, _write_gate_receipt
from tests.test_publish import snapshot

if TYPE_CHECKING:
    from editorial_pipeline.adapters.audio import LocalTtsAudioProvider


def test_notebooklm_import_in_fresh_interpreter() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from editorial_pipeline.adapters.audio.notebooklm import NotebookLMAdapter; print('OK')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def _tts(root: Path, *args: str) -> "LocalTtsAudioProvider":
    """Build the deprecated TTS provider, asserting the deprecation warning."""
    from editorial_pipeline.adapters.audio import LocalTtsAudioProvider

    with pytest.warns(DeprecationWarning, match="NotebookLM Studio is the required"):
        return LocalTtsAudioProvider(root, *args)


def test_tts_cli_dry_run(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before = snapshot(project)
    assert run(project, "--provider", "tts", "--dry-run", "--json") == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "DRY_RUN"
    assert result["audio_files"] == ["dist/audio/post_01/podcast.mp3"]
    assert result["details"]["planned_voice"] == "it-IT-DiegoNeural"
    assert result["details"]["deprecated"] is True
    assert "DEPRECATED provider 'tts'" in captured.err
    assert "sub-standard robotic audio" in captured.err
    assert snapshot(project) == before


@pytest.mark.parametrize("existing_script", [False, True])
def test_tts_synthesizes_narration(
    project: Path, monkeypatch: pytest.MonkeyPatch, existing_script: bool
) -> None:
    output = project / "dist/audio/post_01"
    if existing_script:
        output.mkdir(parents=True)
        (output / "podcast_script.md").write_text(
            "# Podcast: Titolo\nCopione da revisionare prima della registrazione o del TTS.\n"
            "## Intro\n[Speaker] Una **notizia** con [fonte](https://example.com).\n"
            "[Pausa]\nFonte: source-key\nRiferimento: pagina 1\n"
            "<!-- nota privata -->\n[Nota: musica]\nBozza audio: revisione umana richiesta.\n",
            encoding="utf-8",
        )
    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.shutil.which", lambda _: "edge-tts")

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args[:3] == ["edge-tts", "--file", "-"]
        assert "--voice=it-IT-ElsaNeural" in args and "--rate=-10%" in args
        assert kwargs["shell"] is False and kwargs["timeout"] == 300
        assert kwargs["encoding"] == "utf-8"
        text = str(kwargs["input"])
        if existing_script:
            assert text == "Una notizia con fonte."
        else:
            assert "Una bozza." in text and "Evidenza verificata." in text
            assert "**" not in text and "[Speaker]" not in text
        Path(args[args.index("--write-media") + 1]).write_bytes(b"mock mp3")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.subprocess.run", execute)
    result = _tts(project, "it-IT-ElsaNeural", "-10%").build(
        "post_01",
        "# Titolo\nUna **bozza**.",
        [{"key": "source", "claims": [{"text": "Evidenza verificata."}]}],
        output,
    )
    assert result.status == "BUILT" and result.provider == "tts"
    assert result.details == {"voice": "it-IT-ElsaNeural", "deprecated": True}
    assert result.audio_files == ["dist/audio/post_01/podcast.mp3"]
    assert (project / result.audio_files[0]).read_bytes() == b"mock mp3"
    assert sorted(p.name for p in output.iterdir()) == (
        ["podcast.mp3", "podcast_script.md"] if existing_script else ["podcast.mp3"]
    )


@pytest.mark.parametrize("failure", ["missing", "exit", "timeout", "os", "empty", "absent"])
def test_tts_errors_are_safe(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from editorial_pipeline.adapters.audio import AudioUnavailableError

    output = project / "dist/audio/post_01"
    output.mkdir(parents=True)
    audio = output / "podcast.mp3"
    audio.write_bytes(b"previous audio")
    private = f"private diagnostic {project}"
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.tts.shutil.which",
        lambda _: None if failure == "missing" else "edge-tts",
    )

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 300, stderr=private)
        if failure == "os":
            raise OSError(private)
        if failure == "exit":
            raise subprocess.CalledProcessError(1, args, output=private, stderr=private)
        if failure != "absent":
            Path(args[args.index("--write-media") + 1]).write_bytes(b"")
        return subprocess.CompletedProcess(args, 1 if failure == "exit" else 0, private, private)

    mocked = Mock(side_effect=execute)
    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.subprocess.run", mocked)
    with pytest.raises(AudioUnavailableError) as exc:
        _tts(project).build("post_01", "Narration", [], output)
    assert private not in str(exc.value)
    assert audio.read_bytes() == b"previous audio"
    assert [p.name for p in output.iterdir()] == ["podcast.mp3"]
    assert run(project, "--provider", "tts") == 1
    assert private not in capsys.readouterr().err
    if failure == "missing":
        mocked.assert_not_called()


def test_tts_dry_run_does_not_read_or_load_engine(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    before = snapshot(project)
    with monkeypatch.context() as context:
        context.setattr(Path, "read_text", Mock(side_effect=AssertionError("unexpected read")))
        context.setattr(
            "editorial_pipeline.adapters.audio.tts.shutil.which",
            Mock(side_effect=AssertionError("unexpected engine lookup")),
        )
        result = _tts(project).build("post", "Draft", [], project / "dist/audio/post", dry_run=True)
    assert result.status == "DRY_RUN"
    assert snapshot(project) == before


def test_tts_rejects_empty_narration(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.adapters.audio import AudioUnavailableError

    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.shutil.which", lambda _: "edge-tts")
    before = snapshot(project)
    with pytest.raises(AudioUnavailableError, match="non-empty"):
        _tts(project).build("post", "# Heading\n[Pausa]", [], project / "dist/post")
    assert snapshot(project) == before


def test_tts_cli_build(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.shutil.which", lambda _: "edge-tts")

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert "--voice=it-IT-DiegoNeural" in args and "--rate=+0%" in args
        assert kwargs["input"]
        Path(args[args.index("--write-media") + 1]).write_bytes(b"mock mp3")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.subprocess.run", execute)
    assert run(project, "--provider", "tts") == 0
    assert (project / "dist/audio/post_01/podcast.mp3").read_bytes() == b"mock mp3"


def test_tts_cleans_markdown_and_frontmatter(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.shutil.which", lambda _: "edge-tts")

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["input"] == "Primo punto\nSecondo punto\nCitazione"
        Path(args[args.index("--write-media") + 1]).write_bytes(b"mock mp3")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("editorial_pipeline.adapters.audio.tts.subprocess.run", execute)
    _tts(project).build(
        "post",
        "---\ntitle: Metadata\n---\n# Heading\n- Primo *punto*\n"
        "1. Secondo `punto`\n> Citazione\n```\nnota tecnica\n```",
        [],
        project / "dist/post",
    )


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


SAMPLE_FORBIDDEN = (
    "nel panorama in continua evoluzione",
    "è fondamentale sottolineare",
    "non è la tecnologia, ma le persone",
)


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
            assert args[4:6] == ["--language", "it"]
            assert "--confirm" in args and "--json" in args
            return subprocess.CompletedProcess(args, 0, '{"artifact_id": "sandbox-audio"}', "")
        if args[1:3] == ["studio", "status"] and "--artifact-id" not in args:
            return subprocess.CompletedProcess(args, 0, '{"artifacts": []}', "")
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
        assert mocked.call_count == 5
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
        if args[1:3] == ["studio", "status"] and "--artifact-id" not in args:
            return subprocess.CompletedProcess(args, 0, '{"artifacts": []}', "")
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
        if args[1:3] == ["studio", "status"] and "--artifact-id" not in args:
            return subprocess.CompletedProcess(args, 0, '{"artifacts": []}', "")
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
    adapter.assert_called_once_with(
        project.resolve(),
        None,
        "TEST_AUDIO_CORPUS",
        12.0,
        language="it",
        audio_format="m4a",
        length="short",
        overview_format="deep_dive",
        forbidden_phrases=SAMPLE_FORBIDDEN,
    )
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


# --- T-052: NotebookLM as the exclusive publication-grade audio engine ---------------


@pytest.mark.parametrize(("audio_format", "language"), [("m4a", "it"), ("mp3", "en")])
def test_notebooklm_audio_adapter_creates_and_downloads(
    project: Path, monkeypatch: pytest.MonkeyPatch, audio_format: str, language: str
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter, NotebookLMAudioAdapter

    assert NotebookLMAudioAdapter is NotebookLMAdapter
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which", lambda _: "nlm"
    )
    calls: list[list[str]] = []

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["shell"] is False
        calls.append(args)
        if args[1:3] == ["studio", "status"] and "--artifact-id" not in args:
            return subprocess.CompletedProcess(args, 0, '{"artifacts": []}', "")
        if args[1:3] == ["audio", "create"]:
            return subprocess.CompletedProcess(args, 0, '{"artifact_id": "sandbox-audio"}', "")
        if args[1:3] == ["studio", "status"]:
            response = {"artifacts": [{"artifact_id": "sandbox-audio", "status": "completed"}]}
            return subprocess.CompletedProcess(args, 0, json.dumps(response), "")
        destination = args[args.index("--output") + 1]
        assert destination.endswith(f"podcast.{audio_format}")
        (project / destination).write_bytes(b"two-voice podcast")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", execute)
    adapter = NotebookLMAudioAdapter(
        project,
        corpus_id="sandbox-corpus",
        language=language,
        audio_format=audio_format,  # type: ignore[arg-type]
    )
    output = project / "dist/audio/post_01"
    result = adapter.build(
        "post_01",
        "Draft",
        [{"key": "src", "claims": [{"text": "Fatto verificato.", "locator": "p. 1"}]}],
        output,
    )
    create = calls[1]
    assert create[1:4] == ["audio", "create", "sandbox-corpus"]
    assert create[4:7] == ["--language", language, "--confirm"]
    assert create[create.index("--format") + 1] == "deep_dive"
    assert create[create.index("--length") + 1] == "short"
    assert create[-2] == "--focus"
    assert "Fatto verificato. (fonte src, p. 1)" in create[-1]
    assert [call[1:3] for call in calls] == [
        ["studio", "status"],
        ["audio", "create"],
        ["studio", "status"],
        ["download", "audio"],
    ]
    assert result.status == "BUILT" and result.provider == "notebooklm"
    assert result.audio_files == [f"dist/audio/post_01/podcast.{audio_format}"]
    assert result.details == {
        "language": language,
        "format": audio_format,
        "length": "short",
        "overview_format": "deep_dive",
    }
    assert (project / result.audio_files[0]).read_bytes() == b"two-voice podcast"
    assert [p.name for p in output.iterdir()] == [f"podcast.{audio_format}"]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"language": "it;rm"}, "language"),
        ({"language": ""}, "language"),
        ({"language": "-x"}, "language"),
        ({"audio_format": "wav"}, "format"),
        ({"length": "medium"}, "length"),
        ({"length": ""}, "length"),
        ({"overview_format": "summary"}, "overview_format"),
        ({"overview_format": "--json"}, "overview_format"),
    ],
)
def test_notebooklm_rejects_invalid_options(
    project: Path, kwargs: dict[str, str], match: str
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    with pytest.raises(ValueError, match=match):
        NotebookLMAdapter(project, **kwargs)  # type: ignore[arg-type]
    if "length" in kwargs or "overview_format" in kwargs:
        with pytest.raises(ValueError, match=match):
            AudioConfig.model_validate(kwargs)


def test_notebooklm_rejects_bare_string_forbidden_phrases(project: Path) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    with pytest.raises(TypeError, match="forbidden_phrases"):
        NotebookLMAdapter(project, forbidden_phrases="cambia tutto")


def test_cli_mp3_format_dry_run(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before = snapshot(project)
    options = ("--provider", "notebooklm", "--format", "mp3", "--language", "en")
    assert run(project, *options, "--dry-run", "--json") == 0
    result = json.loads(capsys.readouterr().out)
    assert result["audio_files"] == ["dist/audio/post_01/podcast.mp3"]
    assert result["details"] == {
        "language": "en",
        "format": "mp3",
        "length": "short",
        "overview_format": "deep_dive",
    }
    assert snapshot(project) == before


def test_tts_constructor_emits_deprecation(project: Path) -> None:
    from editorial_pipeline.adapters.audio import TTS_DEPRECATION

    assert "sub-standard robotic audio" in TTS_DEPRECATION
    assert "Google NotebookLM Studio is the required editorial standard" in TTS_DEPRECATION
    _tts(project)


def test_cli_provider_choices_prefer_notebooklm(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["build-audio", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert "{notebooklm,script_only,tts}" in help_text
    assert "recommended" in help_text and "deprecated" in help_text


def _configure_notebooklm(project: Path) -> None:
    config = project / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + '\n[audio]\nprovider = "notebooklm"\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize("missing", ["nlm", "corpus"])
def test_configured_notebooklm_falls_back_to_script(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    _configure_notebooklm(project)
    if missing == "corpus":
        monkeypatch.delenv("EDITORIAL_AUDIO_ID", raising=False)
    else:
        monkeypatch.setenv("EDITORIAL_AUDIO_ID", "sandbox-corpus")
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which",
        lambda _: None if missing == "nlm" else "nlm",
    )
    mocked = Mock(side_effect=AssertionError("fallback must stay offline"))
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", mocked)
    assert run(project, "--json") == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["provider"] == "script_only" and result["status"] == "BUILT"
    assert "Falling back to script_only" in output.err
    assert "sandbox-corpus" not in output.err and str(project) not in output.err
    assert not list((project / "dist").rglob("*.mp3"))
    mocked.assert_not_called()


def test_configured_notebooklm_builds_when_available(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from unittest.mock import patch

    from editorial_pipeline.adapters.audio import AudioResult

    _configure_notebooklm(project)
    with patch("editorial_pipeline.cli.commands.NotebookLMAdapter") as adapter:
        adapter.return_value.build.return_value = AudioResult(
            status="BUILT", provider="notebooklm", audio_files=["dist/audio/post_01/podcast.m4a"]
        )
        assert run(project, "--json") == 0
    adapter.return_value.preflight.assert_called_once_with()
    assert json.loads(capsys.readouterr().out)["provider"] == "notebooklm"


# --- T-082: realistic polling window and reuse of existing Studio artifacts ----------


def _studio_mock(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    discovery: list[dict[str, str]],
    statuses: list[str],
) -> list[list[str]]:
    monkeypatch.setattr(
        "editorial_pipeline.adapters.audio.notebooklm.shutil.which", lambda _: "nlm"
    )
    sleeps: list[float] = []
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.time.sleep", sleeps.append)
    pending = iter(statuses)
    calls: list[list[str]] = []

    def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["shell"] is False
        calls.append(args)
        if args[1:3] == ["studio", "status"] and "--artifact-id" not in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"artifacts": discovery}), "")
        if args[1:3] == ["studio", "status"]:
            artifact = args[args.index("--artifact-id") + 1]
            response = {"artifacts": [{"artifact_id": artifact, "status": next(pending)}]}
            return subprocess.CompletedProcess(args, 0, json.dumps(response), "")
        if args[1:3] == ["audio", "create"]:
            return subprocess.CompletedProcess(args, 0, '{"artifact_id": "fresh-audio"}', "")
        assert args[1:3] == ["download", "audio"]
        (project / args[args.index("--output") + 1]).write_bytes(b"studio audio")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.subprocess.run", execute)
    return calls


def test_notebooklm_reuses_completed_studio_artifact(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    discovery = [
        {"artifact_id": "video-1", "type": "video", "status": "completed"},
        {"artifact_id": "-flag", "type": "audio", "status": "completed"},
        {"artifact_id": "broken-audio", "type": "audio", "status": "failed"},
        {"artifact_id": "ready-audio", "type": "audio", "status": "completed"},
    ]
    calls = _studio_mock(project, monkeypatch, discovery, [])
    adapter = NotebookLMAdapter(project, corpus_id="sandbox-corpus")
    result = adapter.build("post_01", "Draft", [], project / "dist/audio/post_01")
    assert [call[1:3] for call in calls] == [["studio", "status"], ["download", "audio"]]
    assert not any(call[1:3] == ["audio", "create"] for call in calls)
    assert calls[-1][calls[-1].index("--id") + 1] == "ready-audio"
    assert result.audio_files == ["dist/audio/post_01/podcast.m4a"]
    assert (project / "dist/audio/post_01/podcast.m4a").read_bytes() == b"studio audio"


@pytest.mark.parametrize("initial", ["in_progress", "queued"])
def test_notebooklm_resumes_in_progress_studio_artifact(
    project: Path, monkeypatch: pytest.MonkeyPatch, initial: str
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    discovery = [{"artifact_id": "running-audio", "status": initial}]
    calls = _studio_mock(project, monkeypatch, discovery, ["in_progress", "completed"])
    adapter = NotebookLMAdapter(project, corpus_id="sandbox-corpus")
    adapter.build("post_01", "Draft", [], project / "dist/audio/post_01")
    assert not any(call[1:3] == ["audio", "create"] for call in calls)
    polls = [call for call in calls if "--artifact-id" in call]
    assert len(polls) == 2
    assert all(call[call.index("--artifact-id") + 1] == "running-audio" for call in polls)
    assert calls[-1][calls[-1].index("--id") + 1] == "running-audio"
    assert (project / "dist/audio/post_01/podcast.m4a").read_bytes() == b"studio audio"


def test_notebooklm_creates_when_no_reusable_artifact(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    discovery = [
        {"artifact_id": "old-audio", "type": "audio", "status": "failed"},
        {"artifact_id": "slides", "type": "slide_deck", "status": "in_progress"},
    ]
    calls = _studio_mock(project, monkeypatch, discovery, ["queued", "completed"])
    NotebookLMAdapter(project, corpus_id="sandbox-corpus").build(
        "post_01", "Draft", [], project / "dist/audio/post_01"
    )
    assert [call[1:3] for call in calls] == [
        ["studio", "status"],
        ["audio", "create"],
        ["studio", "status"],
        ["studio", "status"],
        ["download", "audio"],
    ]
    assert calls[-1][calls[-1].index("--id") + 1] == "fresh-audio"


def test_notebooklm_default_polling_window(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.adapters.audio import AudioUnavailableError, NotebookLMAdapter

    adapter = NotebookLMAdapter(project, corpus_id="sandbox-corpus")
    assert adapter.poll_attempts == 120
    assert adapter.poll_interval == 5.0
    assert adapter.poll_attempts * adapter.poll_interval == 600.0
    sleeps: list[float] = []
    _studio_mock(project, monkeypatch, [], ["in_progress"] * 120)
    monkeypatch.setattr("editorial_pipeline.adapters.audio.notebooklm.time.sleep", sleeps.append)
    with pytest.raises(AudioUnavailableError, match="bounded polling"):
        adapter.build("post_01", "Draft", [], project / "dist/audio/post_01")
    assert len(sleeps) == 119 and set(sleeps) == {5.0}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"poll_attempts": 0},
        {"poll_attempts": -1},
        {"poll_attempts": True},
        {"poll_attempts": 2.5},
        {"poll_interval": 0},
        {"poll_interval": -1.0},
        {"poll_interval": float("inf")},
        {"poll_interval": float("nan")},
    ],
)
def test_notebooklm_rejects_invalid_polling(project: Path, kwargs: dict[str, object]) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    with pytest.raises(ValueError, match="poll_"):
        NotebookLMAdapter(project, **kwargs)  # type: ignore[arg-type]


# --- T-088: explicit regeneration with --new / force_new ------------------------------


def test_notebooklm_force_new_skips_existing_artifact(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    discovery = [{"artifact_id": "ready-audio", "type": "audio", "status": "completed"}]
    calls = _studio_mock(project, monkeypatch, discovery, ["completed"])
    NotebookLMAdapter(project, corpus_id="sandbox-corpus").build(
        "post_01", "Draft", [], project / "dist/audio/post_01", force_new=True
    )
    assert [call[1:3] for call in calls] == [
        ["audio", "create"],
        ["studio", "status"],
        ["download", "audio"],
    ]
    assert calls[-1][calls[-1].index("--id") + 1] == "fresh-audio"


def test_cli_build_audio_new_flag(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from unittest.mock import patch

    from editorial_pipeline.adapters.audio import AudioResult

    built = AudioResult(
        status="BUILT", provider="notebooklm", audio_files=["dist/audio/post_01/podcast.m4a"]
    )
    with patch("editorial_pipeline.cli.commands.NotebookLMAdapter") as adapter:
        adapter.return_value.build.return_value = built
        assert run(project, "--provider", "notebooklm", "--new") == 0
        assert adapter.return_value.build.call_args.kwargs == {"force_new": True}
        adapter.return_value.build.reset_mock()
        assert run(project, "--provider", "notebooklm") == 0
        assert "force_new" not in adapter.return_value.build.call_args.kwargs
    capsys.readouterr()
    assert run(project, "--provider", "script_only", "--new") == 1
    assert "--new is supported only" in capsys.readouterr().err
    assert not (project / "dist/audio/post_01").exists()


# --- T-091: anti-emphasis --focus brief, --length and --overview-format ---------------


def _created(calls: list[list[str]]) -> list[str]:
    (create,) = [call for call in calls if call[1:3] == ["audio", "create"]]
    return create


def test_notebooklm_length_and_format_flags(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    calls = _studio_mock(project, monkeypatch, [], ["completed"])
    result = NotebookLMAdapter(
        project, corpus_id="sandbox-corpus", length="default", overview_format="critique"
    ).build("post_01", "Draft", [], project / "dist/audio/post_01", force_new=True)
    create = _created(calls)
    assert create[create.index("--length") + 1] == "default"
    assert create[create.index("--format") + 1] == "critique"
    assert result.details["length"] == "default"
    assert result.details["overview_format"] == "critique"


def test_notebooklm_defaults_to_short_deep_dive(project: Path) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter
    from editorial_pipeline.config.models import AudioConfig

    adapter = NotebookLMAdapter(project, corpus_id="sandbox-corpus")
    assert (adapter.length, adapter.overview_format) == ("short", "deep_dive")
    assert adapter.forbidden_phrases == ()
    config = AudioConfig()
    assert (config.length, config.overview_format) == ("short", "deep_dive")


def test_focus_imposes_anti_emphasis_rules(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    calls = _studio_mock(project, monkeypatch, [], ["completed"])
    NotebookLMAdapter(
        project,
        corpus_id="sandbox-corpus",
        forbidden_phrases=("a tutto tondo", "  ", "game\n changer"),
    ).build(
        "post_01",
        "Draft",
        [{"key": "src", "claims": [{"text": "Il gettito cresce.", "locator": "tab. 2"}]}],
        project / "dist/audio/post_01",
        force_new=True,
    )
    focus = _created(calls)[-1]
    for directive in (
        "Registro sobrio e giornalistico",
        "Divieto di enfasi e frasi fatte",
        "immersione profonda",
        "forze titaniche",
        "i modelli non mentono",
        "Divieto di metafore ed esempi inventati",
        "prezzi di beni comuni",
        "aliquote",
        "previsioni deterministiche",
        "gettito fiscale",
        "per sempre",
        "Perimetro chiuso",
    ):
        assert directive in focus
    assert "'a tutto tondo', 'game changer'" in focus
    assert "- Il gettito cresce. (fonte src, tab. 2)" in focus
    assert focus.index("Perimetro chiuso") < focus.index("Il gettito cresce.")


def test_focus_omits_project_list_without_forbidden_phrases(project: Path) -> None:
    from editorial_pipeline.adapters.audio import NotebookLMAdapter

    focus = NotebookLMAdapter(project, corpus_id="sandbox-corpus")._build_focus([])
    assert "Espressioni vietate dal progetto" not in focus
    assert "senza precedenti" in focus


@pytest.mark.parametrize(
    ("toml", "options", "expected"),
    [
        ("", (), ("short", "deep_dive")),
        ('length = "long"\noverview_format = "debate"\n', (), ("long", "debate")),
        (
            'length = "long"\noverview_format = "debate"\n',
            ("--length", "default", "--overview-format", "brief"),
            ("default", "brief"),
        ),
    ],
)
def test_cli_resolves_length_and_format(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    toml: str,
    options: tuple[str, ...],
    expected: tuple[str, str],
) -> None:
    config = project / "editorial.toml"
    config.write_text(config.read_text(encoding="utf-8") + "\n[audio]\n" + toml, encoding="utf-8")
    before = snapshot(project)
    assert run(project, "--provider", "notebooklm", *options, "--dry-run", "--json") == 0
    details = json.loads(capsys.readouterr().out)["details"]
    assert (details["length"], details["overview_format"]) == expected
    assert snapshot(project) == before


def test_cli_passes_register_forbidden_phrases(project: Path) -> None:
    from unittest.mock import patch

    from editorial_pipeline.adapters.audio import AudioResult

    with patch("editorial_pipeline.cli.commands.NotebookLMAdapter") as adapter:
        adapter.return_value.build.return_value = AudioResult(
            status="DRY_RUN", provider="notebooklm", audio_files=[]
        )
        assert run(project, "--provider", "notebooklm", "--length", "long", "--dry-run") == 0
    kwargs = adapter.call_args.kwargs
    assert kwargs["forbidden_phrases"] == SAMPLE_FORBIDDEN
    assert kwargs["length"] == "long" and kwargs["overview_format"] == "deep_dive"


def test_cli_rejects_invalid_length(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        run(project, "--provider", "notebooklm", "--length", "medium")
    assert "invalid choice" in capsys.readouterr().err
