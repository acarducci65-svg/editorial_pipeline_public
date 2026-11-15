"""Safe, deterministic validation report serialization."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def digest_bytes(name: str, content: bytes) -> str:
    """Hash exact binary bytes; canonicalize line endings only for known text."""
    h = hashlib.sha256()
    h.update(name.encode())
    h.update(b"\0")
    if (
        Path(name).suffix.lower()
        in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".js"}
        and b"\x00" not in content
    ):
        content = content.replace(b"\r\n", b"\n")
    h.update(content)
    return f"v1:{h.hexdigest()}"


def digest(path: Path, root: Path) -> str:
    return digest_bytes(relative_path(path, root), path.read_bytes())


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"(?i)\b[a-z]:[\\/]+[^\s\"?]*", "[redacted]", value)
        value = re.sub(r'\\\\[^\s\\]+\\[^\s"?]*', "[redacted]", value)
        return re.sub(r'(?<![\w:/])/(?:home|Users|tmp)/[^\s"?]*', "[redacted]", value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {_sanitize(key): _sanitize(item) for key, item in value.items()}
    return value


def serialize(report: Any) -> str:
    return json.dumps(_sanitize(report), ensure_ascii=False, sort_keys=True, indent=2)
