"""Markdown and approved media assets exported to a local static site."""

from pathlib import Path

from editorial_pipeline.config import EditorialConfig

from .base import PublishAdapter, PublishResult, selected_actions, skipped


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
        exports = {markdown_name: files[draft_name]}
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
