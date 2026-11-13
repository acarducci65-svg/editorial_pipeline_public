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

import yaml

from editorial_pipeline.adapters.rag import (
    EvidenceMissingError,
    RagUnavailableError,
    get_rag_provider,
)
from editorial_pipeline.adapters.visual import (
    CarouselSpec,
    PlaywrightVisualBuilder,
    Slide,
    VisualBuildError,
    get_visual_builder,
)
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


def _post_id(post: Path) -> str:
    parts = post.stem.split("_")
    return "_".join(parts[:2]) if len(parts) > 2 and parts[1].isdigit() else post.stem


def _carousel(post: Path, post_id: str, author: str, aspect_ratio: str) -> CarouselSpec:
    text = post.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {}
    if text.startswith("---\n") and "\n---\n" in text:
        header, text = text[4:].split("\n---\n", 1)
        parsed = yaml.safe_load(header)
        if isinstance(parsed, dict):
            metadata = parsed
    title = str(metadata.get("title") or post_id)
    subtitle = str(metadata.get("subtitle") or "")
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        elif line.strip():
            sections.append((title, [line]))
    slides = [
        Slide(i, heading or title, "\n".join(lines).strip())
        for i, (heading, lines) in enumerate(sections, 1)
    ]
    return CarouselSpec(
        post_id, title, subtitle, author, slides or [Slide(1, title, "")], aspect_ratio
    )


def _validate(post: Path, root: Path, evidence: Path, checker: StyleChecker) -> dict[str, Any]:
    findings = list(checker.scan_file(post))
    post_id = _post_id(post)
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
    for name in (
        "status",
        "validate-draft",
        "validate-all",
        "check-gate",
        "verify-facts",
        "build-visual",
    ):
        p = sub.add_parser(name)
        if name == "check-gate":
            p.add_argument("gate_num", type=int, choices=(1, 2))
        if name in ("validate-draft", "check-gate", "verify-facts", "build-visual"):
            p.add_argument("post_target")
        if name == "check-gate":
            p.add_argument("--token")
        if name in ("validate-draft", "validate-all", "verify-facts"):
            p.add_argument("--json", action="store_true")
        if name == "build-visual":
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--aspect-ratio", choices=("4:5", "1:1"), default="4:5")
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
        if args.command in ("verify-facts", "build-visual"):
            post = _post(args.post_target, root, posts)
            post_id = _post_id(post)
            if args.command == "verify-facts":
                evidence = paths["paths.evidence"] / post_id
                try:
                    data = json.loads((evidence / "factcheck.json").read_text(encoding="utf-8"))
                except FileNotFoundError as exc:
                    raise EvidenceMissingError("Required evidence file is missing") from exc
                if not isinstance(data, dict) or data.get("post_id") != post_id:
                    raise ValueError("Invalid evidence post identifier")
                records = data.get("claims")
                if (
                    not isinstance(records, list)
                    or not records
                    or any(
                        not isinstance(item, dict)
                        or not isinstance(item.get("text"), str)
                        or not item["text"].strip()
                        for item in records
                    )
                ):
                    raise ValueError("Invalid or empty claims")
                findings = get_rag_provider("local", config, root).verify(
                    [item["text"] for item in records], evidence
                )
                draft_text = post.read_text(encoding="utf-8")
                for index, item in enumerate(records, 1):
                    if item["text"] not in draft_text:
                        findings.append(
                            Finding(
                                "rag.claim_not_in_draft",
                                f"Claim {index} has no literal match in the draft",
                                VerificationState.WARN,
                            )
                        )
                print(
                    serialize(
                        {
                            "post": relative_path(post, root),
                            "findings": [
                                {"code": f.code, "message": f.message, "state": f.state.value}
                                for f in findings
                            ],
                        }
                    )
                )
                return int(any(f.state == VerificationState.BLOCK for f in findings))
            spec = _carousel(post, post_id, config.project.name, args.aspect_ratio)
            builder = get_visual_builder("playwright", config, root)
            if isinstance(builder, PlaywrightVisualBuilder):
                if not (
                    paths["paths.templates"] / "social" / "carousel_slide.html.jinja2"
                ).is_file():
                    builder.template_dir = None
                if args.dry_run:
                    builder.rasterize = False
            manifest = builder.build_carousel(spec, paths["paths.dist"] / "social")
            print(serialize(manifest.to_dict()))
            return 0
        checker = StyleChecker.from_config(config, root)
        selected = (
            [_post(args.post_target, root, posts)]
            if args.command == "validate-draft"
            else sorted(post for post in posts.rglob("*.md") if not post.name.startswith("_"))
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
    except (OSError, ValueError, RagUnavailableError, VisualBuildError, yaml.YAMLError) as exc:
        print(f"Error: {type(exc).__name__}", file=sys.stderr)
        return 1
