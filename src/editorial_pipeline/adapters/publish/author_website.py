"""Long-form article page for the author's personal website (portfolio channel).

The export is a self-contained folder: ``index.html`` rendered from the
approved draft plus copies of the approved assets (slides, deck, podcast).
Like every publisher it runs only after Gate 2 and only for its own actions;
it never uploads anything — deploying the folder stays a human step.
"""

import importlib
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from editorial_pipeline.application.web_hub import render_markdown
from editorial_pipeline.config import EditorialConfig

from .base import PublishAdapter, PublishResult, selected_actions, skipped

TEMPLATE_NAME = "author_website_article.html.jinja2"
ACTIONS = {"author_website", "publish_author_website", "export_author_site"}
AUDIO = {".m4a": "audio/mp4", ".mp3": "audio/mpeg"}
SLIDE = {".html", ".png", ".jpg", ".jpeg", ".webp"}
ASSET = {*AUDIO, *SLIDE, ".pdf", ".gif", ".svg"}
_HERE = Path(__file__).resolve()
DEFAULT_TEMPLATE_DIRS = (
    _HERE.parents[2] / "_scaffold" / "templates" / "publish",  # installed wheel
    _HERE.parents[4] / "templates" / "publish",  # source checkout
)
WORDS_PER_MINUTE = 220


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return the YAML front matter (empty when absent or invalid) and the body."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    if text.startswith("---\n") and "\n---\n" in text:
        header, body = text[4:].split("\n---\n", 1)
        try:
            data = yaml.safe_load(header)
        except yaml.YAMLError:
            data = None
        return (data if isinstance(data, dict) else {}), body
    return {}, text


def author_card(path: Path) -> dict[str, str]:
    """Name and short bio from a YAML profile or a Markdown author page."""
    # Lazy import: cli.__init__ imports the command dispatcher, which imports us.
    from editorial_pipeline.cli.reports import _sanitize

    try:
        text = str(_sanitize(path.read_text(encoding="utf-8-sig")))
    except OSError:
        return {"name": "", "bio": ""}
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            data = None
        author = data.get("author") if isinstance(data, dict) else None
        if isinstance(author, dict):
            name = author.get("display_name") or ""
            bio = author.get("bio_short") or author.get("bio_long") or ""
            return {"name": str(name).strip(), "bio": " ".join(str(bio).split())}
        return {"name": "", "bio": ""}
    metadata, body = split_front_matter(text)
    name = metadata.get("author")
    if isinstance(name, dict):
        name = name.get("display_name")
    bio = ""
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if block and not block.startswith(("#", "-", "*", ">", "|")):
            bio = re.sub(r"[*_`]", "", " ".join(block.split()))
            break
    return {"name": str(name or "").strip(), "bio": bio}


def _environment(template_dirs: list[Path]) -> Any:
    try:
        jinja = importlib.import_module("jinja2")
    except ImportError as exc:
        raise ValueError(
            "Author website requires Jinja2; install editorial-pipeline[social]"
        ) from exc
    directory = next((d for d in template_dirs if (d / TEMPLATE_NAME).is_file()), None)
    if directory is None:
        raise ValueError("Author website template not found")
    return jinja.Environment(
        loader=jinja.FileSystemLoader(str(directory)),
        autoescape=True,
        undefined=jinja.StrictUndefined,
        keep_trailing_newline=True,
    )


class AuthorWebsitePublisher(PublishAdapter):
    def publish(
        self,
        post_id: str,
        draft_path: Path,
        artifacts: dict[str, str],
        allowed_actions: list[str],
        config: EditorialConfig,
        dry_run: bool = False,
    ) -> PublishResult:
        actions = selected_actions(allowed_actions, ACTIONS)
        if not actions:
            return skipped("author_website")
        files, metadata = self.snapshot(post_id, draft_path, artifacts, allowed_actions, config)
        directory = config.publishing.author_website_dir if config.publishing else None
        directory = directory or f"{config.paths.dist}/author_site"
        output = self.destination(directory, config) / post_id
        self.safe_path(output.relative_to(self.root).as_posix())
        if output.exists():
            raise ValueError("publishing destination already exists")
        paths = config.resolve_paths(self.root)
        dist = paths["paths.dist"]

        # Approved assets keep their path below dist/ so names stay unique.
        exports: dict[str, bytes] = {}
        for name in sorted(artifacts):
            source = self.root / name
            if source.suffix.lower() not in ASSET or not source.is_relative_to(dist):
                continue
            exports["assets/" + source.relative_to(dist).as_posix()] = files[name]
        audio = next((n for n in exports if PurePosixPath(n).suffix.lower() in AUDIO), "")
        slides_by_stem: dict[str, str] = {}
        for name in exports:
            item = PurePosixPath(name)
            if item.suffix.lower() in SLIDE and item.stem.startswith("slide_"):
                # Prefer raster images over HTML previews of the same slide.
                previous = slides_by_stem.get(item.stem)
                if previous is None or PurePosixPath(previous).suffix == ".html":
                    slides_by_stem[item.stem] = name
        slides = [
            {"src": name, "kind": "html" if name.endswith(".html") else "image"}
            for _, name in sorted(slides_by_stem.items())
        ]
        deck = next((n for n in exports if n.lower().endswith(".pdf")), "")

        draft_name = draft_path.relative_to(self.root).as_posix()
        front, body = split_front_matter(files[draft_name].decode("utf-8"))
        article, toc = render_markdown(body)
        words = len(re.findall(r"\w+", body))
        title = str(front.get("title") or post_id)
        base_url = config.project.base_url.rstrip("/")
        transparency = [
            {"label": "Metodo", "href": base_url + config.transparency.method_page},
            {"label": "Correzioni", "href": base_url + config.transparency.corrections_page},
            {"label": "Per chi scrive", "href": base_url + config.transparency.press_page},
        ]
        template_dirs = [paths["paths.templates"] / "publish", *DEFAULT_TEMPLATE_DIRS]
        page = (
            _environment(template_dirs)
            .get_template(TEMPLATE_NAME)
            .render(
                lang=config.project.language,
                site=config.project.name,
                base_url=base_url,
                post_id=post_id,
                title=title,
                subtitle=str(front.get("subtitle") or ""),
                date=str(front.get("date") or ""),
                reading_minutes=max(1, round(words / WORDS_PER_MINUTE)),
                author=author_card(paths["author.profile"]),
                article=article,
                toc=toc,
                audio=audio,
                audio_type=AUDIO.get(PurePosixPath(audio).suffix.lower(), ""),
                slides=slides,
                deck=deck,
                transparency=transparency,
                contact=config.corrections.contact_email,
                theme=config.theme.resolved(),
                bundle_digest=metadata["bundle_digest"],
            )
        )
        exports["index.html"] = page.encode("utf-8")
        targets = {
            self.safe_path((output / name).relative_to(self.root).as_posix()): data
            for name, data in exports.items()
        }
        if not dry_run:
            for path, data in targets.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        return PublishResult(
            status="DRY_RUN" if dry_run else "PUBLISHED",
            target="author_website",
            executed_actions=[] if dry_run else actions,
            published_files=sorted(path.relative_to(self.root).as_posix() for path in targets),
            details={**metadata, "planned_actions": actions, "entry_point": "index.html"},
        )
