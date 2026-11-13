"""Command-line interface for project validation."""

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from editorial_pipeline.application.style_checker import StyleChecker, aggregate_state
from editorial_pipeline.cli.reports import digest, relative_path, serialize
from editorial_pipeline.config import EditorialConfig, load_config
from editorial_pipeline.domain.gates import GhostApprovalForbiddenError, HumanApproval
from editorial_pipeline.domain.models import Finding, VerificationState


def _config(path: str) -> tuple[Path, EditorialConfig, dict[str, Path]]:
    file = Path(path).resolve()
    config = load_config(file)
    config.validate_operative()
    return file.parent, config, config.resolve_paths(file.parent)


def _post(target: str, root: Path, posts: Path) -> Path:
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = root / candidate if len(candidate.parts) > 1 else posts / candidate
    if not candidate.suffix:
        candidate = candidate.with_suffix(".md")
    candidate = candidate.resolve()
    if not candidate.is_relative_to(posts.resolve()) or not candidate.is_file():
        raise ValueError("post not found in project content directory")
    return candidate


def _validate(post: Path, root: Path, evidence: Path, checker: StyleChecker) -> dict[str, Any]:
    findings = list(checker.scan_file(post))
    post_id = post.stem
    # Sample and common editorial naming: post_01_title -> post_01.
    parts = post_id.split("_")
    if len(parts) > 2 and parts[1].isdigit():
        post_id = "_".join(parts[:2])
    ev = evidence / post_id
    for name in ("sources.json", "factcheck.json"):
        if not (ev / name).is_file():
            findings.append(
                Finding("evidence.missing", f"Missing evidence: {name}", VerificationState.BLOCK)
            )
    return {
        "rel_path": relative_path(post, root),
        "digest": digest(post, root),
        "state": aggregate_state(findings).value,
        "evidence": relative_path(ev, root),
        "findings": [
            {"code": f.code, "message": f.message, "state": f.state.value} for f in findings
        ],
    }


def _copy_resources(source: Any, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            _copy_resources(item, destination)
        else:
            destination.write_bytes(item.read_bytes())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="editorial-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("target_dir")
    for name in ("status", "validate-draft", "validate-all", "check-gate"):
        p = sub.add_parser(name)
        if name == "check-gate":
            p.add_argument("gate_num", type=int, choices=(1, 2))
        if name in ("validate-draft", "check-gate"):
            p.add_argument("post_target")
        if name == "check-gate":
            p.add_argument("--token")
        if name in ("validate-draft", "validate-all"):
            p.add_argument("--json", action="store_true")
        p.add_argument("--config", default="editorial.toml")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            target = Path(args.target_dir)
            target.mkdir(parents=True, exist_ok=False)
            source = Path(__file__).resolve().parents[3]
            if (source / "templates").is_dir() and (source / "editorial.example.toml").is_file():
                shutil.copy(source / "editorial.example.toml", target / "editorial.toml")
                shutil.copytree(source / "templates", target / "templates")
            else:
                scaffold = resources.files("editorial_pipeline").joinpath("_scaffold")
                (target / "editorial.toml").write_bytes(
                    scaffold.joinpath("editorial.example.toml").read_bytes()
                )
                _copy_resources(scaffold.joinpath("templates"), target / "templates")
            for folder in ("content/posts", "evidence"):
                (target / folder).mkdir(parents=True, exist_ok=True)
            print("Project initialized; fill in editorial.toml placeholders.")
            return 0
        root, config, paths = _config(args.config)
        posts = paths["paths.content"]
        if args.command == "check-gate":
            post = _post(args.post_target, root, posts)
            approval = HumanApproval(
                author="human",
                timestamp=datetime.now(timezone.utc),
                token=args.token or "",
                source="human",
            )
            approval.bind_evidence(digest(post, root))
            print(
                json.dumps(
                    {
                        "gate": args.gate_num,
                        "post": relative_path(post, root),
                        "status": "APPROVED",
                        "author": approval.author,
                        "timestamp": approval.timestamp.isoformat(),
                        "token": approval.token,
                    }
                )
            )
            return 0
        checker = StyleChecker.from_config(config, root)
        selected = (
            [_post(args.post_target, root, posts)]
            if args.command == "validate-draft"
            else sorted(posts.glob("*.md"))
        )
        reports = [_validate(post, root, paths["paths.evidence"], checker) for post in selected]
        result: dict[str, Any] = {"posts": reports}
        if args.command == "status":
            result["directories"] = {
                key: value.is_dir()
                for key, value in paths.items()
                if key in ("paths.content", "paths.evidence", "paths.templates")
            }
        print(serialize(result))
        return int(any(report["state"] == "BLOCK" for report in reports))
    except GhostApprovalForbiddenError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {type(exc).__name__}", file=sys.stderr)
        return 1
