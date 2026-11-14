"""Command-line interface for project validation."""

import argparse
import re
import shutil
import sys
import warnings
import webbrowser
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from editorial_pipeline import __version__
from editorial_pipeline.adapters.audio import (
    TTS_DEPRECATION,
    AudioProvider,
    AudioUnavailableError,
    LocalTtsAudioProvider,
    NotebookLMAdapter,
    ScriptOnlyAdapter,
)
from editorial_pipeline.adapters.publish import (
    DistArchivePublisher,
    PublishAdapter,
    StaticSitePublisher,
)
from editorial_pipeline.adapters.rag import (
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
from editorial_pipeline.application.evidence_verifier import (
    EvidenceError,
    EvidenceVerifier,
    load_records,
)
from editorial_pipeline.application.style_checker import StyleChecker, aggregate_state
from editorial_pipeline.application.web_hub import generate_web_hub, serve_console
from editorial_pipeline.cli.reports import _sanitize, digest, relative_path, serialize
from editorial_pipeline.config import EditorialConfig, load_config
from editorial_pipeline.config.models import MACRO_RUNTIME_AMMESSE, AudioConfig
from editorial_pipeline.domain.gates import (
    RECEIPT_ADAPTER,
    Gate1Receipt,
    Gate2Receipt,
    GateReceipt,
    GhostApprovalForbiddenError,
    mentions,
    validate_excerpt,
)
from editorial_pipeline.domain.models import (
    EvidenceBundle,
    Finding,
    GateDecision,
    PostId,
    VerificationState,
)


class PostIdCollisionError(ValueError):
    """Multiple Markdown files share an evidence identifier."""


def _config(path: str) -> tuple[Path, EditorialConfig, dict[str, Path]]:
    file = Path(path).resolve()
    config = load_config(file)
    try:
        config.validate_operative()
    except ValueError as exc:
        # Add the field and missing key without exposing the configuration value.
        pending: list[tuple[str, Any]] = [("", config.model_dump(by_alias=True))]
        while pending:
            location, value = pending.pop()
            if isinstance(value, dict):
                pending.extend(
                    (f"{location}.{key}".lstrip("."), item) for key, item in value.items()
                )
            elif isinstance(value, (list, tuple)):
                pending.extend((f"{location}.{i}", item) for i, item in enumerate(value))
            elif isinstance(value, str):
                for placeholder in re.findall(r"\{\{.*?\}\}", value, re.DOTALL):
                    if placeholder not in MACRO_RUNTIME_AMMESSE:
                        raise ValueError(
                            f"Unresolved placeholder at {location}: {placeholder}"
                        ) from exc
        raise
    return file.parent, config, config.resolve_paths(file.parent)


def _post(target: str, root: Path, posts: Path) -> Path:
    _discover_posts(posts)
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


def _discover_posts(posts: Path) -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    for post in sorted(posts.rglob("*.md")):
        if not post.is_file():
            continue
        post_id = _post_id(post)
        if post_id in discovered:
            raise PostIdCollisionError("post_id collision in project content directory")
        discovered[post_id] = post
    return discovered


def _plain_heading(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`~]", "", text).strip()


def _carousel(post: Path, post_id: str, author: str, aspect_ratio: str) -> CarouselSpec:
    text = post.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {}
    if text.startswith("---\n") and "\n---\n" in text:
        header, text = text[4:].split("\n---\n", 1)
        parsed = yaml.safe_load(header)
        if isinstance(parsed, dict):
            metadata = parsed
    title = _plain_heading(str(metadata.get("title") or post_id)) or post_id
    subtitle = str(metadata.get("subtitle") or "")
    sections: list[tuple[str, list[str]]] = []
    fence = ""
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        in_code = bool(fence)
        if marker:
            token, info = marker.groups()
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not info.strip():
                fence = ""
        if in_code or marker:
            if not sections:
                sections.append((title, []))
            sections[-1][1].append(line)
        elif line.startswith("# "):
            title = _plain_heading(line[2:]) or title
        elif line.startswith("## "):
            sections.append((_plain_heading(line[3:]), []))
        elif sections:
            sections[-1][1].append(line)
        elif line.strip():
            sections.append((title, [line]))
    slides = [
        Slide(i, heading or title, "\n".join(lines).strip())
        for i, (heading, lines) in enumerate(sections, 1)
    ]
    for slide in slides:
        if len(slide.title) + len(slide.text) > 800:
            print(f"Warning: slide {slide.number} exceeds 800 characters", file=sys.stderr)
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


def _receipt(gate: int, post_id: str, config: EditorialConfig, evidence: Path) -> GateReceipt:
    path = evidence / config.gates.receipts_dir / f"gate{gate}.json"
    try:
        receipt = RECEIPT_ADAPTER.validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GhostApprovalForbiddenError(f"Gate {gate}: missing or invalid receipt") from exc
    if receipt.gate != gate or receipt.post_id != post_id:
        raise GhostApprovalForbiddenError(f"Gate {gate}: receipt gate/post mismatch")
    if receipt.role != config.gates.approver_role:
        raise GhostApprovalForbiddenError(f"Gate {gate}: receipt approver role mismatch")
    policy = config.gates.gate1 if gate == 1 else config.gates.gate2
    validate_excerpt(
        receipt.excerpt, policy.approval_phrase, post_id, config.gates.forbidden_excerpts
    )
    return receipt


def _check_gate(
    gate: int, post: Path, root: Path, config: EditorialConfig, paths: dict[str, Path]
) -> dict[str, Any]:
    post_id = _post_id(post)
    evidence = paths["paths.evidence"] / post_id
    findings = list(StyleChecker.from_config(config, root).scan_file(post))
    findings.extend(EvidenceVerifier(config, root).verify(post, post_id, evidence))
    checklist = EvidenceBundle(PostId(post_id), tuple(findings)).checklist
    if checklist.blocked:
        codes = sorted({f.code for f in checklist.findings if f.state == VerificationState.BLOCK})
        raise GhostApprovalForbiddenError("Gate blocked by BLOCK findings: " + ", ".join(codes))
    first = _receipt(1, post_id, config, evidence)
    if not isinstance(first, Gate1Receipt):
        raise GhostApprovalForbiddenError("Gate 1 receipt required")
    expected = {
        "draft_digest": digest(post, root),
        "sources_digest": digest(evidence / "sources.json", root),
        "factcheck_digest": digest(evidence / "factcheck.json", root),
        "review_digest": digest(evidence / "draft-review.json", root),
    }
    if first.bundle.model_dump() != expected:
        raise GhostApprovalForbiddenError("Gate 1: stale receipt bundle")
    receipt: GateReceipt = first
    actions: list[str] = []
    if gate == 2:
        second = _receipt(2, post_id, config, evidence)
        if not isinstance(second, Gate2Receipt):
            raise GhostApprovalForbiddenError("Gate 2 receipt required")
        actions = second.allowed_actions
        if (
            len(set(actions)) != len(actions)
            or not set(actions) <= set(config.gates.gate2.allowed_actions)
            or not all(mentions(second.excerpt, action) for action in actions)
        ):
            raise GhostApprovalForbiddenError(
                "Gate 2: actions not permitted or absent from excerpt"
            )
        reports = paths.get("paths.reports")
        artifacts = {
            relative_path(file, root): digest(file, root)
            for file in paths["paths.dist"].rglob("*")
            if file.is_file()
            and file.name != ".gitkeep"
            and (reports is None or not file.resolve().is_relative_to(reports))
        }
        expected_second = {
            "draft_digest": expected["draft_digest"],
            "gate1_digest": digest(evidence / config.gates.receipts_dir / "gate1.json", root),
            "artifacts": artifacts,
        }
        if second.bundle.model_dump() != expected_second:
            raise GhostApprovalForbiddenError("Gate 2: stale receipt bundle or distribution kit")
        receipt = second
    decision = GateDecision(gate, PostId(post_id), receipt)
    return {
        "status": "RECEIPT_VALID",
        "gate": decision.gate,
        "post_id": decision.post_id,
        "post": relative_path(post, root),
        "role": receipt.role,
        "timestamp": receipt.timestamp.isoformat(),
        "allowed_actions": actions,
        "bundle": receipt.bundle.model_dump(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="editorial-pipeline")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("target_dir")
    install = sub.add_parser("install-skill", help="Install the editorial-pipeline agent skill")
    install.add_argument("target_dir", help="Agent skills directory receiving editorial-pipeline/")
    install.add_argument("--force", action="store_true", help="Overwrite an existing skill")
    view = sub.add_parser("view", help="Open the offline editorial console")
    view.add_argument("post_id")
    view.add_argument("--serve", action="store_true", help="Serve on localhost until Ctrl+C")
    view.add_argument("--port", type=int, default=8000, help="Local port; 0 selects a free port")
    view.add_argument("--no-browser", action="store_true")
    view.add_argument("--config", default="editorial.toml")
    for name in (
        "status",
        "validate-draft",
        "validate-all",
        "check-gate",
        "verify-facts",
        "build-visual",
        "build-audio",
        "publish",
    ):
        p = sub.add_parser(name)
        if name == "check-gate":
            p.add_argument("gate_num", type=int, choices=(1, 2))
        if name in (
            "validate-draft",
            "check-gate",
            "verify-facts",
            "build-visual",
            "build-audio",
            "publish",
        ):
            p.add_argument("post_target")
        if name == "check-gate":
            p.add_argument("--token", help="Deprecated; a formal receipt is always required")
        if name in ("validate-draft", "validate-all", "verify-facts", "publish", "build-audio"):
            p.add_argument("--json", action="store_true")
        if name == "publish":
            p.add_argument("--target", choices=("dist_archive", "static_site"))
            p.add_argument("--dry-run", action="store_true")
        if name == "build-audio":
            p.add_argument(
                "--provider",
                choices=("notebooklm", "script_only", "tts"),
                help="notebooklm (recommended, editorial standard), script_only, "
                "or tts (deprecated: sub-standard robotic audio)",
            )
            p.add_argument("--format", dest="audio_format", choices=("m4a", "mp3"), default="m4a")
            p.add_argument("--language", default="it", help="NotebookLM audio language")
            p.add_argument("--dry-run", action="store_true")
        if name == "build-visual":
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--html-only", action="store_true")
            p.add_argument("--aspect-ratio", choices=("4:5", "1:1"), default="4:5")
        p.add_argument("--config", default="editorial.toml")
    args = parser.parse_args(argv)
    try:
        if args.command == "view":
            if not 0 <= args.port <= 65535:
                raise ValueError("port must be between 0 and 65535")
            view_root = Path(args.config).resolve().parent
            view_paths = None
            author, register, receipts_dir = "", "", "approvals"
            if Path(args.config).is_file():
                view_root, view_config, view_paths = _config(args.config)
                register = Path(view_config.register_.active).stem
                receipts_dir = view_config.gates.receipts_dir
                profile = view_paths["author.profile"]
                try:
                    profile_text = profile.read_text(encoding="utf-8-sig")
                    profile_lines = profile_text.splitlines()
                    if profile_lines and profile_lines[0].strip() == "---":
                        end = next(
                            index
                            for index in range(1, len(profile_lines))
                            if profile_lines[index].strip() == "---"
                        )
                        profile_text = "\n".join(profile_lines[1:end])
                    profile_data = yaml.safe_load(profile_text)
                    if isinstance(profile_data, dict):
                        profile_author = profile_data.get("author")
                        if isinstance(profile_author, dict):
                            profile_author = profile_author.get("display_name", "")
                        if isinstance(profile_author, str):
                            author = str(profile_author)
                except Exception:  # noqa: BLE001 - optional metadata must fail softly.
                    # Optional author metadata must never prevent opening the console.
                    author = ""
            elif args.config != "editorial.toml":
                raise ValueError("Configuration file not found")
            console = generate_web_hub(
                view_root,
                args.post_id,
                view_paths,
                author=author,
                register=register,
                receipts_dir=receipts_dir,
            )
            if args.serve:
                serve_console(view_root, console, port=args.port, open_browser=not args.no_browser)
            else:
                print(f"Editorial Hub: {console.relative_to(view_root).as_posix()}")
                if not args.no_browser:
                    webbrowser.open(console.as_uri())
            return 0
        if args.command == "install-skill":
            skill = resources.files("editorial_pipeline").joinpath("_skills/editorial-pipeline")
            if not skill.is_dir():
                skill = Path(__file__).resolve().parents[3] / "skills/editorial-pipeline"
            if (
                not skill.joinpath("SKILL.md").is_file()
                or not skill.joinpath("references").is_dir()
            ):
                raise ValueError("Skill resources are missing or incomplete")
            target = Path(args.target_dir) / "editorial-pipeline"
            if target.exists() and not args.force:
                raise ValueError("Skill destination already exists; use --force to overwrite")
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_bytes(skill.joinpath("SKILL.md").read_bytes())
            _copy_resources(skill.joinpath("references"), target / "references")
            print(
                "Skill installed in editorial-pipeline/. Reload your IDE or agent and activate "
                "the editorial-pipeline skill."
            )
            return 0
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
        if args.command == "build-audio":
            if not config.phases.optional.F5:
                raise ValueError("Phase F5 is disabled in editorial.toml")
            post = _discover_posts(posts).get(args.post_target)
            if post is None:
                post = _post(args.post_target, root, posts)
            post_id = _post_id(post)
            output_dir = paths["paths.dist"] / "audio" / post_id
            # Gate 2 excludes reports: audio must remain in the bound artifact inventory.
            reports_dir = paths["paths.reports"]
            if output_dir.is_relative_to(reports_dir) or reports_dir.is_relative_to(output_dir):
                raise ValueError("audio output overlaps excluded reports directory")
            protected = [
                p for key, p in paths.items() if key not in ("paths.dist", "paths.reports")
            ]
            if any(output_dir.is_relative_to(p) or p.is_relative_to(output_dir) for p in protected):
                raise ValueError("audio output overlaps protected project inputs")
            evidence = paths["paths.evidence"] / post_id
            findings = EvidenceVerifier(config, root).verify(post, post_id, evidence)
            if any(f.state == VerificationState.BLOCK for f in findings):
                raise ValueError("Audio requires current validated draft evidence")
            source_records, checks = load_records(evidence)
            sources = [
                {
                    "key": source.key,
                    "claims": [
                        {"text": claim.text, "locator": claim.locator}
                        for claim in checks.claims
                        if claim.source_key == source.key
                    ],
                }
                for source in source_records.sources
            ]
            adapter = args.provider or (
                config.audio.provider if config.audio else config.providers.audio.adapter
            )
            audio_provider: AudioProvider
            if adapter in ("script_only", "none"):
                audio_provider = ScriptOnlyAdapter(root)
            elif adapter == "tts":
                print(f"Warning: DEPRECATED provider 'tts'. {TTS_DEPRECATION}", file=sys.stderr)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    audio_provider = LocalTtsAudioProvider(root)
            elif adapter == "notebooklm":
                audio_config = config.audio or AudioConfig()
                notebooklm = NotebookLMAdapter(
                    root,
                    audio_config.corpus_id,
                    audio_config.corpus_id_env,
                    audio_config.timeout_seconds,
                    language=args.language,
                    audio_format=args.audio_format,
                )
                audio_provider = notebooklm
                if args.provider is None and not args.dry_run:
                    # Configured default: without nlm/notebook fall back safely to a script,
                    # never to sub-standard synthetic audio. Explicit --provider stays strict.
                    try:
                        notebooklm.preflight()
                    except AudioUnavailableError as exc:
                        print(f"Warning: {exc} Falling back to script_only.", file=sys.stderr)
                        audio_provider = ScriptOnlyAdapter(root)
            else:
                raise ValueError("Unsupported audio provider")
            audio_result = audio_provider.build(
                post_id, post.read_text(encoding="utf-8"), sources, output_dir, args.dry_run
            )
            if args.json:
                print(serialize(audio_result.model_dump()))
            else:
                print(f"{audio_result.status}: {audio_result.provider}")
                print(audio_result.script_file or ", ".join(audio_result.audio_files))
            return 0
        if args.command == "publish":
            discovered = _discover_posts(posts)
            post = discovered.get(args.post_target)
            if post is None:
                post = _post(args.post_target, root, posts)
            try:
                approved = _check_gate(2, post, root, config, paths)
            except (OSError, ValueError) as exc:
                raise GhostApprovalForbiddenError("Gate 2: invalid or unreadable bundle") from exc
            publish_target = args.target or (
                config.publishing.target if config.publishing else "dist_archive"
            )
            publisher: PublishAdapter = (
                DistArchivePublisher(root)
                if publish_target == "dist_archive"
                else StaticSitePublisher(root)
            )
            publish_result = publisher.publish(
                _post_id(post),
                post,
                approved["bundle"]["artifacts"],
                approved["allowed_actions"],
                config,
                dry_run=args.dry_run,
            )
            if args.json:
                print(serialize(publish_result.model_dump()))
            else:
                print(f"{publish_result.status}: {publish_result.target}")
                if publish_result.status == "SKIPPED":
                    print(publish_result.details["warning"], file=sys.stderr)
            return 0
        if args.command == "check-gate":
            post = _post(args.post_target, root, posts)
            try:
                gate_result = _check_gate(args.gate_num, post, root, config, paths)
            except (OSError, ValueError) as exc:
                if isinstance(exc, GhostApprovalForbiddenError):
                    raise
                raise GhostApprovalForbiddenError("Gate: invalid or unreadable bundle") from exc
            print(serialize(gate_result))
            return 0
        if args.command in ("verify-facts", "build-visual"):
            post = _post(args.post_target, root, posts)
            post_id = _post_id(post)
            if args.command == "verify-facts":
                evidence = paths["paths.evidence"] / post_id
                adapter = (
                    config.rag.provider if config.rag is not None else config.providers.rag.adapter
                )
                if adapter in ("local", "manual"):
                    findings = EvidenceVerifier(config, root).verify(post, post_id, evidence)
                elif adapter == "none":
                    findings = [
                        Finding(
                            "rag.unavailable",
                            "RAG verification is disabled; evidence cannot be verified",
                            VerificationState.BLOCK,
                        )
                    ]
                else:
                    provider = get_rag_provider(adapter, config, root)
                    findings = EvidenceVerifier(config, root).verify(post, post_id, evidence)
                    try:
                        _, checks = load_records(evidence)
                    except EvidenceError:
                        pass  # EvidenceVerifier already emitted a blocking schema finding.
                    else:
                        findings.extend(
                            provider.verify([claim.text for claim in checks.claims], evidence)
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
            if not config.phases.optional.F4_visual:
                raise ValueError("Phase F4_visual is disabled in editorial.toml")
            spec = _carousel(post, post_id, config.project.name, args.aspect_ratio)
            if args.dry_run:
                files = [f"{post_id}/slide_{slide.number:02d}.html" for slide in spec.slides]
                if not args.html_only:
                    files += [f"{post_id}/slide_{slide.number:02d}.png" for slide in spec.slides]
                    files.append(f"{post_id}/{post_id}_carousel.pdf")
                files.append(f"{post_id}/manifest.json")
                print(
                    serialize(
                        {
                            "post_id": post_id,
                            "dry_run": True,
                            "output_dir": relative_path(paths["paths.dist"] / "social", root),
                            "files": files,
                        }
                    )
                )
                return 0
            builder = get_visual_builder("playwright", config, root)
            if isinstance(builder, PlaywrightVisualBuilder):
                if not (
                    paths["paths.templates"] / "social" / "carousel_slide.html.jinja2"
                ).is_file():
                    builder.template_dir = None
                if args.html_only:
                    builder.rasterize = False
            manifest = builder.build_carousel(spec, paths["paths.dist"] / "social")
            print(serialize(manifest.to_dict()))
            return 0
        checker = StyleChecker.from_config(config, root)
        selected = (
            [_post(args.post_target, root, posts)]
            if args.command == "validate-draft"
            else sorted(
                post for post in _discover_posts(posts).values() if not post.name.startswith("_")
            )
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
    except PostIdCollisionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except GhostApprovalForbiddenError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValidationError as exc:
        for error in exc.errors(include_url=False, include_context=False, include_input=False):
            location = ".".join(str(part) for part in error["loc"]) or "configuration"
            print(_sanitize(f"Error: {location}: {error['msg']}"), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(_sanitize(f"Error: {exc}"), file=sys.stderr)
        return 1
    except AudioUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, RagUnavailableError, VisualBuildError, yaml.YAMLError) as exc:
        print(f"Error: {type(exc).__name__}", file=sys.stderr)
        return 1
