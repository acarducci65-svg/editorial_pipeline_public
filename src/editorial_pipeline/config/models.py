import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def relative_path(value: str) -> str:
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value.replace("\\", "/"))
    if not value or windows.drive or windows.root or posix.is_absolute() or ".." in posix.parts:
        raise ValueError("path must be relative to the project directory")
    return value


RelativePath = Annotated[str, AfterValidator(relative_path)]

MACRO_RUNTIME_AMMESSE = {"{{UNIT_ID}}", "{{DIGEST_SHORT}}", "{{PUBLISH_AT_LOCAL}}", "{{SEQ}}"}


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Project(Schema):
    name: str
    slug: str
    language: str
    timezone: str
    content_unit: str
    content_unit_plural: str
    base_url: str


class Paths(Schema):
    content: RelativePath
    evidence: RelativePath
    dist: RelativePath
    templates: RelativePath
    pages: RelativePath
    corrections: RelativePath
    sources: RelativePath
    reports: RelativePath


class Author(Schema):
    profile: RelativePath


class Manifesto(Schema):
    file: RelativePath


class Register(Schema):
    active: RelativePath
    directory: RelativePath
    extra_forbidden: list[str]


class OptionalPhases(Schema):
    F0: bool
    F1: bool
    F4_visual: bool
    F4_video: bool
    F5: bool


class DisabledBehavior(Schema):
    status: Literal["skipped", "warning", "blocked"]
    report_in_summary: bool


class Phases(Schema):
    core: list[str]
    optional: OptionalPhases
    disabled_behavior: DisabledBehavior


class Gate(Schema):
    name: str
    required: Literal[True]
    after: str
    approval_phrase: str
    question: str
    allowed_actions: list[str] = []


class Gates(Schema):
    approver_role: str
    receipts_dir: RelativePath
    forbidden_excerpts: list[str]
    gate1: Gate
    gate2: Gate


class DraftingProvider(Schema):
    adapter: str
    model_label: str


class HumanizerProvider(Schema):
    adapter: str
    separate_pass_required: bool


class RagProvider(Schema):
    adapter: str
    corpus_id_env: str
    max_claims_per_turn: int


class Provider(Schema):
    adapter: str


class Providers(Schema):
    drafting: DraftingProvider
    humanizer: HumanizerProvider
    rag: RagProvider
    audio: Provider = Field(default_factory=lambda: Provider(adapter="script_only"))
    visual: Provider


class Factcheck(Schema):
    allowed_outcomes: list[str]
    blocking_outcomes: list[str]
    promotion_outcomes: list[str]
    require_locator_for_promotion: bool
    circular_source_tags: list[str]


class Humanizer(Schema):
    required_items: list[str]
    reviewer_must_differ_from_author: bool


class TransparencyTemplates(Schema):
    method: RelativePath
    corrections: RelativePath
    press: RelativePath


class Transparency(Schema):
    method_page: str
    corrections_page: str
    press_page: str
    trailing_slash: bool
    require_separate_approval: bool
    templates: TransparencyTemplates


class Corrections(Schema):
    pre_publication_id: str
    post_publication_id: str
    categories_pre: list[str]
    categories_post: list[str]
    statuses: list[str]
    show_reporter_name: bool
    contact_email: str


class Privacy(Schema):
    report_paths: Literal["relative"]
    reject_absolute_paths: Literal[True]
    deny_patterns: list[str]


class RagConfig(Schema):
    provider: Literal["local", "manual", "none", "notebooklm"] = "local"
    corpus_id: str | None = None
    corpus_id_env: str = "EDITORIAL_RAG_ID"
    timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)


class PublishingConfig(Schema):
    target: Literal["dist_archive", "static_site", "author_website"] = "dist_archive"
    archive_dir: RelativePath | None = None
    static_site_dir: RelativePath | None = None
    static_site_layout: Literal["flat", "hugo_bundle"] = "flat"
    allow_overwrite: bool = False
    author_website_dir: RelativePath | None = None


class AudioConfig(Schema):
    provider: Literal["script_only", "notebooklm"] = "script_only"
    corpus_id: str | None = Field(default=None, repr=False)
    corpus_id_env: str = "EDITORIAL_AUDIO_ID"
    timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    length: Literal["short", "default", "long"] = "short"
    overview_format: Literal["deep_dive", "brief", "critique", "debate"] = "deep_dive"


HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]

# Contrast-checked presets: accent and ink pass WCAG AA (4.5:1) on the background.
THEME_PRESETS: dict[str, dict[str, str]] = {
    "cobalt_tech": {
        "accent_color": "#2563eb",
        "background_color": "#f8fafc",
        "ink_color": "#0f172a",
    },
    "emerald": {"accent_color": "#0f766e", "background_color": "#f7faf9", "ink_color": "#0f1f1c"},
    "nordic_minimal": {
        "accent_color": "#475569",
        "background_color": "#ffffff",
        "ink_color": "#111827",
    },
}


class ThemeConfig(Schema):
    """Visual identity shared by the web console and the social carousel.

    ``palette`` selects a preset; colours set explicitly in ``[theme]`` override
    it (``custom`` starts from ``cobalt_tech``). Colours are strict ``#rrggbb``
    values because they are written into CSS.
    """

    palette: Literal["cobalt_tech", "emerald", "nordic_minimal", "custom"] = "cobalt_tech"
    accent_color: HexColor = "#2563eb"
    background_color: HexColor = "#f8fafc"
    ink_color: HexColor = "#0f172a"
    font_family: Literal["sans", "serif"] = "sans"

    def resolved(self) -> dict[str, str]:
        """Return the effective colours and font family for templates."""
        values = dict(THEME_PRESETS.get(self.palette, THEME_PRESETS["cobalt_tech"]))
        for key in ("accent_color", "background_color", "ink_color"):
            if key in self.model_fields_set:
                values[key] = getattr(self, key)
        values["font_family"] = self.font_family
        values["palette"] = self.palette
        return values


class EditorialConfig(Schema):
    schema_version: Literal[1]
    project: Project
    paths: Paths
    author: Author
    manifesto: Manifesto
    register_: Register = Field(alias="register")
    phases: Phases
    gates: Gates
    providers: Providers
    factcheck: Factcheck
    humanizer: Humanizer
    transparency: Transparency
    corrections: Corrections
    privacy: Privacy
    rag: RagConfig | None = None
    publishing: PublishingConfig | None = None
    audio: AudioConfig | None = None
    theme: ThemeConfig = Field(default_factory=ThemeConfig)

    @property
    def register(self) -> Register:
        return self.register_

    def resolve_paths(self, project_root: Path) -> dict[str, Path]:
        """Resolve configured filesystem paths, rejecting symlink escapes."""
        root = project_root.resolve()
        values = {f"paths.{key}": value for key, value in self.paths.model_dump().items()}
        values.update(
            {
                "author.profile": self.author.profile,
                "manifesto.file": self.manifesto.file,
                "register.active": self.register.active,
                "register.directory": self.register.directory,
                "gates.receipts_dir": self.gates.receipts_dir,
            }
        )
        values.update(
            {
                f"transparency.templates.{key}": value
                for key, value in self.transparency.templates.model_dump().items()
            }
        )
        result: dict[str, Path] = {}
        for key, value in values.items():
            resolved = (root / value.replace("\\", "/")).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(f"configured path {key} resolves outside project root")
            result[key] = resolved
        return result

    def validate_operative(self) -> None:
        """Reject unexpanded placeholders in configuration values."""

        def check(value: object) -> None:
            if isinstance(value, str):
                placeholders = re.findall(r"\{\{.*?\}\}", value, re.DOTALL)
                if any(item not in MACRO_RUNTIME_AMMESSE for item in placeholders):
                    raise ValueError("unresolved placeholder in operative configuration")
            if isinstance(value, dict):
                for item in value.values():
                    check(item)
            if isinstance(value, (list, tuple)):
                for item in value:
                    check(item)

        check(self.model_dump())
