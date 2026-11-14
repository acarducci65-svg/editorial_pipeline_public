"""Local tar.gz export of the approved publication bundle."""

import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from editorial_pipeline.config import EditorialConfig

from .base import PublishAdapter, PublishResult, selected_actions, skipped


class DistArchivePublisher(PublishAdapter):
    def publish(
        self,
        post_id: str,
        draft_path: Path,
        artifacts: dict[str, str],
        allowed_actions: list[str],
        config: EditorialConfig,
        dry_run: bool = False,
    ) -> PublishResult:
        actions = selected_actions(allowed_actions, {"archive", "dist_archive", "export_package"})
        if not actions:
            return skipped("dist_archive")
        files, metadata = self.snapshot(post_id, draft_path, artifacts, allowed_actions, config)
        directory = config.publishing.archive_dir if config.publishing else None
        directory = directory or f"{config.paths.dist}/packages"
        output = self.destination(directory, config) / f"{post_id}.tar.gz"
        self.safe_path(output.relative_to(self.root).as_posix())
        if output.exists():
            raise ValueError("publishing destination already exists")
        manifest = {
            **metadata,
            "post_id": post_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "executed_actions": actions,
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        }
        files["publish_manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2).encode()
        if not dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream, tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for name, data in files.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(data))
        return PublishResult(
            status="DRY_RUN" if dry_run else "PUBLISHED",
            target="dist_archive",
            executed_actions=[] if dry_run else actions,
            published_files=[output.relative_to(self.root).as_posix()],
            details={**metadata, "planned_actions": actions, "archive_members": sorted(files)},
        )
