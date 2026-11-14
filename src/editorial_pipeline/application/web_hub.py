"""Read-only, offline editorial console and loopback preview server.

Generating a console never validates or creates a gate receipt. Links refer to
local assets; keep the project tree together when moving the generated page.
"""

import importlib
import json
import posixpath
import re
import webbrowser
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

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


def generate_web_hub(
    root: Path,
    post_id: str,
    paths: dict[str, Path] | None = None,
    *,
    author: str = "",
    register: str = "",
    receipts_dir: str = "approvals",
) -> Path:
    """Render available assets without modifying sources, receipts or publication.

    Jinja2 is provided by the existing ``social`` extra. Missing optional assets
    are displayed explicitly; unknown posts and unsafe paths fail closed.
    """
    from editorial_pipeline.cli.reports import _sanitize

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", post_id):
        raise ValueError("Invalid post_id")
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
    script = audio_dir / "script.txt"
    script_text = _text(script) if existing(script) else ""
    article = next(
        (f for f in published_files if f.suffix.lower() in (".md", ".txt", ".html")), None
    )
    article_text = _text(article) if article else ""
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
    sources = _json(evidence / "sources.json").get("sources", [])
    claims = _json(evidence / "factcheck.json").get("claims", [])
    review = _json(evidence / "draft-review.json")
    gates = []
    for number in (1, 2):
        status, role, timestamp = "Non disponibile", "", ""
        report = _contained(
            root, locations["paths.reports"] / "gates" / post_id / f"gate{number}.json"
        )
        receipt = _contained(root, evidence / receipts_dir / f"gate{number}.json")
        if existing(report):
            data = _json(report)
            if data.get("post_id") == post_id and data.get("gate") == number:
                status = str(data.get("status", "Non rivalidato"))
                role, timestamp = str(data.get("role", "")), str(data.get("timestamp", ""))
        elif existing(receipt):
            status = "Non rivalidato"
            try:
                record = RECEIPT_ADAPTER.validate_json(receipt.read_text(encoding="utf-8"))
                if record.post_id == post_id and record.gate == number:
                    status = "Ricevuta presente"
                    role, timestamp = record.role, record.timestamp.isoformat()
            except ValueError:
                pass
        gates.append({"number": number, "status": status, "role": role, "timestamp": timestamp})
    template_dir = next(
        (p for p in DEFAULT_TEMPLATE_DIRS if (p / "console.html.jinja2").is_file()), None
    )
    if template_dir is None:
        raise ValueError("Web console template not found")
    try:
        jinja = importlib.import_module("jinja2")
    except ImportError as exc:
        raise ValueError("Web console requires Jinja2; install editorial-pipeline[social]") from exc
    env = jinja.Environment(
        loader=jinja.FileSystemLoader(str(template_dir)),
        autoescape=True,
        undefined=jinja.StrictUndefined,
    )
    html = env.get_template("console.html.jinja2").render(
        post_id=post_id,
        title=title,
        subtitle=str(metadata.get("subtitle", "")),
        author=str(metadata.get("author") or author),
        date=str(metadata.get("date", "")),
        register=str(metadata.get("register") or register),
        gates=gates,
        social=_social(kit_text, social_files),
        draft=body,
        article=article_text,
        podcast=url(podcast) if podcast else "",
        script=script_text,
        slides=slides,
        sources=[s for s in sources if isinstance(s, dict)] if isinstance(sources, list) else [],
        claims=[c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else [],
        score=review.get("de_aizing_score", review.get("score", "Non disponibile")),
        downloads=[{"name": f.relative_to(root).as_posix(), "url": url(f)} for f in sorted(files)],
        pdfs=[{"name": f.name, "url": url(f)} for f in social_files if f.suffix.lower() == ".pdf"],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(_sanitize(html)), encoding="utf-8")
    return output


class _Links(HTMLParser):
    def __init__(self, root: Path, page: Path) -> None:
        super().__init__()
        self.root, self.page = root, page
        self.allowed = {page.resolve()}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in ("href", "src") and value and not urlsplit(value).scheme:
                path = (self.page.parent / unquote(urlsplit(value).path)).resolve()
                if path.is_relative_to(self.root):
                    self.allowed.add(path)


def serve_console(root: Path, page: Path, *, port: int = 8000, open_browser: bool = True) -> None:
    """Serve the console and linked assets on loopback until Ctrl+C.

    Configuration, unrelated articles and directory listings are not served.
    Port zero asks the OS for a free port; occupied explicit ports fail normally.
    """
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    root = root.resolve()
    page = _contained(root, page)
    links = _Links(root, page)
    links.feed(page.read_text(encoding="utf-8"))

    class Handler(SimpleHTTPRequestHandler):
        def send_head(self) -> Any:
            path = Path(self.translate_path(self.path))
            try:
                safe = _contained(root, path)
            except ValueError:
                self.send_error(403)
                return None
            if safe not in links.allowed or not safe.is_file():
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
