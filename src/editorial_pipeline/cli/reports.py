"""Safe, deterministic validation report serialization."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def digest(path: Path, root: Path) -> str:
    h = hashlib.sha256()
    h.update(relative_path(path, root).encode())
    h.update(b"\0")
    h.update(path.read_bytes())
    return h.hexdigest()


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"(?i)\b[a-z]:[\\/]+[^\s\"?]*", "[redacted]", value)
        return re.sub(r"(?<![\w:/])/(?!/)[^\s\"?]+", "[redacted]", value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {_sanitize(key): _sanitize(item) for key, item in value.items()}
    return value


def serialize(report: Any) -> str:
    return json.dumps(_sanitize(report), ensure_ascii=False, sort_keys=True, indent=2)
