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
    page = put(tmp_path, "dist/web/demo.html", '<a href="../audio/demo/podcast.mp3">audio</a>')
    put(tmp_path, "dist/audio/demo/podcast.mp3", "audio bytes")
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
                for path in ("/editorial.toml", "/", "/dist/web/", "/../editorial.toml"):
                    with pytest.raises(HTTPError) as exc:
                        urlopen(base + path, timeout=5)
                    assert exc.value.code == 404
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
