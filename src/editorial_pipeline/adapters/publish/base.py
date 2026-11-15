"""Publishing port and safe snapshots of the approved distribution bundle."""

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from editorial_pipeline.config import EditorialConfig
from editorial_pipeline.config.models import relative_path
from editorial_pipeline.domain.gates import (
    Gate2Receipt,
    GhostApprovalForbiddenError,
    mentions,
    validate_excerpt,
)


class PublishResult(BaseModel):
    status: Literal["PUBLISHED", "DRY_RUN", "SKIPPED"]
    target: str
    executed_actions: list[str]
    published_files: list[str]
    details: dict[str, Any] = Field(default_factory=dict)


class PublishAdapter(ABC):
    """A local target; callers must validate Gate 2 before invoking publish."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root.resolve()

    @abstractmethod
    def publish(
        self,
        post_id: str,
        draft_path: Path,
        artifacts: dict[str, str],
        allowed_actions: list[str],
        config: EditorialConfig,
        dry_run: bool = False,
    ) -> PublishResult:
        """Execute only explicitly approved target actions."""

    def safe_path(self, name: str) -> Path:
        relative_path(name)
        path = self.root / name.replace("\\", "/")
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("publishing path resolves outside project root")
        if any(p.is_symlink() for p in (path, *path.parents) if p != self.root):
            raise ValueError("publishing paths must not contain symlinks")
        return path

    def destination(self, directory: str, config: EditorialConfig) -> Path:
        path = self.safe_path(directory)
        paths = config.resolve_paths(self.root)
        protected = [value for key, value in paths.items() if key != "paths.dist"]
        # Output must never be an ancestor/descendant of editorial source paths.
        if any(path.is_relative_to(p) or p.is_relative_to(path) for p in protected):
            raise ValueError("publishing destination overlaps protected project inputs")
        return path

    def snapshot(
        self,
        post_id: str,
        draft: Path,
        artifacts: dict[str, str],
        allowed_actions: list[str],
        config: EditorialConfig,
    ) -> tuple[dict[str, bytes], dict[str, Any]]:
        # Lazy import: cli.__init__ imports the command dispatcher, which imports us.
        from editorial_pipeline.cli.reports import _sanitize

        if not post_id or post_id in {".", ".."} or "/" in post_id or "\\" in post_id:
            raise ValueError("invalid publishing post identifier")
        paths = config.resolve_paths(self.root)
        receipts = paths["paths.evidence"] / post_id / config.gates.receipts_dir
        first = (receipts / "gate1.json").relative_to(self.root).as_posix()
        second = (receipts / "gate2.json").relative_to(self.root).as_posix()
        draft_name = draft.relative_to(self.root).as_posix()
        names = sorted(set(artifacts) | {draft_name, first, second})
        try:
            files = {name: self.safe_path(name).read_bytes() for name in names}
            receipt = Gate2Receipt.model_validate_json(files[second])
        except (OSError, ValueError) as exc:
            raise GhostApprovalForbiddenError(
                "Approved publishing inputs are unreadable or invalid"
            ) from exc
        if (
            receipt.role != config.gates.approver_role
            or receipt.post_id != post_id
            or receipt.allowed_actions != allowed_actions
            or receipt.bundle.artifacts != artifacts
            or not all(mentions(receipt.excerpt, action) for action in allowed_actions)
        ):
            raise GhostApprovalForbiddenError("Gate 2 changed before publishing")
        validate_excerpt(
            receipt.excerpt,
            config.gates.gate2.approval_phrase,
            post_id,
            config.gates.forbidden_excerpts,
        )
        expected = {
            **artifacts,
            draft_name: receipt.bundle.draft_digest,
            first: receipt.bundle.gate1_digest,
        }
        for name, checksum in expected.items():
            actual = (
                "v1:"
                + hashlib.sha256(
                    name.encode() + b"\0" + files[name].replace(b"\r\n", b"\n")
                ).hexdigest()
            )
            if actual != checksum:
                raise GhostApprovalForbiddenError("Approved publishing input changed")
        files[draft_name] = str(_sanitize(files[draft_name].decode("utf-8"))).encode("utf-8")
        bundle = json.dumps(receipt.bundle.model_dump(), sort_keys=True, separators=(",", ":"))
        metadata = {"bundle_digest": "v1:" + hashlib.sha256(bundle.encode()).hexdigest()}
        return files, metadata


def selected_actions(allowed: list[str], aliases: set[str]) -> list[str]:
    return [action for action in allowed if action in aliases]


def skipped(target: str) -> PublishResult:
    return PublishResult(
        status="SKIPPED",
        target=target,
        executed_actions=[],
        published_files=[],
        details={"warning": "No approved action authorizes this target"},
    )
