"""Visual builder interfaces and factory."""

from pathlib import Path

from editorial_pipeline.adapters.visual.base import (
    ASPECT_RATIOS,
    ArtifactManifest,
    CarouselSpec,
    Slide,
    TemplateNotFoundError,
    VisualBuilder,
    VisualBuildError,
)
from editorial_pipeline.adapters.visual.playwright_builder import PlaywrightVisualBuilder
from editorial_pipeline.config.models import EditorialConfig


def get_visual_builder(
    name: str = "playwright", config: EditorialConfig | None = None, root: Path | None = None
) -> VisualBuilder:
    if name != "playwright":
        raise ValueError("Unknown visual builder")
    template_dir = None
    if root is not None:
        templates = config.paths.templates if config is not None else "templates"
        template_dir = root / templates / "social"
    language = config.project.language if config is not None else "it"
    return PlaywrightVisualBuilder(
        template_dir=template_dir, language=language, workspace_root=root
    )


__all__ = [
    "ASPECT_RATIOS",
    "ArtifactManifest",
    "CarouselSpec",
    "PlaywrightVisualBuilder",
    "Slide",
    "TemplateNotFoundError",
    "VisualBuildError",
    "VisualBuilder",
    "get_visual_builder",
]
