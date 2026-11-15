"""Carousel builder: Jinja2 HTML rendering, optional Playwright rasterisation.

HTML slides are always produced. PNG and PDF files are produced only when
Playwright and a Chromium browser are available locally; otherwise the build
degrades to an HTML-only manifest with an explanatory note and never raises
for a missing browser. All network requests from the page are blocked.
"""

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from editorial_pipeline.adapters.visual.base import (
    ArtifactManifest,
    CarouselSpec,
    Slide,
    TemplateNotFoundError,
    VisualBuilder,
    VisualBuildError,
    manifest_digest,
    sha256_file,
)

TEMPLATE_NAME = "carousel_slide.html.jinja2"
_HERE = Path(__file__).resolve()
DEFAULT_TEMPLATE_DIRS = (
    _HERE.parents[2] / "_scaffold" / "templates" / "social",  # installed wheel
    _HERE.parents[4] / "templates" / "social",  # source checkout
)


def _load_sync_playwright() -> tuple[Callable[[], Any], type[Exception]] | None:
    """Return Playwright's ``sync_playwright`` factory and its base error class."""
    try:
        module = importlib.import_module("playwright.sync_api")
    except ImportError:
        return None
    factory = getattr(module, "sync_playwright", None)
    error = getattr(module, "Error", None)
    if not callable(factory) or not (isinstance(error, type) and issubclass(error, Exception)):
        return None
    return factory, error


def _block_request(route: Any) -> None:
    route.abort()


class PlaywrightVisualBuilder(VisualBuilder):
    def __init__(
        self,
        template_dir: Path | None = None,
        template_name: str = TEMPLATE_NAME,
        language: str = "it",
        rasterize: bool = True,
        workspace_root: Path | None = None,
    ) -> None:
        self.template_dir = template_dir
        self.template_name = template_name
        self.language = language
        self.rasterize = rasterize
        self.workspace_root = workspace_root.resolve() if workspace_root else None
        # Resolved [theme] values (see ThemeConfig.resolved); empty means template defaults.
        self.theme: dict[str, str] = {}
        self._template: Any = None

    def _resolve_template_dir(self) -> Path:
        candidates = (self.template_dir,) if self.template_dir else DEFAULT_TEMPLATE_DIRS
        for candidate in candidates:
            if candidate is not None and (candidate / self.template_name).is_file():
                return candidate
        raise TemplateNotFoundError("Carousel template not found")

    def _load_template(self) -> Any:
        if self._template is None:
            try:
                jinja2 = importlib.import_module("jinja2")
            except ImportError as exc:
                raise VisualBuildError("Jinja2 is required: install the 'social' extra") from exc
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(self._resolve_template_dir())),
                autoescape=True,
                undefined=jinja2.StrictUndefined,
                keep_trailing_newline=True,
            )
            try:
                self._template = env.get_template(self.template_name)
            except jinja2.TemplateNotFound as exc:
                raise TemplateNotFoundError("Carousel template not found") from exc
        return self._template

    def render_html(self, spec: CarouselSpec, slides: list[Slide] | None = None) -> str:
        width, height = spec.size
        try:
            return str(
                self._load_template().render(
                    spec=spec,
                    slides=spec.slides if slides is None else slides,
                    total=len(spec.slides),
                    width=width,
                    height=height,
                    lang=self.language,
                    theme=self.theme,
                )
            )
        except VisualBuildError:
            raise
        except Exception as exc:
            raise VisualBuildError("Carousel template rendering failed") from exc

    def build_carousel(self, spec: CarouselSpec, output_dir: Path) -> ArtifactManifest:
        target = output_dir / spec.post_id
        # Without an explicit workspace, the lexical output directory is the boundary.
        boundary = self.workspace_root or output_dir.absolute()

        def check(path: Path) -> None:
            if not path.resolve().is_relative_to(boundary):
                raise VisualBuildError("Carousel output resolves outside workspace")

        check(output_dir)
        check(target)
        # Preflight every output before any write, including existing file links.
        outputs = [target / "manifest.json", target / f"{spec.post_id}_carousel.pdf"]
        outputs.extend(
            target / f"slide_{slide.number:02d}.{ext}"
            for slide in spec.slides
            for ext in ("html", "png")
        )
        for output in outputs:
            check(output)
        try:
            target.mkdir(parents=True, exist_ok=True)
            html_files: list[Path] = []
            for slide in spec.slides:
                path = target / f"slide_{slide.number:02d}.html"
                path.write_text(self.render_html(spec, [slide]), encoding="utf-8")
                html_files.append(path)
            deck = self.render_html(spec)
        except OSError as exc:
            raise VisualBuildError("Cannot write carousel files") from exc

        notes: list[str] = []
        rendered: list[Path] = []
        if self.rasterize:
            rendered, note = self._rasterize(spec, target, deck)
            if note:
                notes.append(note)
        else:
            notes.append("Rasterisation disabled: HTML preview only")

        files = [
            {
                "path": path.relative_to(output_dir).as_posix(),
                "kind": path.suffix.lstrip("."),
                "sha256": sha256_file(path),
            }
            for path in html_files + rendered
        ]
        manifest = ArtifactManifest(
            post_id=spec.post_id,
            artifact_type="carousel" if rendered else "carousel_html",
            files=files,
            digest=manifest_digest(files),
            notes=notes,
        )
        try:
            (target / "manifest.json").write_text(
                json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise VisualBuildError("Cannot write carousel manifest") from exc
        return manifest

    def _rasterize(self, spec: CarouselSpec, target: Path, deck: str) -> tuple[list[Path], str]:
        loaded = _load_sync_playwright()
        if loaded is None:
            return [], "Playwright not installed: HTML preview only"
        sync_playwright, playwright_error = loaded
        width, height = spec.size
        outputs: list[Path] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.route("**/*", _block_request)
                    for slide in spec.slides:
                        png = target / f"slide_{slide.number:02d}.png"
                        page.set_content(self.render_html(spec, [slide]), wait_until="load")
                        page.screenshot(path=str(png), type="png", full_page=False)
                        outputs.append(png)
                    pdf = target / f"{spec.post_id}_carousel.pdf"
                    page.set_content(deck, wait_until="load")
                    page.pdf(
                        path=str(pdf),
                        width=f"{width}px",
                        height=f"{height}px",
                        print_background=True,
                    )
                    outputs.append(pdf)
                finally:
                    browser.close()
        except (playwright_error, OSError) as exc:
            for path in outputs:
                path.unlink(missing_ok=True)
            return [], f"Browser rendering unavailable ({type(exc).__name__}): HTML preview only"
        return outputs, ""
