import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

import pytest

from editorial_pipeline.cli.commands import main
from tests.test_cli import ROOT, _refresh_evidence, _write_gate_receipt

ACTIONS = [
    "archive",
    "dist_archive",
    "export_package",
    "export_markdown",
    "publish_markdown",
    "static_site",
    "publish_audio",
    "publish",
]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "blog"
    shutil.copytree(ROOT, root)
    config = root / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace(
        'allowed_actions = ["publish", "sync", "deploy"]',
        "allowed_actions = " + json.dumps(ACTIONS),
    )
    # Replace the actual policy independently of formatting of its action list.
    import re

    text = re.sub(
        r"(\[gates.gate2\][\s\S]*?allowed_actions\s*=\s*)\[[^\]]*\]",
        lambda m: m[1] + json.dumps(ACTIONS),
        text,
    )
    config.write_text(text, encoding="utf-8")
    _refresh_evidence(root)
    asset = root / "dist/social/post_01/slide.png"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"visual")
    _write_gate_receipt(root, 1)
    approve(root, ["archive", "export_markdown"])
    return root


def approve(root: Path, actions: list[str]) -> None:
    path = _write_gate_receipt(root, 2)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["allowed_actions"] = actions
    data["excerpt"] = "Approvo Gate 2 #post_01; " + ", ".join(actions)
    path.write_text(json.dumps(data), encoding="utf-8")


def snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
        for p in root.rglob("*")
    }


def run(root: Path, *args: str) -> int:
    return main(["publish", "post_01", "--config", str(root / "editorial.toml"), "--json", *args])


def test_publish_snapshot_keeps_binary_crlf(project: Path) -> None:
    asset = project / "dist/social/post_01/slide.png"
    asset.write_bytes(b"binary\r\nbytes")
    approve(project, ["archive", "export_markdown"])
    assert run(project) == 0


def test_binary_newline_change_invalidates_gate2(project: Path) -> None:
    asset = project / "dist/social/post_01/slide.png"
    asset.write_bytes(b"binary\r\nbytes")
    approve(project, ["archive", "export_markdown"])
    asset.write_bytes(b"binary\nbytes")
    before = snapshot(project)
    assert run(project) == 2
    assert snapshot(project) == before


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "json",
        "role",
        "excerpt",
        "draft",
        "gate1",
        "asset",
        "unmentioned",
        "not_permitted",
    ],
)
@pytest.mark.parametrize("dry", [False, True])
def test_invalid_gate_never_writes(
    project: Path, case: str, dry: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    receipt = project / "evidence/post_01/approvals/gate2.json"
    if case == "missing":
        receipt.unlink()
    elif case == "json":
        receipt.write_text("{", encoding="utf-8")
    elif case in {"draft", "gate1", "asset"}:
        name = {
            "draft": "content/posts/post_01_valid.md",
            "gate1": "evidence/post_01/approvals/gate1.json",
            "asset": "dist/social/post_01/slide.png",
        }[case]
        with (project / name).open("ab") as stream:
            stream.write(b" ")
    else:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data[
            {
                "role": "role",
                "excerpt": "excerpt",
                "unmentioned": "excerpt",
                "not_permitted": "allowed_actions",
            }[case]
        ] = ["delete"] if case == "not_permitted" else ""
        receipt.write_text(json.dumps(data), encoding="utf-8")
    before = snapshot(project)
    assert run(project, *(["--dry-run"] if dry else [])) == 2
    assert snapshot(project) == before
    output = capsys.readouterr()
    assert output.err and not output.out
    assert str(project) not in output.err


@pytest.mark.parametrize(
    "target,action",
    [
        ("dist_archive", "archive"),
        ("dist_archive", "dist_archive"),
        ("dist_archive", "export_package"),
        ("static_site", "export_markdown"),
        ("static_site", "publish_markdown"),
        ("static_site", "static_site"),
    ],
)
@pytest.mark.parametrize("dry", [False, True])
def test_publish_targets(
    project: Path, target: str, action: str, dry: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(project, [action])
    before = snapshot(project)
    assert run(project, "--target", target, *(["--dry-run"] if dry else [])) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == ("DRY_RUN" if dry else "PUBLISHED")
    assert result["executed_actions"] == ([] if dry else [action])
    assert result["published_files"]
    assert str(project) not in output
    if dry:
        assert before == snapshot(project)
    elif target == "dist_archive":
        with tarfile.open(project / "dist/packages/post_01.tar.gz") as archive:
            names = archive.getnames()
            assert {
                "content/posts/post_01_valid.md",
                "evidence/post_01/approvals/gate1.json",
                "evidence/post_01/approvals/gate2.json",
                "dist/social/post_01/slide.png",
                "publish_manifest.json",
            } <= set(names)
            stream = archive.extractfile("publish_manifest.json")
            assert stream is not None
            manifest = json.load(stream)
            assert manifest["bundle_digest"].startswith("v1:")
            for name, checksum in manifest["files"].items():
                member = archive.extractfile(name)
                assert member is not None
                assert checksum == hashlib.sha256(member.read()).hexdigest()
    else:
        assert (project / "dist/published/post_01/post_01_valid.md").read_bytes() == (
            project / "content/posts/post_01_valid.md"
        ).read_bytes()
        assert (
            project / "dist/published/post_01/dist/social/post_01/slide.png"
        ).read_bytes() == b"visual"


@pytest.mark.parametrize("target", ["dist_archive", "static_site"])
def test_generic_publish_does_not_grant_adapter_actions(
    project: Path, target: str, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(project, ["publish"])
    before = snapshot(project)
    assert run(project, "--target", target) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "SKIPPED"
    assert result["executed_actions"] == result["published_files"] == []
    assert snapshot(project) == before


def test_config_target_and_output(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\ntarget = "static_site"\nstatic_site_dir = "public/posts"\n')
    assert run(project) == 0
    assert json.loads(capsys.readouterr().out)["target"] == "static_site"
    assert (project / "public/posts/post_01/post_01_valid.md").is_file()


@pytest.mark.parametrize("directory", ["../escape", "content/posts", "evidence/post_01/approvals"])
def test_unsafe_output_rejected_before_writes(project: Path, directory: str) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write("\n[publishing]\nstatic_site_dir = " + json.dumps(directory) + "\n")
    before = snapshot(project)
    assert run(project, "--target", "static_site") == 1
    assert snapshot(project) == before


def test_static_site_hugo_bundle_layout(project: Path) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\nstatic_site_layout = "hugo_bundle"\n')
    draft = project / "content/posts/post_01_valid.md"
    draft.write_bytes(draft.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    _refresh_evidence(project)
    _write_gate_receipt(project, 1)
    approve(project, ["export_markdown"])
    assert run(project, "--target", "static_site") == 0
    output = project / "dist/published/post_01"
    assert (output / "index.md").read_bytes() == draft.read_bytes()
    assert not (output / draft.name).exists()


@pytest.mark.parametrize("suffix", [".mp3", ".m4a", ".ogg", ".wav", ".MP3"])
@pytest.mark.parametrize("action", ["publish_audio", "static_site", "export_markdown"])
def test_static_site_audio_media_included(project: Path, suffix: str, action: str) -> None:
    name = f"dist/audio/post_01/podcast{suffix}"
    audio = project / name
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"audio\r\nbytes")
    approve(project, ["export_markdown", action] if action != "export_markdown" else [action])
    assert run(project, "--target", "static_site") == 0
    output = project / "dist/published/post_01" / name
    if action == "export_markdown":
        assert not output.exists()
    else:
        assert output.read_bytes() == b"audio\r\nbytes"


def test_static_site_excludes_html_artifacts(project: Path) -> None:
    excluded = [
        "dist/social/post_01/slide_01.html",
        "dist/social/post_01/slide_01.css",
        "dist/web/post_01.html",
        "dist/web/post_01.HTML",
    ]
    for name in excluded:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html></html>", encoding="utf-8")
    approve(project, ["export_markdown", "static_site"])
    assert run(project, "--target", "static_site") == 0
    output = project / "dist/published/post_01"
    assert (output / "post_01_valid.md").exists()
    assert (output / "dist/social/post_01/slide.png").read_bytes() == b"visual"
    for name in excluded:
        assert not (output / name).exists()
    exported = {path.suffix.lower() for path in output.rglob("*") if path.is_file()}
    assert not exported & {".html", ".css"}


@pytest.mark.parametrize("dry", [False, True])
def test_static_site_allow_overwrite(project: Path, dry: bool) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write("\n[publishing]\nallow_overwrite = true\n")
    assert run(project, "--target", "static_site") == 0
    draft = project / "content/posts/post_01_valid.md"
    draft.write_bytes(draft.read_bytes() + b"\nApproved correction.\n")
    _refresh_evidence(project)
    _write_gate_receipt(project, 1)
    approve(project, ["export_markdown"])
    before = snapshot(project)
    assert run(project, "--target", "static_site", *(["--dry-run"] if dry else [])) == 0
    if dry:
        assert snapshot(project) == before
    else:
        assert (
            project / "dist/published/post_01/post_01_valid.md"
        ).read_bytes() == draft.read_bytes()


def test_static_site_overwrite_disabled(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write("\n[publishing]\nallow_overwrite = false\n")
    output = project / "dist/published/post_01/post_01_valid.md"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"existing publication")
    approve(project, ["export_markdown"])
    before = snapshot(project)
    assert run(project, "--target", "static_site") == 1
    assert "publishing destination already exists" in capsys.readouterr().err
    assert snapshot(project) == before


def test_static_site_rejects_invalid_layout(project: Path) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\nstatic_site_layout = "unknown"\n')
    before = snapshot(project)
    assert run(project, "--target", "static_site") == 1
    assert snapshot(project) == before


def test_missing_config_returns_one(tmp_path: Path) -> None:
    assert run(tmp_path) == 1


@pytest.mark.parametrize(
    "case",
    [
        "asset_changed",
        "asset_missing",
        "receipt_corrupt",
        "receipt_missing",
        "actions_changed",
        "role_changed",
        "excerpt_changed",
    ],
)
def test_inputs_changed_after_gate_check_fail_closed(
    project: Path, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from editorial_pipeline.cli import commands

    original = commands._check_gate

    def checking(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original(*args, **kwargs)
        asset = project / "dist/social/post_01/slide.png"
        receipt = project / "evidence/post_01/approvals/gate2.json"
        if case == "asset_changed":
            asset.write_bytes(b"changed")
        elif case == "asset_missing":
            asset.unlink()
        elif case == "receipt_corrupt":
            receipt.write_bytes(b"{")
        elif case == "receipt_missing":
            receipt.unlink()
        else:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if case == "role_changed":
                data["role"] = "agent"
            elif case == "excerpt_changed":
                data["excerpt"] = "Approvo Gate 2 #post_01"
            else:
                data["allowed_actions"] = ["static_site"]
            receipt.write_text(json.dumps(data), encoding="utf-8")
        return result

    monkeypatch.setattr(commands, "_check_gate", checking)
    assert run(project) == 2
    assert not (project / "dist/packages").exists()


@pytest.mark.parametrize("target", ["dist_archive", "static_site"])
def test_existing_destination_is_preserved(project: Path, target: str) -> None:
    output = project / (
        "dist/packages/post_01.tar.gz" if target == "dist_archive" else "dist/published/post_01"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if target == "static_site":
        output.mkdir()
    else:
        output.write_bytes(b"existing archive")
    approve(project, ["archive", "export_markdown"])
    before = snapshot(project)
    assert run(project, "--target", target) == 1
    assert snapshot(project) == before


def test_archive_custom_output_and_human_output(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\narchive_dir = "releases"\n')
    assert main(["publish", "post_01_valid.md", "--config", str(project / "editorial.toml")]) == 0
    assert "PUBLISHED: dist_archive" in capsys.readouterr().out
    assert (project / "releases/post_01.tar.gz").is_file()


def test_skipped_human_output_warns(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    approve(project, ["publish"])
    assert main(["publish", "post_01", "--config", str(project / "editorial.toml")]) == 0
    output = capsys.readouterr()
    assert "SKIPPED" in output.out and "No approved action" in output.err


@pytest.mark.parametrize("outside", [False, True])
def test_symlink_outputs_are_rejected(project: Path, tmp_path: Path, outside: bool) -> None:
    target = tmp_path / "outside" if outside else project / "export-dir"
    target.mkdir()
    link = project / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with (project / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\narchive_dir = "linked"\n')
    assert run(project) == 1
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("target", ["dist_archive", "static_site"])
def test_sanitized_draft_and_selective_files(
    project: Path, target: str, capsys: pytest.CaptureFixture[str]
) -> None:
    post = project / "content/posts/post_01_valid.md"
    host_path = "Z:" + chr(92) + "fixture" + chr(92) + "draft.md"
    text = post.read_text(encoding="utf-8")
    post.write_text(
        text.replace("---\n", "---\nprivate_path: " + host_path + "\n", 1), encoding="utf-8"
    )
    _refresh_evidence(project)
    _write_gate_receipt(project, 1)
    approve(project, ["archive", "export_markdown"])
    assert run(project, "--target", target) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["executed_actions"] == (
        ["archive"] if target == "dist_archive" else ["export_markdown"]
    )
    if target == "static_site":
        output = (project / "dist/published/post_01/post_01_valid.md").read_text(encoding="utf-8")
        assert not (project / "dist/published/post_01/dist/social/post_01/kit.txt").exists()
    else:
        with tarfile.open(project / "dist/packages/post_01.tar.gz") as archive:
            member = archive.extractfile("content/posts/post_01_valid.md")
            assert member is not None
            output = member.read().decode("utf-8")
            assert all(
                not m.uid and not m.gid and not m.uname and not m.gname
                for m in archive.getmembers()
            )
    assert host_path not in output
    assert "private_path: [redacted]" in output
    assert host_path in post.read_text(encoding="utf-8")
