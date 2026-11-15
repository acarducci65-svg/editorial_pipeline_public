import hashlib
from pathlib import Path

import pytest

from editorial_pipeline.cli.reports import digest


@pytest.mark.parametrize(
    "name",
    [
        "audio.m4a",
        "audio.mp3",
        "doc.pdf",
        "x.png",
        "x.jpg",
        "x.jpeg",
        "x.tar.gz",
        "x.whl",
        "x.zip",
        "x.bin",
        "x.md",
    ],
)
def test_binary_digest_preserves_crlf(tmp_path: Path, name: str) -> None:
    content = b"binary\r\nbytes" + (b"\x00" if name.endswith(".md") else b"")
    path = tmp_path / name
    path.write_bytes(content)
    assert (
        digest(path, tmp_path)
        == "v1:" + hashlib.sha256(name.encode() + b"\0" + content).hexdigest()
    )
    path.write_bytes(content.replace(b"\r\n", b"\n"))
    assert (
        digest(path, tmp_path)
        != "v1:" + hashlib.sha256(name.encode() + b"\0" + content).hexdigest()
    )


@pytest.mark.parametrize(
    "suffix", ["md", "txt", "json", "yaml", "yml", "toml", "html", "css", "js"]
)
def test_text_digest_normalizes_crlf(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"text.{suffix}"
    path.write_bytes(b"one\r\ntwo\r\n")
    expected = digest(path, tmp_path)
    path.write_bytes(b"one\ntwo\n")
    assert digest(path, tmp_path) == expected
