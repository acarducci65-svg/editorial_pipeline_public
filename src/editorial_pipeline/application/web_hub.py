"""Read-only, offline editorial console and loopback preview server.

Generating a console never validates or creates a gate receipt. Links refer to
local assets; keep the project tree together when moving the generated page.
"""

import html as html_lib
import importlib
import json
import posixpath
import re
import webbrowser
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from editorial_pipeline.domain.gates import RECEIPT_ADAPTER

CHANNELS = {
    "linkedin": "LinkedIn",
    "twitter": "Twitter/X",
    "newsletter": "Newsletter",
    "instagram": "Instagram",
}
DEFAULT_TEMPLATE_DIRS = (
    Path(__file__).resolve().parents[1] / "_scaffold/templates/web",
    Path(__file__).resolve().parents[3] / "templates/web",
)


def _contained(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Web console path escapes project directory")
    # Reject aliases too: serving the project must not follow a linked asset.
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError("Web console does not follow symbolic links")
    return resolved


def _text(path: Path) -> str:
    # Lazy import: cli.__init__ also imports the command dispatcher.
    from editorial_pipeline.cli.reports import _sanitize

    return str(_sanitize(path.read_text(encoding="utf-8-sig", errors="replace")))


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(_text(path))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = _text(path)
    if text.startswith("---\n") and "\n---\n" in text:
        header, body = text[4:].split("\n---\n", 1)
        try:
            metadata = yaml.safe_load(header)
        except yaml.YAMLError:
            metadata = {}
        return metadata if isinstance(metadata, dict) else {}, body
    return {}, text


def _channel(label: str) -> str | None:
    label = label.casefold().replace("_", " ").replace("-", " ")
    for key in CHANNELS:
        if key in label or (key == "twitter" and label in ("x", "x thread")):
            return key
    return None


def _social(kit: str, files: list[Path]) -> list[dict[str, str]]:
    copies = dict.fromkeys(CHANNELS, "")
    current: str | None = None
    level = 0
    for line in kit.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            key = _channel(heading[2].strip())
            if key:
                current, level = key, len(heading[1])
                continue
            if len(heading[1]) <= level:
                current = None
        if current:
            copies[current] += line + "\n"
    for file in files:
        if file.suffix.lower() in (".md", ".txt") and (key := _channel(file.stem)):
            copies[key] = _text(file)
    return [
        {"key": key, "label": label, "text": copies[key].strip()} for key, label in CHANNELS.items()
    ]


MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)
DEFAULT_THEME = {
    "palette": "cobalt_tech",
    "accent_color": "#2563eb",
    "background_color": "#f8fafc",
    "ink_color": "#0f172a",
    "font_family": "sans",
}
OUTCOMES = {
    "grounded_primary": ("Dato verificato · riscontro letterale", "ok"),
    "verified_external": ("Dato verificato · riscontro esterno", "ok"),
    "verified": ("Dato verificato", "ok"),
    "grounded_secondary": ("Riscontro su fonte secondaria", "partial"),
    "unsupported": ("Non supportato dalle fonti", "fail"),
    "contradicted": ("Contraddetto dalle fonti", "fail"),
}
SOURCE_TYPES = {
    "institutional_report": "Rapporto istituzionale",
    "institutional_analysis": "Analisi istituzionale",
    "institutional_research": "Ricerca istituzionale",
    "working_paper": "Working paper",
    "research_center_press_release": "Comunicato di centro studi",
    "press_release": "Comunicato stampa",
    "peer_reviewed": "Articolo scientifico",
    "journal_article": "Articolo scientifico",
    "dataset": "Dataset",
    "statistics": "Statistica ufficiale",
    "law": "Atto normativo",
    "regulation": "Atto normativo",
    "news": "Articolo di stampa",
    "interview": "Intervista",
}
ACTIONS = {
    "archive": "Archiviazione nel pacchetto locale",
    "export_markdown": "Esportazione Markdown",
    "static_site": "Pubblicazione su sito statico",
    "publish": "Pubblicazione",
    "social": "Diffusione sui social",
}
FILE_GROUPS = (
    ("dist/published", "Versione pubblicata"),
    ("dist/packages", "Archivio dell'articolo"),
    ("content", "Testo e kit social"),
    ("dist/social", "Social e carosello"),
    ("dist/audio", "Audio"),
    ("evidence", "Fonti, verifiche e ricevute"),
    ("reports", "Report dei gate"),
)
STAGES = (
    ("F1", "Fonti"),
    ("F2", "Bozza"),
    ("F3", "Verifica"),
    ("G1", "Gate 1"),
    ("F4", "Visual e social"),
    ("F5", "Audio"),
    ("G2", "Gate 2"),
)
POST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _when(value: str, timezone: str = "") -> str:
    """Italian, human-readable date (and time when present); raw value on failure."""
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if len(value) <= 10:
        return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"
    suffix = ""
    if moment.tzinfo is not None and timezone:
        try:
            moment = moment.astimezone(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError):
            # Without tz data the browser refines the label (see data-tz).
            suffix = " (UTC)" if moment.utcoffset() == timedelta(0) else ""
    day = f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"
    return f"{day}, ore {moment:%H:%M}{suffix}"


def _safe_href(url: str) -> str | None:
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme in ("http", "https") and parts.netloc:
        return url
    if not parts.scheme and not url.startswith("//") and "\\" not in url:
        return url
    return None


def _inline(text: str, citations: bool) -> str:
    """Escape, then apply a small, safe subset of inline Markdown."""
    stash: list[str] = []

    def keep(fragment: str) -> str:
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    def link(match: re.Match[str]) -> str:
        href = _safe_href(html_lib.unescape(match[2]))
        if href is None:
            return match[1]
        external = href.startswith(("http://", "https://"))
        rel = ' target="_blank" rel="noopener noreferrer"' if external else ""
        return keep(f'<a href="{html_lib.escape(href)}"{rel}>{match[1]}</a>')

    text = html_lib.escape(text.replace("\x00", ""), quote=True)
    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{m[1]}</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
    if citations:

        def cite(match: re.Match[str]) -> str:
            refs = ", ".join(
                f'<a class="cite" href="#fonte-{n}" data-source="{n}">{n}</a>'
                for n in (part.strip() for part in match[1].split(","))
            )
            return f'<sup class="cites">[{refs}]</sup>'

        text = re.sub(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]", cite, text)
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m[1])], text)
    return text


def _slug(text: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:60] or "sezione"
    slug, counter = base, 2
    while slug in used:
        slug, counter = f"{base}-{counter}", counter + 1
    used.add(slug)
    return slug


def render_markdown(
    text: str, *, citations: bool = True, skip_title: bool = True
) -> tuple[str, list[dict[str, str]]]:
    """Render Markdown with untrusted content to escaped HTML.

    Supports headings, paragraphs, lists, block quotes, rules and fenced code.
    Every text fragment is escaped; links keep only http(s) or relative targets.
    Returns the HTML and the table of contents (level-2 headings).
    """
    out: list[str] = []
    toc: list[dict[str, str]] = []
    used: set[str] = set()
    paragraph: list[str] = []
    items: list[str] = []
    list_tag = "ul"
    quote_lines: list[str] = []
    fence: list[str] | None = None
    title_skipped = not skip_title

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph), citations)}</p>")
            paragraph.clear()
        if items:
            body = "".join(f"<li>{_inline(item, citations)}</li>" for item in items)
            out.append(f"<{list_tag}>{body}</{list_tag}>")
            items.clear()
        if quote_lines:
            joined = _inline(" ".join(quote_lines), citations)
            out.append(f"<blockquote><p>{joined}</p></blockquote>")
            quote_lines.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if fence is not None:
            if stripped.startswith(("```", "~~~")):
                out.append(f"<pre><code>{html_lib.escape(chr(10).join(fence))}</code></pre>")
                fence = None
            else:
                fence.append(line)
            continue
        if stripped.startswith(("```", "~~~")):
            flush()
            fence = []
            continue
        if not stripped:
            flush()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped)
        if heading:
            flush()
            if len(heading[1]) == 1 and not title_skipped:
                title_skipped = True
                continue
            level = max(2, len(heading[1]))
            slug = _slug(heading[2], used)
            if level == 2:
                toc.append({"id": slug, "text": re.sub(r"[*_`]", "", heading[2])})
            out.append(f'<h{level} id="{slug}">{_inline(heading[2], citations)}</h{level}>')
            continue
        if re.fullmatch(r"(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}", stripped):
            flush()
            out.append("<hr>")
            continue
        entry = re.match(r"^(?:(?P<b>[-*+•])|\d{1,3}[.)])\s+(?P<text>.+)$", stripped)
        if entry:
            tag = "ul" if entry["b"] else "ol"
            if paragraph or quote_lines or (items and list_tag != tag):
                flush()
            list_tag = tag
            items.append(entry["text"])
            continue
        if stripped.startswith(">"):
            if paragraph or items:
                flush()
            quote_lines.append(stripped.lstrip(">").strip())
            continue
        if items and line[:1].isspace():
            items[-1] += " " + stripped
            continue
        if items or quote_lines:
            flush()
        paragraph.append(stripped)
    if fence is not None:
        out.append(f"<pre><code>{html_lib.escape(chr(10).join(fence))}</code></pre>")
    flush()
    return "\n".join(out), toc


def _theme(theme: dict[str, str] | None) -> dict[str, str]:
    rules = {
        "palette": r"[a-z_]{1,32}",
        "font_family": r"sans|serif",
        "accent_color": r"#[0-9a-fA-F]{6}",
        "background_color": r"#[0-9a-fA-F]{6}",
        "ink_color": r"#[0-9a-fA-F]{6}",
    }
    resolved = dict(DEFAULT_THEME)
    for key, value in (theme or {}).items():
        # Values are written into CSS: anything unexpected keeps the default.
        if key in rules and isinstance(value, str) and re.fullmatch(rules[key], value):
            resolved[key] = value
    return resolved


def _size(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB".replace(".", ",")
    return f"{size / 1024 / 1024:.1f} MB".replace(".", ",")


def _source_links(source: dict[str, Any], local: str | None) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in ("url", "pdf", "html", "open_access_url"):
        value = source.get(key)
        if not isinstance(value, str) or not value or value in seen:
            continue
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue
        seen.add(value)
        is_pdf = key == "pdf" or parts.path.casefold().endswith(".pdf")
        links.append(
            {
                "url": value,
                "label": "Scarica il PDF" if is_pdf else "Apri la pagina web",
                "kind": "pdf" if is_pdf else "html",
                "host": parts.netloc.removeprefix("www."),
            }
        )
    doi = source.get("doi")
    if isinstance(doi, str) and re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        links.append(
            {
                "url": "https://doi.org/" + quote(doi, safe="/.:;()-_"),
                "label": "Scheda DOI",
                "kind": "doi",
                "host": "doi.org",
            }
        )
    if local:
        links.append({"url": local, "label": "Copia locale", "kind": "local", "host": "archivio"})
    return links


def _gate(
    root: Path,
    reports: Path,
    evidence: Path,
    receipts_dir: str,
    post_id: str,
    number: int,
    existing: Callable[[Path], bool],
    timezone: str,
) -> dict[str, Any]:
    status, role, timestamp = "Non disponibile", "", ""
    actions: list[str] = []
    report = _contained(root, reports / "gates" / post_id / f"gate{number}.json")
    receipt = _contained(root, evidence / receipts_dir / f"gate{number}.json")
    if existing(report):
        data = _json(report)
        if data.get("post_id") == post_id and data.get("gate") == number:
            status = str(data.get("status", "Non rivalidato"))
            role, timestamp = str(data.get("role", "")), str(data.get("timestamp", ""))
            raw = data.get("allowed_actions")
            actions = [str(a) for a in raw] if isinstance(raw, list) else []
    elif existing(receipt):
        status = "Non rivalidato"
        try:
            record = RECEIPT_ADAPTER.validate_json(receipt.read_text(encoding="utf-8"))
            if record.post_id == post_id and record.gate == number:
                status = "Ricevuta presente"
                role, timestamp = record.role, record.timestamp.isoformat()
                actions = list(getattr(record, "allowed_actions", []))
        except ValueError:
            pass
    return {
        "number": number,
        "name": "Bozza" if number == 1 else "Pubblicazione",
        "status": status,
        "label": "Ricevuta valida" if status == "RECEIPT_VALID" else status,
        "registered": status in ("RECEIPT_VALID", "Ricevuta presente"),
        "role": role,
        "timestamp": timestamp,
        "when": _when(timestamp, timezone),
        "actions": [{"code": a, "label": ACTIONS.get(a, a.replace("_", " "))} for a in actions],
    }


def _review_score(review: dict[str, Any]) -> str:
    """De-aizing score, or the share of passed style checks when no score is stored."""
    score = review.get("de_aizing_score", review.get("score"))
    if score is not None:
        return str(score)
    items = review.get("items")
    if isinstance(items, dict) and items:
        passed = sum(str(value).casefold() == "pass" for value in items.values())
        return f"{passed}/{len(items)} controlli superati"
    return "Non disponibile"


def _stages(flags: tuple[bool, ...]) -> list[dict[str, Any]]:
    return [
        {"code": code, "label": label, "done": flag}
        for (code, label), flag in zip(STAGES, flags, strict=True)
    ]


def _environment(template_dir: Path) -> Any:
    try:
        jinja = importlib.import_module("jinja2")
    except ImportError as exc:
        raise ValueError("Web console requires Jinja2; install editorial-pipeline[social]") from exc
    return jinja.Environment(
        loader=jinja.FileSystemLoader(str(template_dir)),
        autoescape=True,
        undefined=jinja.StrictUndefined,
    )


def _template_dir(name: str) -> Path | None:
    return next((p for p in DEFAULT_TEMPLATE_DIRS if (p / name).is_file()), None)


def _build(
    root: Path,
    post_id: str,
    paths: dict[str, Path] | None,
    options: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    from editorial_pipeline.cli.reports import _sanitize

    if not POST_ID.fullmatch(post_id):
        raise ValueError("Invalid post_id")
    timezone = str(options["timezone"])
    root = root.resolve()
    locations = {
        "paths.content": root / "content/posts",
        "paths.evidence": root / "evidence",
        "paths.dist": root / "dist",
        "paths.reports": root / "reports",
    }
    locations.update(paths or {})
    for path in locations.values():
        _contained(root, path)
    content = locations["paths.content"]
    dist = locations["paths.dist"]
    post_dir = _contained(root, content / post_id)
    evidence = _contained(root, locations["paths.evidence"] / post_id)
    published = _contained(root, dist / "published" / post_id)
    social_dir = _contained(root, dist / "social" / post_id)
    audio_dir = _contained(root, dist / "audio" / post_id)
    output = _contained(root, dist / "web" / f"{post_id}.html")
    files: set[Path] = set()

    def scan(directory: Path) -> list[Path]:
        found = []
        for file in sorted(directory.rglob("*")):
            _contained(root, file)
            if file.is_file() and file.name != ".gitkeep":
                found.append(file)
                files.add(file)
        return found

    def existing(path: Path) -> bool:
        _contained(root, path)
        if path.is_file():
            files.add(path)
            return True
        return False

    draft = post_dir / "draft.md"
    if not existing(draft):
        candidates = [
            file
            for file in content.glob("*.md")
            if file.stem == post_id or file.stem.startswith(post_id + "_")
        ]
        if len(candidates) > 1:
            raise ValueError("Ambiguous post_id")
        draft = candidates[0] if candidates else draft
    has_draft = existing(draft)
    published_files = scan(published)
    social_files = scan(social_dir)
    audio_files = scan(audio_dir)
    evidence_files = scan(evidence)
    kit = post_dir / "social_kit.md"
    has_kit = existing(kit)
    if not (
        has_draft or has_kit or published_files or social_files or audio_files or evidence_files
    ):
        raise ValueError("post not found in project assets")
    metadata, body = _markdown(draft) if has_draft else ({}, "")
    heading = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = str(metadata.get("title") or (heading[1] if heading else post_id))
    kit_text = _text(kit) if has_kit else ""
    podcast = next((f for f in audio_files if f.name in ("podcast.m4a", "podcast.mp3")), None)
    script_file = next(
        (audio_dir / n for n in ("script.txt", "podcast_script.md") if existing(audio_dir / n)),
        None,
    )
    script_html = ""
    if script_file is not None:
        script_html = render_markdown(_markdown(script_file)[1], citations=False, skip_title=False)[
            0
        ]
    article = next(
        (f for f in published_files if f.suffix.lower() in (".md", ".txt", ".html")), None
    )
    article_text = ""
    if article is not None:
        article_text = _markdown(article)[1]
        if article.suffix.lower() == ".html":
            # Published HTML is shown as text: markup read from disk is never trusted.
            article_text = re.sub(r"<[^>]+>", " ", article_text)
    for package in (dist / "packages" / f"{post_id}.tar.gz", dist / "packages" / f"{post_id}.zip"):
        existing(package)

    def url(file: Path) -> str:
        # Same-project relative URLs work both under file:// and localhost.
        relative = posixpath.relpath(
            file.relative_to(root).as_posix(), output.parent.relative_to(root).as_posix()
        )
        return quote(relative, safe="/.-_")

    slide_files = [
        f
        for f in social_files
        if f.suffix.lower() in (".html", ".png", ".jpg", ".jpeg", ".webp")
        and ("carousel" in f.relative_to(social_dir).parts or f.stem.startswith("slide_"))
    ]
    # Rasterised slides and HTML slides represent the same slide, not two slides.
    slides_by_name: dict[str, Path] = {}
    for file in slide_files:
        previous = slides_by_name.get(file.stem)
        if previous is None or previous.suffix == ".html":
            slides_by_name[file.stem] = file
    slides = [
        {
            "name": file.name,
            "url": url(file),
            "html": _text(file) if file.suffix.lower() == ".html" else "",
        }
        for _, file in sorted(slides_by_name.items())
    ]
    raw_sources = _json(evidence / "sources.json").get("sources", [])
    raw_claims = _json(evidence / "factcheck.json").get("claims", [])
    source_list = (
        [s for s in raw_sources if isinstance(s, dict)] if isinstance(raw_sources, list) else []
    )
    claims = [c for c in raw_claims if isinstance(c, dict)] if isinstance(raw_claims, list) else []
    review = _json(evidence / "draft-review.json")
    sources: list[dict[str, Any]] = []
    for number, source in enumerate(source_list, 1):
        local = None
        local_copy = source.get("local_copy")
        if isinstance(local_copy, str) and local_copy:
            try:
                candidate = _contained(root, root / local_copy.replace("\\", "/"))
                local = url(candidate) if candidate.is_file() else None
            except ValueError:
                local = None
        primary = source.get("primary")
        kind = str(source.get("type", ""))
        access = str(source.get("access", "")).casefold()
        sources.append(
            {
                "number": number,
                "key": str(source.get("key", number)),
                "title": str(source.get("title", "")) or str(source.get("key", number)),
                "author": str(source.get("author", "")),
                "publisher": str(source.get("publisher", "")),
                "published": str(source.get("published", "")),
                "accessed": _when(str(source.get("accessed", ""))),
                "type": SOURCE_TYPES.get(kind, kind.replace("_", " ").capitalize()),
                "primary": primary is True,
                "primary_label": (
                    "Fonte ufficiale primaria"
                    if primary is True
                    else "Fonte secondaria"
                    if primary is False
                    else "Tipologia non dichiarata"
                ),
                "access": (
                    "Accesso libero"
                    if access in ("open", "free", "libero", "open_access")
                    else "Accesso riservato"
                    if access in ("paywall", "restricted", "riservato")
                    else ""
                ),
                "description": str(source.get("description", "")),
                "links": _source_links(source, local),
                "claims": [],
            }
        )
    by_key = {s["key"]: s for s in sources}
    orphans: list[dict[str, Any]] = []
    verified = 0
    for index, claim in enumerate(claims, 1):
        outcome = str(claim.get("outcome", ""))
        label, tone = OUTCOMES.get(outcome, (outcome or "Non disponibile", "neutral"))
        verified += tone == "ok"
        item = {
            "id": str(claim.get("id", index)),
            "text": str(claim.get("text", "")),
            "quote": str(claim.get("quote", "")),
            "locator": str(claim.get("locator", "")),
            "source_key": str(claim.get("source_key", "")),
            "label": label,
            "tone": tone,
        }
        target = by_key.get(item["source_key"])
        (target["claims"] if target else orphans).append(item)
    reports = locations["paths.reports"]
    receipts_dir = str(options["receipts_dir"])
    gates = [
        _gate(root, reports, evidence, receipts_dir, post_id, n, existing, timezone) for n in (1, 2)
    ]
    article_html, toc = render_markdown(article_text or body)
    draft_html = render_markdown(body)[0] if article_text and body else ""
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", article_html)))
    date = str(metadata.get("date", ""))
    author = str(metadata.get("author") or options["author"])
    subtitle = str(metadata.get("subtitle", ""))
    front = {"title": title, "description": subtitle, "date": date, "author": author}
    front_yaml = yaml.safe_dump(
        {k: v for k, v in front.items() if v}, allow_unicode=True, sort_keys=False
    ).strip()
    export_body = re.sub(r"\A\s*# .+\n+", "", article_text or body, count=1).strip()
    groups: dict[str, list[dict[str, str]]] = {}
    for file in sorted(files):
        relative = file.relative_to(root).as_posix()
        group = next(
            (label for prefix, label in FILE_GROUPS if relative.startswith(prefix + "/")),
            "Altri file",
        )
        groups.setdefault(group, []).append(
            {"name": relative, "file": file.name, "url": url(file), "size": _size(file)}
        )
    order = [label for _, label in FILE_GROUPS] + ["Altri file"]
    archive = next(
        (
            {"name": f.name, "url": url(f), "size": _size(f)}
            for f in sorted(files)
            if f.parent == dist / "packages"
        ),
        None,
    )
    stages = _stages(
        (
            (evidence / "sources.json").is_file(),
            has_draft,
            (evidence / "factcheck.json").is_file(),
            gates[0]["registered"],
            bool(social_files) or has_kit,
            bool(audio_files),
            gates[1]["registered"],
        )
    )
    template_dir = _template_dir("console.html.jinja2")
    if template_dir is None:
        raise ValueError("Web console template not found")
    html = (
        _environment(template_dir)
        .get_template("console.html.jinja2")
        .render(
            post_id=post_id,
            title=title,
            subtitle=subtitle,
            author=author,
            date=date,
            date_label=_when(date),
            register=str(metadata.get("register") or options["register"]),
            newsroom=str(options["newsroom"]),
            theme=_theme(options["theme"]),
            timezone=timezone,
            gates=gates,
            stages=stages,
            social=_social(kit_text, social_files),
            article_html=article_html,
            draft_html=draft_html,
            article_version="Versione pubblicata" if article_text else "Bozza di lavoro",
            toc=toc,
            reading_minutes=max(1, round(words / 200)) if words else 0,
            markdown_export=f"---\n{front_yaml}\n---\n\n{export_body}\n",
            podcast=url(podcast) if podcast else "",
            podcast_format=podcast.suffix.lstrip(".").upper() if podcast else "",
            podcast_size=_size(podcast) if podcast else "",
            script_html=script_html,
            script_name=script_file.name if script_file else "",
            script_url=url(script_file) if script_file else "",
            slides=slides,
            sources=sources,
            orphans=orphans,
            claims_total=len(claims),
            claims_verified=verified,
            score=_review_score(review),
            groups=[{"label": g, "files": groups[g]} for g in order if g in groups],
            package=archive,
            pdfs=[
                {"name": f.name, "url": url(f)} for f in social_files if f.suffix.lower() == ".pdf"
            ],
            index_url="index.html" if (output.parent / "index.html").is_file() else "",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(_sanitize(html)), encoding="utf-8", newline="\n")
    if published_files:
        state = "Pubblicato"
    elif gates[1]["registered"]:
        state = "Pronto per la pubblicazione"
    elif gates[0]["registered"]:
        state = "In produzione"
    else:
        state = "In lavorazione"
    summary = {
        "post_id": post_id,
        "title": title,
        "subtitle": subtitle,
        "date": date,
        "date_label": _when(date),
        "author": author,
        "url": url(output),
        "stages": stages,
        "state": state,
        "error": "",
    }
    return output, summary


def generate_web_hub(
    root: Path,
    post_id: str,
    paths: dict[str, Path] | None = None,
    *,
    author: str = "",
    register: str = "",
    receipts_dir: str = "approvals",
    newsroom: str = "",
    theme: dict[str, str] | None = None,
    timezone: str = "",
) -> Path:
    """Render available assets without modifying sources, receipts or publication.

    Jinja2 is provided by the existing ``social`` extra. Missing optional assets
    are displayed explicitly; unknown posts and unsafe paths fail closed.
    ``theme`` takes the values of ``ThemeConfig.resolved()``; invalid values
    fall back to the default Modern Tech palette.
    """
    options: dict[str, Any] = {
        "author": author,
        "register": register,
        "receipts_dir": receipts_dir,
        "newsroom": newsroom,
        "theme": theme,
        "timezone": timezone,
    }
    return _build(root, post_id, paths, options)[0]


def discover_post_ids(content: Path) -> list[str]:
    """Post identifiers under the content directory, in stable order.

    A post is either ``<id>/draft.md`` or a flat ``<id>.md`` /
    ``<id>_<slug>.md`` file (numbered ids such as ``post_01_title``). Sidecar
    files with extra dots (``<id>.social_kit.md``) and ``_``-prefixed files are
    not posts.
    """
    found: set[str] = set()
    if not content.is_dir():
        return []
    for entry in content.iterdir():
        if entry.is_dir() and (entry / "draft.md").is_file():
            found.add(entry.name)
        elif entry.is_file() and entry.suffix == ".md" and "." not in entry.stem:
            parts = entry.stem.split("_")
            found.add("_".join(parts[:2]) if len(parts) > 2 and parts[1].isdigit() else entry.stem)
    return sorted(p for p in found if POST_ID.fullmatch(p) and not p.startswith("_"))


def generate_index(
    root: Path,
    paths: dict[str, Path] | None = None,
    *,
    author: str = "",
    register: str = "",
    receipts_dir: str = "approvals",
    newsroom: str = "",
    theme: dict[str, str] | None = None,
    timezone: str = "",
) -> Path:
    """Regenerate every post console and the newsroom index ``dist/web/index.html``.

    The index lists each post with its lifecycle (F1-F5, Gate 1, Gate 2) and a
    link to its console. Posts whose assets cannot be read are listed with the
    reason instead of aborting the whole catalogue.
    """
    from editorial_pipeline.cli.reports import _sanitize

    root = root.resolve()
    content = _contained(root, (paths or {}).get("paths.content", root / "content/posts"))
    dist = _contained(root, (paths or {}).get("paths.dist", root / "dist"))
    output = _contained(root, dist / "web" / "index.html")
    template_dir = _template_dir("index.html.jinja2")
    if template_dir is None:
        raise ValueError("Newsroom index template not found")
    env = _environment(template_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file():
        # Placeholder first, so every console renders its link back to the index.
        output.write_text("", encoding="utf-8")
    options: dict[str, Any] = {
        "author": author,
        "register": register,
        "receipts_dir": receipts_dir,
        "newsroom": newsroom,
        "theme": theme,
        "timezone": timezone,
    }
    posts: list[dict[str, Any]] = []
    for post_id in discover_post_ids(content):
        try:
            posts.append(_build(root, post_id, paths, options)[1])
        except ValueError as exc:
            posts.append(
                {
                    "post_id": post_id,
                    "title": post_id,
                    "date": "",
                    "error": str(_sanitize(str(exc))),
                }
            )
    posts.sort(key=lambda p: (str(p["date"]), str(p["post_id"])), reverse=True)
    html = env.get_template("index.html.jinja2").render(
        newsroom=newsroom,
        theme=_theme(theme),
        posts=posts,
        stages=[{"code": code, "label": label} for code, label in STAGES],
    )
    output.write_text(str(_sanitize(html)), encoding="utf-8", newline="\n")
    return output


class _Links(HTMLParser):
    def __init__(self, root: Path, page: Path, dist: Path | None = None) -> None:
        super().__init__()
        self.root, self.page = root.resolve(), page
        self.dist = _contained(self.root, dist or root / "dist")
        if not self.is_public(page.resolve()):
            raise ValueError("Console must be a public file inside dist")
        self.allowed = {page.resolve()}

    def is_public(self, path: Path) -> bool:
        if not path.is_relative_to(self.root) or not path.is_relative_to(self.dist):
            return False
        parts = {p.lower() for p in path.relative_to(self.dist).parts}
        return (
            not parts.intersection({"src", "config", "content", "evidence", "reports", "manifests"})
            and not any(p.startswith(".") for p in parts)
            and "manifest" not in path.name.lower()
            and path.suffix.lower()
            in {
                ".html",
                ".css",
                ".js",
                ".md",
                ".txt",
                ".m4a",
                ".mp3",
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".gif",
                ".zip",
                ".gz",
                ".wav",
                ".mp4",
            }
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if (
                key in ("href", "src")
                and value
                and not urlsplit(value).scheme
                and not urlsplit(value).netloc
            ):
                path = (self.page.parent / unquote(urlsplit(value).path)).resolve()
                if self.is_public(path):
                    self.allowed.add(path)


def serve_console(
    root: Path,
    page: Path,
    *,
    port: int = 8000,
    open_browser: bool = True,
    dist: Path | None = None,
) -> None:
    """Serve the console and linked assets on loopback until Ctrl+C.

    Configuration, unrelated articles and directory listings are not served.
    Port zero asks the OS for a free port; occupied explicit ports fail normally.
    """
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    root = root.resolve()
    page = _contained(root, page)
    links = _Links(root, page, dist)
    links.feed(page.read_text(encoding="utf-8"))
    # The newsroom index links to post consoles: serve their assets as well.
    pending = [p for p in links.allowed if p.suffix == ".html" and p.parent == page.parent]
    visited = {page.resolve()}
    while pending:
        linked = pending.pop()
        if linked in visited or not linked.is_file():
            continue
        visited.add(linked)
        links.page = linked
        before = set(links.allowed)
        links.feed(linked.read_text(encoding="utf-8"))
        pending.extend(
            p for p in links.allowed - before if p.suffix == ".html" and p.parent == page.parent
        )

    class Handler(SimpleHTTPRequestHandler):
        def send_head(self) -> Any:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or not re.fullmatch(
                r"(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?", hosts[0], re.IGNORECASE
            ):
                self.send_error(403)
                return None
            path = Path(self.translate_path(self.path))
            try:
                safe = _contained(root, path)
            except ValueError:
                self.send_error(403)
                return None
            if safe not in links.allowed or not links.is_public(safe) or not safe.is_file():
                self.send_error(404)
                return None
            return super().send_head()

        def log_message(self, format: str, *args: Any) -> None:
            # Requests can contain arbitrary text: keep preview logs private.
            return

    with ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(root))) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}/{quote(page.relative_to(root).as_posix())}"
        print(f"Editorial Hub: {url} (Ctrl+C per terminare)")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
