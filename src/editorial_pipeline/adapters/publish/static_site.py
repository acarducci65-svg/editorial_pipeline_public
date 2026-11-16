"""Markdown and approved media assets exported to a local static site."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from editorial_pipeline.config import EditorialConfig

from .base import PublishAdapter, PublishResult, selected_actions, skipped

SOURCES_HEADING = re.compile(r"(?im)^#{2,3}\s+Fonti\b")
YEAR = re.compile(r"\b(\d{4})\b")


def _public_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return None
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return value.replace("(", "%28").replace(")", "%29")


def _text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value if _text(item))
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return " ".join(str(value).split())
    return ""


def _source_line(source: dict[str, Any]) -> str | None:
    title = _text(source.get("title"))
    if not title:
        return None
    title = re.sub(r"([\\\[\]])", r"\\\1", title)
    link = next(
        (url for key in ("url", "pdf", "open_access_url") if (url := _public_url(source.get(key)))),
        None,
    )
    doi = _text(source.get("doi")).removeprefix("doi:").removeprefix("https://doi.org/")
    if link is None and doi:
        link = _public_url("https://doi.org/" + doi.strip())
    line = f"- [{title}]({link})" if link else f"- {title}"
    credit = _text(source.get("authors")) or _text(
        source.get("institution") or source.get("publisher") or source.get("organization")
    )
    year_value = source.get("year") or source.get("date") or source.get("published")
    match = YEAR.search(_text(year_value))
    year = match[1] if match else ""
    if credit:
        line += f" — {credit}"
    if year:
        line += f" ({year})" if credit else f" — {year}"
    return line


def append_sources(data: bytes, sources_file: Path) -> bytes:
    """Append a public '## Fonti' list built from sources.json, never local metadata."""
    try:
        text = data.decode("utf-8")
        loaded = json.loads(sources_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return data
    if SOURCES_HEADING.search(text):
        return data
    raw = loaded.get("sources") if isinstance(loaded, dict) else loaded
    if not isinstance(raw, list):
        return data
    lines = [line for s in raw if isinstance(s, dict) and (line := _source_line(s))]
    if not lines:
        return data
    newline = "\r\n" if "\r\n" in text else "\n"
    body = text.rstrip("\r\n")
    section = newline.join(["## Fonti", "", *lines])
    return (body + newline * 2 + section + newline).encode("utf-8")


class StaticSitePublisher(PublishAdapter):
    def publish(
        self,
        post_id: str,
        draft_path: Path,
        artifacts: dict[str, str],
        allowed_actions: list[str],
        config: EditorialConfig,
        dry_run: bool = False,
    ) -> PublishResult:
        actions = selected_actions(
            allowed_actions, {"export_markdown", "publish_markdown", "static_site"}
        )
        if not actions:
            return skipped("static_site")
        files, metadata = self.snapshot(post_id, draft_path, artifacts, allowed_actions, config)
        directory = config.publishing.static_site_dir if config.publishing else None
        directory = directory or f"{config.paths.dist}/published"
        output = self.destination(directory, config) / post_id
        self.safe_path(output.relative_to(self.root).as_posix())
        if output.exists() and not (config.publishing and config.publishing.allow_overwrite):
            raise ValueError("publishing destination already exists")
        draft_name = draft_path.relative_to(self.root).as_posix()
        markdown_name = (
            "index.md"
            if config.publishing and config.publishing.static_site_layout == "hugo_bundle"
            else draft_path.name
        )
        evidence = config.resolve_paths(self.root)["paths.evidence"] / post_id / "sources.json"
        sources_file = self.safe_path(evidence.relative_to(self.root).as_posix())
        markdown = files[draft_name]
        if sources_file.is_file():
            markdown = append_sources(markdown, sources_file)
        exports = {markdown_name: markdown}
        visual = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}
        media_audio = {".mp3", ".m4a", ".ogg", ".wav"}
        if {"publish_audio", "static_site"}.intersection(allowed_actions):
            visual |= media_audio
        exports.update(
            {name: files[name] for name in artifacts if Path(name).suffix.lower() in visual}
        )
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
            target="static_site",
            executed_actions=[] if dry_run else actions,
            published_files=sorted(path.relative_to(self.root).as_posix() for path in targets),
            details={**metadata, "planned_actions": actions},
        )
