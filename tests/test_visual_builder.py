import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from editorial_pipeline.adapters.visual import (
    ArtifactManifest,
    CarouselSpec,
    PlaywrightVisualBuilder,
    Slide,
    TemplateNotFoundError,
    VisualBuilder,
    VisualBuildError,
    get_visual_builder,
)
from editorial_pipeline.adapters.visual import playwright_builder as pb
from editorial_pipeline.adapters.visual.base import manifest_digest, sha256_file
from editorial_pipeline.config import load_config

TEMPLATE_DIR = Path("templates/social")
TEMPLATE = TEMPLATE_DIR / "carousel_slide.html.jinja2"


def make_spec(aspect_ratio: str = "4:5", **overrides: Any) -> CarouselSpec:
    values: dict[str, Any] = {
        "post_id": "post_01",
        "title": "Una redazione aumentata",
        "subtitle": "Metodo, fonti e cancelli umani",
        "author": "Redazione di esempio",
        "slides": [
            Slide(1, "Perché un metodo", "Primo paragrafo.\n\nSecondo paragrafo."),
            Slide(2, "Fonti primarie", "Ogni dato ha un locator.", "Nessuna fonte, nessun dato."),
            Slide(3, "Due cancelli", "Bozza e pubblicazione restano umane."),
        ],
        "aspect_ratio": aspect_ratio,
    }
    values.update(overrides)
    return CarouselSpec(**values)


def builder(**kwargs: Any) -> PlaywrightVisualBuilder:
    return PlaywrightVisualBuilder(template_dir=TEMPLATE_DIR, **kwargs)


# --- dataclasses ---------------------------------------------------------------------------


def test_spec_dimensions_and_validation() -> None:
    assert make_spec().size == (1080, 1350)
    assert make_spec("1:1").size == (1080, 1080)
    bad: list[dict[str, Any]] = [
        {"post_id": "../escape"},
        {"post_id": ""},
        {"aspect_ratio": "16:9"},
        {"slides": []},
        {"slides": [Slide(2, "Fuori ordine", "")]},
    ]
    for override in bad:
        with pytest.raises(ValueError):
            make_spec(**override)
    with pytest.raises(ValueError):
        Slide(0, "Titolo", "")
    with pytest.raises(ValueError):
        Slide(1, "   ", "")


def test_manifest_digest_is_order_independent(tmp_path: Path) -> None:
    files = [{"path": "a.html", "sha256": "1"}, {"path": "b.png", "sha256": "2"}]
    digest = manifest_digest(files)
    assert digest == manifest_digest(list(reversed(files)))
    manifest = ArtifactManifest("post_01", "carousel", files, digest)
    assert manifest.verify()
    assert manifest.to_dict()["files"] == files
    assert not ArtifactManifest("post_01", "carousel", files, "0" * 64).verify()
    sample = tmp_path / "x.bin"
    sample.write_bytes(b"abc")
    assert sha256_file(sample) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


# --- template ------------------------------------------------------------------------------


def test_template_is_offline_and_leak_free() -> None:
    source = re.sub(r"\{#.*?#\}", "", TEMPLATE.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert not re.search(
        r"https?://|//fonts\.|cdn|@import|<script|<link|<img", source, re.IGNORECASE
    )
    assert not re.search(r"[A-Za-z]:\\|/Users/|/home/|@[a-z0-9-]+\.[a-z]{2,}", source)


def test_render_valid_html_with_sizes() -> None:
    spec = make_spec()
    html = builder().render_html(spec, [spec.slides[1]])
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert '<html lang="it">' in html and html.rstrip().endswith("</html>")
    assert html.count('<section class="slide') == 1
    assert "aspect-ratio: 1080 / 1350" in html
    assert "02 / 03" in html
    assert "Nessuna fonte, nessun dato." in html
    assert "src=" not in html and "http" not in html
    square = builder(language="en").render_html(make_spec("1:1"))
    assert "aspect-ratio: 1080 / 1080" in square and '<html lang="en">' in square
    assert square.count('<section class="slide') == 3
    assert 'class="slide cover"' in square and "Metodo, fonti e cancelli umani" in square
    assert square.count("<p>") == 4


def test_render_autoescapes_special_characters() -> None:
    payload = '<script>alert("x")</script> & co'
    spec = make_spec(
        title=payload,
        author="A & B",
        slides=[Slide(1, payload, payload, payload)],
    )
    html = builder().render_html(spec)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "A &amp; B" in html


def test_missing_template_and_jinja(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(TemplateNotFoundError):
        PlaywrightVisualBuilder(template_dir=tmp_path).render_html(make_spec())
    monkeypatch.setattr(pb, "DEFAULT_TEMPLATE_DIRS", (tmp_path / "none",))
    with pytest.raises(TemplateNotFoundError):
        PlaywrightVisualBuilder().render_html(make_spec())
    monkeypatch.setitem(sys.modules, "jinja2", None)
    with pytest.raises(VisualBuildError, match="Jinja2"):
        builder().render_html(make_spec())


def test_template_vanishing_and_render_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "t.jinja2").write_text("{{ missing_variable }}", encoding="utf-8")
    with pytest.raises(VisualBuildError, match="rendering"):
        PlaywrightVisualBuilder(tmp_path, "t.jinja2").render_html(make_spec())
    gone = PlaywrightVisualBuilder(tmp_path, "t.jinja2")
    (tmp_path / "t.jinja2").unlink()
    monkeypatch.setattr(gone, "_resolve_template_dir", lambda: tmp_path)
    with pytest.raises(TemplateNotFoundError):
        gone.render_html(make_spec())


def test_default_template_dir_from_checkout() -> None:
    html = PlaywrightVisualBuilder().render_html(make_spec())
    assert "<!DOCTYPE html>" in html


# --- builder ---------------------------------------------------------------------------------


def _assert_manifest(manifest: ArtifactManifest, out: Path) -> None:
    assert manifest.verify()
    for entry in manifest.files:
        assert not Path(entry["path"]).is_absolute() and ".." not in entry["path"]
        assert sha256_file(out / entry["path"]) == entry["sha256"]
    stored = json.loads((out / "post_01" / "manifest.json").read_text(encoding="utf-8"))
    assert stored == manifest.to_dict()
    assert str(out) not in json.dumps(stored)


def test_build_dry_run_writes_html_only(tmp_path: Path) -> None:
    manifest = builder(rasterize=False).build_carousel(make_spec(), tmp_path)
    assert manifest.artifact_type == "carousel_html"
    assert [f["path"] for f in manifest.files] == [
        "post_01/slide_01.html",
        "post_01/slide_02.html",
        "post_01/slide_03.html",
    ]
    assert manifest.notes == ["Rasterisation disabled: HTML preview only"]
    _assert_manifest(manifest, tmp_path)


def test_build_without_playwright_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    manifest = builder().build_carousel(make_spec(), tmp_path)
    assert manifest.artifact_type == "carousel_html"
    assert "not installed" in manifest.notes[0]
    _assert_manifest(manifest, tmp_path)


class FakePlaywrightError(Exception):
    pass


class FakePage:
    def __init__(self, fail_on_pdf: bool) -> None:
        self.fail_on_pdf = fail_on_pdf
        self.contents: list[str] = []
        self.routed = False

    def route(self, pattern: str, handler: Any) -> None:
        self.routed = True
        route = types.SimpleNamespace(aborted=False)
        route.abort = lambda: setattr(route, "aborted", True)
        handler(route)
        assert route.aborted

    def set_content(self, html: str, wait_until: str) -> None:
        self.contents.append(html)

    def screenshot(self, path: str, type: str, full_page: bool) -> None:
        Path(path).write_bytes(b"\x89PNG fake")

    def pdf(self, path: str, **kwargs: Any) -> None:
        if self.fail_on_pdf:
            raise FakePlaywrightError("browser crashed")
        assert kwargs["width"] == "1080px" and kwargs["print_background"]
        Path(path).write_bytes(b"%PDF fake")


def install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch, *, fail_on_pdf: bool = False, fail_launch: bool = False
) -> dict[str, Any]:
    state: dict[str, Any] = {"closed": False}
    page = FakePage(fail_on_pdf)
    state["page"] = page

    class Browser:
        def new_page(self, viewport: dict[str, int]) -> FakePage:
            state["viewport"] = viewport
            return page

        def close(self) -> None:
            state["closed"] = True

    class Chromium:
        def launch(self) -> Browser:
            if fail_launch:
                raise FakePlaywrightError("Executable doesn't exist")
            return Browser()

    class Context:
        chromium = Chromium()

        def __enter__(self) -> Any:
            return types.SimpleNamespace(chromium=self.chromium)

        def __exit__(self, *args: object) -> None:
            return None

    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = Context  # type: ignore[attr-defined]
    module.Error = FakePlaywrightError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    return state


def test_build_with_playwright_renders_png_and_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = install_fake_playwright(monkeypatch)
    manifest = builder().build_carousel(make_spec(), tmp_path)
    assert manifest.artifact_type == "carousel"
    kinds = [f["kind"] for f in manifest.files]
    assert kinds == ["html"] * 3 + ["png"] * 3 + ["pdf"]
    assert manifest.files[-1]["path"] == "post_01/post_01_carousel.pdf"
    assert manifest.notes == []
    assert state["viewport"] == {"width": 1080, "height": 1350}
    assert state["closed"] and state["page"].routed
    assert state["page"].contents[-1].count('<section class="slide') == 3
    _assert_manifest(manifest, tmp_path)


def test_build_browser_failure_cleans_partial_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = install_fake_playwright(monkeypatch, fail_on_pdf=True)
    manifest = builder().build_carousel(make_spec(), tmp_path)
    assert manifest.artifact_type == "carousel_html"
    assert "FakePlaywrightError" in manifest.notes[0]
    assert state["closed"]
    assert not list((tmp_path / "post_01").glob("*.png"))
    _assert_manifest(manifest, tmp_path)
    install_fake_playwright(monkeypatch, fail_launch=True)
    assert builder().build_carousel(make_spec(), tmp_path).artifact_type == "carousel_html"


def test_playwright_module_without_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", types.ModuleType("x"))
    assert pb._load_sync_playwright() is None


def test_build_write_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    with pytest.raises(VisualBuildError, match="write carousel files"):
        builder(rasterize=False).build_carousel(make_spec(), blocker)
    original = Path.write_text

    def failing(self: Path, *args: Any, **kwargs: Any) -> int:
        if self.name == "manifest.json":
            raise OSError("disk full")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing)
    with pytest.raises(VisualBuildError, match="manifest"):
        builder(rasterize=False).build_carousel(make_spec(), tmp_path / "out")


# --- factory ---------------------------------------------------------------------------------


def test_factory(tmp_path: Path) -> None:
    default = get_visual_builder()
    assert isinstance(default, VisualBuilder) and isinstance(default, PlaywrightVisualBuilder)
    assert default.template_dir is None
    config = load_config("editorial.example.toml")
    configured = get_visual_builder("playwright", config, Path("."))
    assert isinstance(configured, PlaywrightVisualBuilder)
    assert configured.template_dir == Path(".") / config.paths.templates / "social"
    assert configured.language == config.project.language
    rooted = get_visual_builder(root=tmp_path)
    assert isinstance(rooted, PlaywrightVisualBuilder)
    assert rooted.template_dir == tmp_path / "templates" / "social"
    with pytest.raises(ValueError):
        get_visual_builder("canva")
