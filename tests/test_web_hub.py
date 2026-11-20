"""Offline editorial console behavior and CLI integration."""

import importlib
import json
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from editorial_pipeline.application.web_hub import generate_web_hub, serve_console
from editorial_pipeline.cli.commands import main


def put(root: Path, name: str, text: str = "sample") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_complete_console(tmp_path: Path) -> None:
    put(
        tmp_path,
        "content/posts/demo/draft.md",
        "---\ntitle: Test article\nauthor: Example Editor\nsubtitle: A subtitle\ndate: 2026-11-14\nregister: tech\n---\n# Draft\nBody",
    )
    put(
        tmp_path,
        "content/posts/demo/social_kit.md",
        "## LinkedIn\nProfessional copy\n## Twitter/X\nThread copy\n## Newsletter\nDigest copy\n## Instagram\nCaption copy",
    )
    put(tmp_path, "dist/published/demo/article.md", "Published body")
    put(tmp_path, "dist/social/demo/carousel/slide_01.html", "<h1>Slide</h1>")
    put(tmp_path, "dist/social/demo/carousel/slide_02.png")
    put(tmp_path, "dist/social/demo/carousel/deck.pdf")
    put(tmp_path, "dist/audio/demo/podcast.m4a")
    put(tmp_path, "dist/audio/demo/script.txt", "Podcast script")
    put(
        tmp_path,
        "evidence/demo/sources.json",
        json.dumps(
            {
                "sources": [
                    {"key": "s1", "title": "Primary source", "url": "https://example.com/source"}
                ]
            }
        ),
    )
    put(
        tmp_path,
        "evidence/demo/factcheck.json",
        json.dumps(
            {
                "claims": [
                    {
                        "source_key": "s1",
                        "text": "Claim text",
                        "outcome": "verified",
                        "locator": "p. 2",
                    }
                ]
            }
        ),
    )
    put(tmp_path, "evidence/demo/draft-review.json", '{"de_aizing_score": 92}')
    put(
        tmp_path,
        "reports/gates/demo/gate1.json",
        '{"status":"RECEIPT_VALID","gate":1,"post_id":"demo","role":"Direttore","timestamp":"2026-11-14"}',
    )
    output = generate_web_hub(tmp_path, "demo")
    assert output == tmp_path / "dist/web/demo.html"
    html = output.read_text(encoding="utf-8")
    for expected in (
        "Test article",
        "Example Editor",
        "A subtitle",
        "2026-11-14",
        "tech",
        "Professional copy",
        "Thread copy",
        "Digest copy",
        "Caption copy",
        "Published body",
        "Podcast script",
        "Primary source",
        "Claim text",
        "p. 2",
        "92",
        "RECEIPT_VALID",
        "navigator.clipboard.writeText",
        "Copiato!",
        "touchstart",
        "<audio controls",
        "download",
        "deck.pdf",
    ):
        assert expected in html
    assert "../audio/demo/podcast.m4a" in html
    assert str(tmp_path) not in html
    assert "<script src=" not in html
    assert 'sandbox=""' in html
    assert "non rivalidato" in html


@pytest.mark.parametrize("audio", [False, True])
def test_partial_console(tmp_path: Path, audio: bool) -> None:
    put(tmp_path, "content/posts/demo/draft.md", "# Minimal draft\n<script>alert('x')</script>")
    if audio:
        put(tmp_path, "dist/audio/demo/podcast.mp3")
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    assert "Minimal draft" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html
    assert ("<audio controls" in html) == audio
    assert "Non disponibile" in html
    assert "Approvato" not in html


@pytest.mark.parametrize("post_id", ["../outside", "a/b", "a\\b", "", ".", ".."])
def test_unsafe_post_id(tmp_path: Path, post_id: str) -> None:
    with pytest.raises(ValueError, match="post_id"):
        generate_web_hub(tmp_path, post_id)


def test_missing_post(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        generate_web_hub(tmp_path, "missing")


def test_flat_posts_and_existing_carousel(tmp_path: Path) -> None:
    put(tmp_path, "content/posts/post_01_long_title.md", "# Flat article")
    put(tmp_path, "dist/social/post_01/slide_01.html", "<p>Slide</p>")
    put(tmp_path, "dist/social/post_01/linkedin.txt", "File copy")
    put(tmp_path, "dist/packages/post_01.tar.gz")
    put(tmp_path, "evidence/post_01/sources.json", "invalid JSON")
    put(tmp_path, "evidence/post_01/approvals/gate1.json", '{"status":"approved"}')
    html = generate_web_hub(tmp_path, "post_01").read_text(encoding="utf-8")
    assert "Flat article" in html
    assert "slide_01.html" in html
    assert "File copy" in html
    assert "post_01.tar.gz" in html
    assert "Non rivalidato" in html
    assert "approved" not in html


@pytest.mark.parametrize("filename", ["post_01.md", "post_01_long_title.md"])
def test_nested_draft_discovery(tmp_path: Path, filename: str) -> None:
    put(
        tmp_path,
        f"content/posts/nested/{filename}",
        "---\ntitle: Nested article title\n---\n# Draft heading\n\nNested article body.",
    )
    put(tmp_path, "evidence/post_01/sources.json", '{"sources": []}')

    output = generate_web_hub(tmp_path, "post_01", paths={"paths.content": tmp_path / "content"})
    html = output.read_text(encoding="utf-8")

    assert "Nested article title" in html
    assert "<p>Nested article body.</p>" in html
    assert "Testo non disponibile" not in html


def test_cli_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    put(tmp_path, "content/posts/demo/draft.md", "# CLI article")
    browser = MagicMock()
    monkeypatch.setattr("editorial_pipeline.application.web_hub.webbrowser.open", browser)
    assert main(["view", "demo", "--no-browser"]) == 0
    browser.assert_not_called()
    assert "dist/web/demo.html" in capsys.readouterr().out
    assert main(["view", "demo"]) == 0
    browser.assert_called_once_with((tmp_path / "dist/web/demo.html").as_uri())


def test_cli_serve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    put(tmp_path, "content/posts/demo/draft.md", "# CLI article")
    server = MagicMock()
    monkeypatch.setattr("editorial_pipeline.cli.commands.serve_console", server)
    assert main(["view", "demo", "--serve", "--port", "8123", "--no-browser"]) == 0
    assert server.call_args.kwargs == {"port": 8123, "open_browser": False}


def test_server_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    page = put(tmp_path, "dist/web/demo.html", '<a href="../audio/demo/podcast.mp3">audio</a>')
    server = MagicMock()
    server.__enter__.return_value = server
    server.server_address = ("127.0.0.1", 8123)
    server.serve_forever.side_effect = KeyboardInterrupt
    factory = MagicMock(return_value=server)
    browser = MagicMock()
    monkeypatch.setattr("editorial_pipeline.application.web_hub.ThreadingHTTPServer", factory)
    monkeypatch.setattr("editorial_pipeline.application.web_hub.webbrowser.open", browser)
    serve_console(tmp_path, page, port=8123)
    assert factory.call_args.args[0] == ("127.0.0.1", 8123)
    browser.assert_called_once_with("http://127.0.0.1:8123/dist/web/demo.html")
    assert "http://127.0.0.1:8123" in capsys.readouterr().out
    server.__exit__.assert_called_once()


def test_real_http_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = put(
        tmp_path,
        "dist/web/demo.html",
        '<a href="../audio/demo/podcast.mp3">audio</a><a href="../../editorial.toml">private</a><a href="../manifest.json">manifest</a><a href="../src/code.py">code</a>',
    )
    put(tmp_path, "dist/audio/demo/podcast.mp3", "audio bytes")
    put(tmp_path, "dist/manifest.json", "private manifest")
    put(tmp_path, "dist/src/code.py", "private source")
    put(tmp_path, "editorial.toml", "private configuration")

    class ProbeServer(ThreadingHTTPServer):
        def serve_forever(self, poll_interval: float = 0.5) -> None:
            worker = threading.Thread(target=super().serve_forever, kwargs={"poll_interval": 0.01})
            worker.start()
            base = f"http://127.0.0.1:{self.server_address[1]}"
            try:
                with urlopen(base + "/dist/web/demo.html", timeout=5) as response:
                    assert response.status == 200
                with urlopen(base + "/dist/audio/demo/podcast.mp3", timeout=5) as response:
                    assert response.read() == b"audio bytes"
                for path in (
                    "/editorial.toml",
                    "/",
                    "/dist/web/",
                    "/../editorial.toml",
                    "/dist/manifest.json",
                    "/dist/src/code.py",
                ):
                    with pytest.raises(HTTPError) as exc:
                        urlopen(base + path, timeout=5)
                    assert exc.value.code == 404
                from urllib.request import Request

                for host in (
                    "attacker.example",
                    "localhost.attacker.example",
                    "127.0.0.1.attacker.example",
                ):
                    with pytest.raises(HTTPError) as exc:
                        urlopen(
                            Request(base + "/dist/web/demo.html", headers={"Host": host}), timeout=5
                        )
                    assert exc.value.code == 403
                with urlopen(
                    Request(base + "/dist/web/demo.html", headers={"Host": "localhost"}), timeout=5
                ) as response:
                    assert response.status == 200
            finally:
                self.shutdown()
                worker.join(timeout=5)
            raise KeyboardInterrupt

    monkeypatch.setattr("editorial_pipeline.application.web_hub.ThreadingHTTPServer", ProbeServer)
    serve_console(tmp_path, page, port=0, open_browser=False)


@pytest.mark.parametrize("markdown", [False, True])
@pytest.mark.parametrize(
    "author_yaml", ['"Example Newsroom"', '{display_name: "Example Newsroom"}']
)
def test_cli_author_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, markdown: bool, author_yaml: str
) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    config_path = tmp_path / "editorial.toml"
    config = config_path.read_text(encoding="utf-8")
    profile_name = "pages/autore.md" if markdown else "pages/autore.yaml"
    config_path.write_text(
        config.replace('"author_profile.yaml"', f'"{profile_name}"'), encoding="utf-8"
    )
    profile_text = f"author: {author_yaml}\n"
    if markdown:
        profile_text = f'---\ntitle: "Chi scrive"\n{profile_text}---\n# Chi scrive\nBody'
    put(tmp_path, profile_name, profile_text)
    put(tmp_path, "content/posts/post_01_valid.md", "# Profile test article")
    monkeypatch.chdir(tmp_path)
    assert main(["view", "post_01", "--no-browser"]) == 0
    html = (tmp_path / "dist/web/post_01.html").read_text(encoding="utf-8")
    assert "Example Newsroom" in html


@pytest.mark.parametrize(
    "profile_text",
    [
        "author: [broken",
        "---\nauthor: Example Newsroom\n",
        "[]",
        "null",
        "author: 42",
        "author: {}",
        "author: {display_name: null}",
        "author: {display_name: []}",
    ],
)
def test_cli_invalid_author_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile_text: str
) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    put(tmp_path, "author_profile.yaml", profile_text)
    put(tmp_path, "content/posts/post_01_valid.md", "# Profile test article")
    monkeypatch.chdir(tmp_path)
    assert main(["view", "post_01", "--no-browser"]) == 0
    html = (tmp_path / "dist/web/post_01.html").read_text(encoding="utf-8")
    assert "Autore non disponibile" in html


def test_configured_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    assert main(["view", "post_01", "--no-browser"]) == 0
    html = (tmp_path / "dist/web/post_01.html").read_text(encoding="utf-8")
    assert "Ricevuta presente" in html
    assert "Autore non disponibile" not in html
    assert "tech_blog" in html


@pytest.mark.parametrize(
    "args", [["--port", "-1"], ["--port", "65536"], ["--config", "missing.toml"]]
)
def test_cli_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["view", "demo", "--no-browser", *args]) == 1


def test_server_invalid_port(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="port"):
        serve_console(tmp_path, tmp_path / "missing.html", port=65536)


def test_custom_dist_whitelist(tmp_path: Path) -> None:
    from editorial_pipeline.application.web_hub import _Links

    dist = tmp_path / "output"
    page = put(tmp_path, "output/web/demo.html")
    asset = put(tmp_path, "output/audio/demo.mp3")
    links = _Links(tmp_path, page, dist)
    links.feed(
        '<a href="../audio/demo.mp3">audio</a><a href="../../editorial.toml">config</a><a href="../editorial.toml">config</a><a href="../manifest.json">manifest</a><a href="//example.com/x">remote</a>'
    )
    assert links.allowed == {page.resolve(), asset.resolve()}
    with pytest.raises(ValueError, match="public"):
        _Links(tmp_path, tmp_path / "editorial.toml")


def test_cli_serves_configured_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    config = tmp_path / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace('dist = "dist"', 'dist = "output"'),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    server = MagicMock()
    monkeypatch.setattr("editorial_pipeline.cli.commands.serve_console", server)
    assert main(["view", "post_01", "--serve", "--no-browser"]) == 0
    assert server.call_args.kwargs["dist"] == tmp_path / "output"


@pytest.mark.parametrize(
    "payload",
    ["[]", "null", '{"sources":null,"claims":null}', '{"sources":[null,1],"claims":[null]}'],
)
def test_optional_json_shapes(tmp_path: Path, payload: str) -> None:
    put(tmp_path, "content/posts/demo/draft.md", "---\ntitle: [bad\n---\n# Fallback heading")
    put(tmp_path, "evidence/demo/sources.json", payload)
    put(tmp_path, "evidence/demo/factcheck.json", payload)
    put(
        tmp_path,
        "reports/gates/demo/gate1.json",
        '{"gate":1,"post_id":"other","status":"RECEIPT_VALID"}',
    )
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    assert "Fallback heading" in html
    assert "RECEIPT_VALID" not in html


def test_hostile_content_is_inert(tmp_path: Path) -> None:
    payload = '</textarea><script>window.attack=1</script><img src="https://example.com/tracker">'
    put(tmp_path, "content/posts/demo/draft.md", "# Draft")
    put(tmp_path, "dist/social/demo/linkedin.txt", payload)
    put(tmp_path, "dist/social/demo/carousel/slide_01.html", payload)
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    assert "<script>window.attack" not in html
    assert "&lt;script&gt;window.attack" in html
    assert "connect-src 'none'" in html
    assert "default-src &#39;none&#39;" in html


def test_template_and_dependency_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.application import web_hub

    put(tmp_path, "content/posts/demo/draft.md", "# Article")
    importer = importlib.import_module

    def unavailable(name: str) -> Any:
        if name == "jinja2":
            raise ImportError
        return importer(name)

    with monkeypatch.context() as context:
        context.setattr(
            "editorial_pipeline.application.web_hub.importlib.import_module", unavailable
        )
        with pytest.raises(ValueError, match="requires Jinja2"):
            generate_web_hub(tmp_path, "demo")
    monkeypatch.setattr(web_hub, "DEFAULT_TEMPLATE_DIRS", (tmp_path,))
    with pytest.raises(ValueError, match="template not found"):
        generate_web_hub(tmp_path, "demo")


def test_output_and_config_paths_must_be_contained(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        generate_web_hub(tmp_path, "demo", {"paths.dist": tmp_path.parent})


def test_ambiguous_flat_id(tmp_path: Path) -> None:
    put(tmp_path, "content/posts/demo_one.md")
    put(tmp_path, "content/posts/demo_two.md")
    with pytest.raises(ValueError, match="Ambiguous"):
        generate_web_hub(tmp_path, "demo")


def test_symlink_is_rejected(tmp_path: Path) -> None:
    put(tmp_path, "content/posts/demo/draft.md", "# Article")
    asset = put(tmp_path, "dist/audio/demo/real.mp3")
    link = asset.with_name("podcast.mp3")
    try:
        link.symlink_to(asset)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError, match="symbolic links"):
        generate_web_hub(tmp_path, "demo")


def test_social_only_and_nested_thread_sections(tmp_path: Path) -> None:
    put(
        tmp_path,
        "content/posts/demo/social_kit.md",
        "## LinkedIn\nFirst line\n### Details\nMore copy\n## Unrelated\nOmit this\n## Twitter/X\nTweet one\n### Tweet two\nSecond tweet",
    )
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    assert "First line\n### Details\nMore copy" in html
    assert "Tweet one\n### Tweet two\nSecond tweet" in html
    assert "Omit this" not in html


def test_x_thread_filename(tmp_path: Path) -> None:
    put(tmp_path, "dist/social/demo/x_thread.txt", "Thread from file")
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    assert ">Thread from file</textarea>" in html


# --- T-058: tabbed console, theme, sources, publishing and newsroom index ---------


def test_theme_config_presets_and_overrides() -> None:
    from pydantic import ValidationError

    from editorial_pipeline.config.models import ThemeConfig

    assert ThemeConfig().resolved()["accent_color"] == "#2563eb"
    emerald = ThemeConfig(palette="emerald").resolved()
    assert emerald["accent_color"] == "#0f766e" and emerald["palette"] == "emerald"
    custom = ThemeConfig(palette="nordic_minimal", accent_color="#123456", font_family="serif")
    assert custom.resolved()["accent_color"] == "#123456"
    assert custom.resolved()["background_color"] == "#ffffff"
    assert custom.resolved()["font_family"] == "serif"
    for bad in ({"accent_color": "red;}"}, {"palette": "vintage"}, {"font_family": "mono"}):
        with pytest.raises(ValidationError):
            ThemeConfig.model_validate(bad)


def test_live_example_declares_theme() -> None:
    from editorial_pipeline.config import load_config

    config = load_config("examples/live_newsroom/editorial.toml")
    assert config.theme.palette == "cobalt_tech"
    assert config.theme.resolved()["ink_color"] == "#0f172a"


def test_console_is_tabbed_and_themed(tmp_path: Path) -> None:
    put(
        tmp_path,
        "content/posts/demo/draft.md",
        "---\ntitle: Tabbed\ndate: 2026-11-14\n---\n# Tabbed\nIntro **bold** and *italic* with "
        "`code` [1], [link](https://example.org/a) and [bad](javascript:alert(1)).\n\n"
        "## Section one\n- first\n- second\n  continued\n\n1. one\n2. two\n\n> quoted\n\n---\n\n"
        "```\n<raw>\n```\n### Sub\nText [1, 2] and [9]\n",
    )
    put(tmp_path, "dist/social/demo/twitter.txt", "1/2 " + "x" * 300 + "\n\n2/2 short")
    html = generate_web_hub(
        tmp_path,
        "demo",
        newsroom="Example Desk",
        theme={"accent_color": "#0f766e", "ink_color": "url(x)", "font_family": "serif"},
        timezone="Europe/Rome",
    ).read_text(encoding="utf-8")
    for view in ("articolo", "social", "podcast", "carosello", "fonti", "pubblicazione"):
        assert f'id="view-{view}"' in html and f'href="#{view}"' in html
    assert 'role="tablist"' in html and "Example Desk" in html
    assert "--accent:#0f766e" in html and "url(x)" not in html and "--ink:#0f172a" in html
    assert "--reading:var(--serif)" in html
    assert "<strong>bold</strong>" in html and "<em>italic</em>" in html
    assert "<code>code</code>" in html and 'href="https://example.org/a"' in html
    assert 'href="javascript' not in html and ">bad</a>" not in html
    assert 'href="#fonte-1"' in html and 'href="#fonte-2"' in html
    assert '<h2 id="section-one">' in html and "<ol><li>one</li>" in html
    assert "<li>second continued</li>" in html and "<blockquote><p>quoted</p>" in html
    assert "<hr>" in html and "&lt;raw&gt;" in html and '<h3 id="sub">' in html
    assert "In questo articolo" in html and "Section one" in html
    article = html.split('id="article-body"')[1].split("</article>")[0]
    assert article.count("<pre>") == 1  # only the fenced code block, never the whole text
    assert "14 novembre 2026" in html and "Nessuna ricevuta registrata" in html
    assert "In attesa del Gate 2" in html


def test_sources_view_links_and_badges(tmp_path: Path) -> None:
    put(tmp_path, "content/posts/demo/draft.md", "# Sources")
    put(tmp_path, "evidence/sources/copy.pdf", "pdf bytes")
    sources = [
        {
            "key": "a",
            "title": "Official report",
            "type": "institutional_report",
            "primary": True,
            "url": "https://example.org/report.html",
            "pdf": "https://example.org/report.pdf",
            "doi": "10.1234/abc.5",
            "access": "open",
            "local_copy": "evidence/sources/copy.pdf",
            "accessed": "2026-11-14",
        },
        {
            "key": "b",
            "title": "Press piece",
            "primary": False,
            "type": "custom_kind",
            "url": "ftp://example.org/x",
            "access": "paywall",
            "local_copy": "../outside.pdf",
        },
        {"key": "c", "title": "", "url": "https://example.org/doc.PDF"},
    ]
    claims = [
        {"id": "C1", "source_key": "a", "outcome": "grounded_primary", "text": "T1", "quote": "Q"},
        {"id": "C2", "source_key": "b", "outcome": "grounded_secondary", "text": "T2"},
        {"id": "C3", "source_key": "zz", "outcome": "contradicted", "text": "Orphan claim"},
        {"source_key": "a", "outcome": "mystery", "text": "T4"},
    ]
    put(tmp_path, "evidence/demo/sources.json", json.dumps({"sources": sources}))
    put(tmp_path, "evidence/demo/factcheck.json", json.dumps({"claims": claims}))
    put(tmp_path, "evidence/demo/draft-review.json", '{"items": {"a": "pass", "b": "fail"}}')
    html = generate_web_hub(tmp_path, "demo").read_text(encoding="utf-8")
    for expected in (
        "Fonte ufficiale primaria",
        "Fonte secondaria",
        "Tipologia non dichiarata",
        "Rapporto istituzionale",
        "Custom kind",
        "Accesso libero",
        "Accesso riservato",
        "Scarica il PDF",
        "Apri la pagina web",
        "https://doi.org/10.1234/abc.5",
        "../../evidence/sources/copy.pdf",
        "Dato verificato · riscontro letterale",
        "Riscontro su fonte secondaria",
        "Contraddetto dalle fonti",
        "mystery",
        "Affermazioni senza fonte registrata",
        "Orphan claim",
        "1/2 controlli superati",
        "Consultata il 14 novembre 2026",
        'id="fonte-3"',
    ):
        assert expected in html, expected
    assert "ftp://" not in html and "outside.pdf" not in html


def test_publishing_view_and_gate_actions(tmp_path: Path) -> None:
    put(
        tmp_path,
        "content/posts/demo/draft.md",
        "---\ntitle: Ready\nsubtitle: Sub\nauthor: Desk\ndate: 2026-11-14\n---\n# Ready\nBody",
    )
    put(tmp_path, "dist/published/demo/article.html", "<h1>Ready</h1><p>Published <b>html</b></p>")
    put(tmp_path, "dist/packages/demo.zip", "zip")
    put(tmp_path, "dist/audio/demo/podcast.m4a", "a" * 2048)
    put(tmp_path, "dist/audio/demo/podcast_script.md", "# Script\nHost line")
    put(
        tmp_path,
        "reports/gates/demo/gate2.json",
        json.dumps(
            {
                "status": "RECEIPT_VALID",
                "gate": 2,
                "post_id": "demo",
                "role": "Direttore",
                "timestamp": "2026-11-14T20:10:44+00:00",
                "allowed_actions": ["archive", "custom_action"],
            }
        ),
    )
    html = generate_web_hub(tmp_path, "demo", timezone="Mars/Olympus").read_text(encoding="utf-8")
    for expected in (
        "Versione pubblicata",
        "Published",
        "Confronta con la bozza di lavoro",
        "Gate 2 registrato",
        "Archiviazione nel pacchetto locale",
        "custom action",
        "14 novembre 2026, ore 20:10 (UTC)",
        "Ghost",
        "Substack",
        "Hugo / Jekyll",
        "Medium",
        "title: Ready",
        "description: Sub",
        "Scarica l'archivio dell'articolo",
        "non l'intero sito",
        "NotebookLM · Audio Overview",
        "2,0 KB",
        "Host line",
        "podcast_script.md",
    ):
        assert expected in html, expected
    assert "<b>html</b>" not in html


def test_when_formats_dates() -> None:
    from editorial_pipeline.application.web_hub import _when

    assert _when("") == ""
    assert _when("not a date") == "not a date"
    assert _when("2026-03-05") == "5 marzo 2026"
    assert _when("2026-11-14T20:55:00") == "14 novembre 2026, ore 20:55"
    assert _when("2026-11-14T19:55:00+01:00", "Bad/Zone") == "14 novembre 2026, ore 19:55"


def test_file_sizes() -> None:
    from editorial_pipeline.application.web_hub import _size

    class Fake:
        def __init__(self, size: int) -> None:
            self.size = size

        def stat(self) -> Any:
            return MagicMock(st_size=self.size)

    assert _size(Fake(10)) == "10 B"  # type: ignore[arg-type]
    assert _size(Fake(3 * 1024 * 1024)) == "3,0 MB"  # type: ignore[arg-type]


def test_newsroom_index_and_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from editorial_pipeline.application.web_hub import discover_post_ids

    put(tmp_path, "content/posts/alpha/draft.md", "---\ntitle: Alpha\ndate: 2026-11-10\n---\nA")
    put(tmp_path, "content/posts/post_02_long_name.md", "---\ndate: 2026-11-12\n---\n# Beta")
    put(tmp_path, "content/posts/beta.social_kit.md", "## LinkedIn\nx")
    put(tmp_path, "content/posts/_notes.md", "skip")
    put(tmp_path, "content/posts/dup.md", "# one")
    put(tmp_path, "content/posts/dup_two.md", "# two")
    put(tmp_path, "evidence/alpha/sources.json", '{"sources": []}')
    assert discover_post_ids(tmp_path / "content/posts") == ["alpha", "dup", "dup_two", "post_02"]
    assert discover_post_ids(tmp_path / "missing") == []
    monkeypatch.chdir(tmp_path)
    browser = MagicMock()
    monkeypatch.setattr("editorial_pipeline.cli.commands.webbrowser.open", browser)
    assert main(["view", "--no-browser"]) == 0
    assert "dist/web/index.html" in capsys.readouterr().out
    index = (tmp_path / "dist/web/index.html").read_text(encoding="utf-8")
    assert index.index("Beta") < index.index("Alpha")
    assert 'href="alpha.html"' in index and 'href="post_02.html"' in index
    assert "Console non generata" in index and "Ambiguous post_id" in index
    assert "In lavorazione" in index and "G2" in index
    console = (tmp_path / "dist/web/alpha.html").read_text(encoding="utf-8")
    assert 'href="index.html"' in console
    assert main(["view", "alpha", "--all"]) == 0
    browser.assert_called_once()


def test_configured_cli_passes_theme_and_newsroom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    config = tmp_path / "editorial.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + '\n[theme]\npalette = "emerald"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert main(["view", "post_01", "--no-browser"]) == 0
    html = (tmp_path / "dist/web/post_01.html").read_text(encoding="utf-8")
    assert "--accent:#0f766e" in html


def test_index_states_and_missing_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.application import web_hub

    put(tmp_path, "content/posts/live/draft.md", "# Live")
    put(tmp_path, "dist/published/live/article.md", "Body")
    put(tmp_path, "content/posts/ready/draft.md", "# Ready")
    put(tmp_path, "content/posts/doing/draft.md", "# Doing")
    for post, gates in (("ready", (1, 2)), ("doing", (1,))):
        for number in gates:
            put(
                tmp_path,
                f"reports/gates/{post}/gate{number}.json",
                json.dumps({"status": "RECEIPT_VALID", "gate": number, "post_id": post}),
            )
    index = web_hub.generate_index(tmp_path).read_text(encoding="utf-8")
    for state in ("Pubblicato", "Pronto per la pubblicazione", "In produzione"):
        assert state in index
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "Nessun articolo trovato" in web_hub.generate_index(empty).read_text(encoding="utf-8")
    monkeypatch.setattr(web_hub, "DEFAULT_TEMPLATE_DIRS", (tmp_path,))
    with pytest.raises(ValueError, match="index template not found"):
        web_hub.generate_index(tmp_path)


def test_server_follows_index_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from editorial_pipeline.application import web_hub

    index = put(tmp_path, "dist/web/index.html", '<a href="a.html">A</a><a href="gone.html">x</a>')
    put(tmp_path, "dist/web/a.html", '<a href="../audio/a/podcast.mp3">p</a><a href="index.html">')
    put(tmp_path, "dist/audio/a/podcast.mp3")
    captured: list[set[Path]] = []

    class Probe(ThreadingHTTPServer):
        def serve_forever(self, poll_interval: float = 0.5) -> None:
            raise KeyboardInterrupt

    original = web_hub._Links.feed

    def feed(self: Any, data: str) -> None:
        original(self, data)
        captured.append(self.allowed)

    monkeypatch.setattr(web_hub, "ThreadingHTTPServer", Probe)
    monkeypatch.setattr(web_hub._Links, "feed", feed)
    serve_console(tmp_path, index, port=0, open_browser=False)
    assert (tmp_path / "dist/audio/a/podcast.mp3").resolve() in captured[-1]


def test_render_markdown_edges() -> None:
    from editorial_pipeline.application.web_hub import render_markdown

    html, toc = render_markdown("# Title\n## Same\n## Same\n```\nopen fence", skip_title=False)
    assert '<h2 id="title">' in html and 'id="same-2"' in html and len(toc) == 3
    assert "<pre><code>open fence</code></pre>" in html
    html, _ = render_markdown("> a\n- b\n\npara\n- c\n1. d\n> e\nf", citations=False)
    assert "<blockquote><p>a</p></blockquote>\n<ul><li>b</li></ul>" in html
    assert "<ul><li>c</li></ul>\n<ol><li>d</li></ol>" in html and "<p>f</p>" in html
    assert "[1]" in render_markdown("see [1]", citations=False)[0]
    assert '<a href="/metodo/">' in render_markdown("[M](/metodo/)")[0]
    assert "href" not in render_markdown("[x](//evil.example/a)")[0]


SERVICE = {
    "enabled": True,
    "api_base": "/redazione/api/stato",
    "action_base": "/redazione/azioni/stato/",
    "blog_url": "/",
    "timezone_label": "Europe/Rome",
}


@pytest.mark.parametrize("field", ["api_base", "action_base", "blog_url"])
@pytest.mark.parametrize(
    "unsafe",
    [
        "https://example.com/api",
        "//example.com/api",
        "javascript:alert(1)",
        "redazione/api",
        "/redazione/../api",
        "/redazione/./api",
        "/redazione/api\n",
        "/redazione/api?x=1",
        "/redazione\\api",
        "",
    ],
)
def test_redazione_service_rejects_unsafe_paths(field: str, unsafe: str) -> None:
    from pydantic import ValidationError

    from editorial_pipeline.config.models import RedazioneServiceConfig

    with pytest.raises(ValidationError):
        RedazioneServiceConfig.model_validate({field: unsafe})


def test_redazione_service_config_defaults() -> None:
    from pydantic import ValidationError

    from editorial_pipeline.config.models import PublishingConfig, RedazioneServiceConfig

    default = RedazioneServiceConfig()
    assert default.enabled is False
    assert default.api_base == "/redazione/api/stato"
    assert default.action_base == "/redazione/azioni/stato"
    assert default.blog_url is None
    assert default.timezone_label == "Europe/Rome"
    assert PublishingConfig().redazione_service is None
    publishing = PublishingConfig.model_validate({"redazione_service": {"enabled": True}})
    assert publishing.redazione_service == RedazioneServiceConfig(enabled=True)
    assert RedazioneServiceConfig(blog_url="/").blog_url == "/"
    with pytest.raises(ValidationError):
        RedazioneServiceConfig(timezone_label="Europe/Rome'; x")


def test_console_without_redazione_service_stays_offline(tmp_path: Path) -> None:
    put(tmp_path, "content/posts/demo/draft.md", "# Demo\nBody")
    for service in (None, {"enabled": False, "blog_url": "/"}):
        html = generate_web_hub(tmp_path, "demo", redazione_service=service).read_text(
            encoding="utf-8"
        )
        assert "connect-src 'none'" in html and "form-action 'none'" in html
        assert "connect-src 'self'" not in html and "form-action 'self'" not in html
        assert "data-editorial-slug" not in html
        assert "Decisione di uscita" not in html
        assert "Torna al Blog" not in html


def test_console_with_redazione_service_renders_decision_panel(tmp_path: Path) -> None:
    from editorial_pipeline.config.models import RedazioneServiceConfig

    put(tmp_path, "content/posts/demo/draft.md", "# Demo\nBody")
    html = generate_web_hub(tmp_path, "demo", redazione_service=SERVICE).read_text(encoding="utf-8")
    assert "connect-src 'self'" in html and "form-action 'self'" in html
    assert "connect-src 'none'" not in html
    panel = html[html.index('id="view-pubblicazione"') :]
    assert 'class="decision"' in panel and 'data-editorial-slug="demo"' in panel
    assert 'data-api="/redazione/api/stato/demo"' in panel
    assert 'method="post" action="/redazione/azioni/stato/demo"' in panel
    assert 'type="datetime-local"' in panel
    for action in ("schedule", "publish_now", "draft", "undo"):
        assert f'value="{action}"' in panel
    for shortcut in ("hour", "tomorrow", "monday"):
        assert f'data-shortcut="{shortcut}"' in panel
    assert "Europe/Rome" in panel
    # Scheduling stays disabled until the Direttore registers Gate 2.
    assert 'value="schedule" disabled' in panel and 'value="publish_now" disabled' in panel
    assert "fetch(decision.dataset.api" in html and "fetch(form.action" in html
    assert '<a class="back" href="/">← Torna al Blog</a>' in html
    put(
        tmp_path,
        "reports/gates/demo/gate2.json",
        '{"status":"RECEIPT_VALID","gate":2,"post_id":"demo","allowed_actions":["publish"]}',
    )
    model = RedazioneServiceConfig(enabled=True)
    html = generate_web_hub(tmp_path, "demo", redazione_service=model).read_text(encoding="utf-8")
    assert 'value="schedule" disabled' not in html
    assert 'value="publish_now" disabled' not in html
    assert "Torna al Blog" not in html
    with pytest.raises(ValueError, match="same-origin"):
        generate_web_hub(
            tmp_path,
            "demo",
            redazione_service={"enabled": True, "api_base": "https://example.com/x"},
        )


def test_editorial_plan_page_and_index_link(tmp_path: Path) -> None:
    from editorial_pipeline.application.web_hub import discover_post_ids, generate_index

    put(tmp_path, "content/posts/alpha/draft.md", "# Alpha\nBody")
    index = generate_index(tmp_path).read_text(encoding="utf-8")
    assert "Piano editoriale" not in index
    assert not (tmp_path / "dist/web/piano_editoriale.html").exists()
    put(
        tmp_path,
        "content/posts/editorial_plan.md",
        "# Piano di novembre\n\n## Settimana 1\n- Alpha <script>x</script>\n"
        "- [Fonte](javascript:alert(1))\n",
    )
    assert discover_post_ids(tmp_path / "content/posts") == ["alpha"]
    index = generate_index(tmp_path, newsroom="Redazione Demo").read_text(encoding="utf-8")
    assert '<a class="plan" href="piano_editoriale.html">Piano editoriale</a>' in index
    assert "editorial_plan" not in index
    assert "Torna al Blog" not in index
    plan = (tmp_path / "dist/web/piano_editoriale.html").read_text(encoding="utf-8")
    assert "default-src 'none'" in plan and "form-action 'none'" in plan
    assert "<script" not in plan and "javascript:" not in plan
    assert "&lt;script&gt;" in plan
    assert '<a class="back" href="index.html">← Tutti gli articoli</a>' in plan
    assert "<h1>Piano di novembre</h1>" in plan and 'id="settimana-1"' in plan
    assert "Redazione Demo" in plan
    put(tmp_path, "content/posts/editorial_plan.md", "---\ntitle: Piano Q4\n---\nSenza titolo")
    generate_index(tmp_path)
    plan = (tmp_path / "dist/web/piano_editoriale.html").read_text(encoding="utf-8")
    assert "<h1>Piano Q4</h1>" in plan
    put(tmp_path, "content/posts/editorial_plan.md", "Solo testo")
    generate_index(tmp_path)
    plan = (tmp_path / "dist/web/piano_editoriale.html").read_text(encoding="utf-8")
    assert "<h1>Piano editoriale</h1>" in plan


def test_index_blog_link_and_service_consoles(tmp_path: Path) -> None:
    from editorial_pipeline.application.web_hub import _Links, generate_index

    put(tmp_path, "content/posts/alpha/draft.md", "# Alpha\nBody")
    put(tmp_path, "content/posts/editorial_plan.md", "# Piano")
    index = generate_index(tmp_path, redazione_service=SERVICE)
    text = index.read_text(encoding="utf-8")
    assert '<a href="/">← Torna al Blog</a>' in text
    console = (tmp_path / "dist/web/alpha.html").read_text(encoding="utf-8")
    assert 'data-editorial-slug="alpha"' in console and "connect-src 'self'" in console
    # The loopback preview follows the index link to the plan page.
    links = _Links(tmp_path, index)
    links.feed(text)
    assert (tmp_path / "dist/web/piano_editoriale.html").resolve() in links.allowed


def test_cli_view_passes_redazione_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree("examples/sample_blog", tmp_path, dirs_exist_ok=True)
    config = tmp_path / "editorial.toml"
    text = config.read_text(encoding="utf-8")
    service = '[publishing.redazione_service]\nenabled = true\nblog_url = "/"\n'
    if "[publishing]" not in text:
        service = "[publishing]\n" + service
    config.write_text(text + "\n" + service, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["view", "post_01", "--no-browser"]) == 0
    html = (tmp_path / "dist/web/post_01.html").read_text(encoding="utf-8")
    assert 'data-editorial-slug="post_01"' in html
    assert "form-action 'self'" in html and "← Torna al Blog" in html
    assert main(["view", "--no-browser"]) == 0
    index = (tmp_path / "dist/web/index.html").read_text(encoding="utf-8")
    assert "← Torna al Blog" in index


def test_index_without_redazione_service_has_no_live_status(tmp_path: Path) -> None:
    from editorial_pipeline.application.web_hub import generate_index

    put(tmp_path, "content/posts/alpha/draft.md", "# Alpha\nBody")
    for service in (None, {"enabled": False, "api_base": "/redazione/api"}):
        html = generate_index(tmp_path, redazione_service=service).read_text(encoding="utf-8")
        assert (
            "content=\"default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'none'\""
        ) in html
        assert "script-src" not in html and "connect-src" not in html
        assert "<script" not in html and "fetch(" not in html
        assert "live-published" not in html and "state-sub" not in html


def test_index_with_redazione_service_polls_live_status(tmp_path: Path) -> None:
    from editorial_pipeline.application.web_hub import generate_index
    from editorial_pipeline.config.models import RedazioneServiceConfig

    put(tmp_path, "content/posts/alpha/draft.md", "# Alpha\nBody")
    service = RedazioneServiceConfig(enabled=True).model_dump()
    assert service["api_base"] == "/redazione/api/stato"
    html = generate_index(tmp_path, redazione_service=service).read_text(encoding="utf-8")
    assert '"/redazione/api/stato"' in html
    assert "/redazione/api/stato/stato" not in html
    assert (
        "content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'\""
    ) in html
    assert "form-action 'none'" not in html
    for rule in (".state.live-published{", ".state.live-scheduled{", ".state.live-draft{"):
        assert rule in html
    assert ".state-sub{" in html
    script = html[html.index("<script>") : html.index("</script>")]
    assert html.index("</script>") < html.index("</body>")
    assert 'var endpoint = "/redazione/api/stato";' in script
    assert "fetch(endpoint, {cache: 'no-store'" in script
    assert "setInterval(poll, 30000)" in script
    assert "/^https?:$/.test(location.protocol)" in script
    assert "'.table:not(.plan-table) tbody tr'" in script and "td.title code" in script
    assert "badge.textContent = info.badge_label" in script
    assert "'state live-' + kind" in script and "info.countdown" in script
    assert "data.posts" in script and "data.articles" in script
    assert "createElement('small')" in script and "state-sub" in script
    assert "innerHTML" not in html
    # The row the script targets carries the slug inside td.title code.
    assert '<td class="title"><a href="alpha.html">' in html and "<code>alpha</code>" in html
