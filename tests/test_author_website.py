import importlib
import json
import re
from pathlib import Path

import pytest

from editorial_pipeline.adapters.publish import author_website
from editorial_pipeline.adapters.publish.author_website import (
    AuthorWebsitePublisher,
    author_card,
    split_front_matter,
)
from editorial_pipeline.config import load_config
from tests import test_publish
from tests.test_publish import approve, run, snapshot

# Reuse the Gate 2-ready sample project of the publish tests.
project = test_publish.project

WEBSITE_ACTIONS = ["author_website", "publish_author_website", "export_author_site"]


@pytest.fixture
def site(project: Path) -> Path:
    config = project / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    text = re.sub(
        r"(\[gates.gate2\][\s\S]*?allowed_actions\s*=\s*\[)",
        lambda m: m[1] + ", ".join(json.dumps(a) for a in WEBSITE_ACTIONS) + ", ",
        text,
    )
    config.write_text(text, encoding="utf-8")
    social = project / "dist/social/post_01"
    (social / "slide_01.html").write_text("<p>uno</p>", encoding="utf-8")
    (social / "slide_02.html").write_text("<p>due</p>", encoding="utf-8")
    (social / "slide_02.png").write_bytes(b"png")
    (social / "deck.pdf").write_bytes(b"%PDF")
    audio = project / "dist/audio/post_01/podcast.m4a"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"audio")
    return project


@pytest.mark.parametrize("action", WEBSITE_ACTIONS)
@pytest.mark.parametrize("dry", [False, True])
def test_author_website_export(
    site: Path, action: str, dry: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(site, [action])
    before = snapshot(site)
    assert run(site, "--target", "author_website", *(["--dry-run"] if dry else [])) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["target"] == "author_website"
    assert result["status"] == ("DRY_RUN" if dry else "PUBLISHED")
    assert result["executed_actions"] == ([] if dry else [action])
    assert "dist/author_site/post_01/index.html" in result["published_files"]
    assert result["details"]["bundle_digest"].startswith("v1:")
    assert str(site) not in output
    if dry:
        assert snapshot(site) == before
        return
    out = site / "dist/author_site/post_01"
    page = (out / "index.html").read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE html>")
    assert 'src="assets/audio/post_01/podcast.m4a" type="audio/mp4"' in page
    # Raster slide wins over the HTML preview of the same slide.
    assert "assets/social/post_01/slide_02.png" in page
    assert "assets/social/post_01/slide_01.html" in page
    assert "sandbox" in page
    assert 'href="assets/social/post_01/deck.pdf"' in page
    assert "https://blog.example.org/metodo/" in page
    assert "Ada Esempio" in page
    assert "https://" not in re.sub(r'href="https://blog\.example\.org[^"]*"', "", page)
    assert (out / "assets/audio/post_01/podcast.m4a").read_bytes() == b"audio"
    assert not (out / "assets/audio/post_01/podcast_script.md").exists()


def test_author_website_config_target_and_dir(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(site, ["author_website"])
    with (site / "editorial.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[publishing]\ntarget = "author_website"\nauthor_website_dir = "site"\n')
    assert run(site) == 0
    assert json.loads(capsys.readouterr().out)["target"] == "author_website"
    assert (site / "site/post_01/index.html").is_file()
    assert run(site) == 1  # never overwrites an existing export


def test_author_website_requires_its_own_action(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(site, ["export_markdown"])
    before = snapshot(site)
    assert run(site, "--target", "author_website") == 0
    assert json.loads(capsys.readouterr().out)["status"] == "SKIPPED"
    assert snapshot(site) == before


def test_author_website_stale_gate_never_writes(site: Path) -> None:
    approve(site, ["author_website"])
    (site / "dist/audio/post_01/podcast.m4a").write_bytes(b"changed")
    before = snapshot(site)
    assert run(site, "--target", "author_website") == 2
    assert snapshot(site) == before


def test_author_website_missing_template(site: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    approve(site, ["author_website"])
    monkeypatch.setattr(author_website, "DEFAULT_TEMPLATE_DIRS", ())
    assert run(site, "--target", "author_website") == 1


def test_author_website_missing_jinja(site: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    approve(site, ["author_website"])
    real = importlib.import_module

    def fake(name: str) -> object:
        if name == "jinja2":
            raise ImportError(name)
        return real(name)

    monkeypatch.setattr(importlib, "import_module", fake)
    assert run(site, "--target", "author_website") == 1


def test_project_template_override(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    approve(site, ["author_website"])
    config = load_config(site / "editorial.toml")
    folder = config.resolve_paths(site)["paths.templates"] / "publish"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / author_website.TEMPLATE_NAME).write_text("custom {{ title }}", encoding="utf-8")
    result = AuthorWebsitePublisher(site).publish(
        "post_01",
        site / "content/posts/post_01_valid.md",
        json.loads((site / "evidence/post_01/approvals/gate2.json").read_text("utf-8"))["bundle"][
            "artifacts"
        ],
        ["author_website"],
        config,
    )
    assert result.status == "PUBLISHED"
    page = (site / "dist/author_site/post_01/index.html").read_text(encoding="utf-8")
    assert page.startswith("custom ")


def test_split_front_matter() -> None:
    assert split_front_matter("---\ntitle: T\n---\nbody") == ({"title": "T"}, "body")
    assert split_front_matter("---\n: [\n---\nbody") == ({}, "body")
    assert split_front_matter("---\n- a\n---\nbody") == ({}, "body")
    assert split_front_matter("plain") == ({}, "plain")


def test_author_card_formats(tmp_path: Path) -> None:
    yaml_profile = tmp_path / "profile.yaml"
    yaml_profile.write_text(
        "author:\n  display_name: Ada\n  bio_long: Lunga  bio\n", encoding="utf-8"
    )
    assert author_card(yaml_profile) == {"name": "Ada", "bio": "Lunga bio"}
    yaml_profile.write_text("author: solo testo\n", encoding="utf-8")
    assert author_card(yaml_profile) == {"name": "", "bio": ""}
    yaml_profile.write_text("author: [\n", encoding="utf-8")
    assert author_card(yaml_profile) == {"name": "", "bio": ""}
    page = tmp_path / "autore.md"
    page.write_text(
        "---\nauthor:\n  display_name: Redazione\n---\n# Titolo\n\n- voce\n\n"
        "La **redazione** scrive\nsu due righe.\n",
        encoding="utf-8",
    )
    assert author_card(page) == {"name": "Redazione", "bio": "La redazione scrive su due righe."}
    page.write_text("Solo testo.\n", encoding="utf-8")
    assert author_card(page) == {"name": "", "bio": "Solo testo."}
    assert author_card(tmp_path / "missing.md") == {"name": "", "bio": ""}
