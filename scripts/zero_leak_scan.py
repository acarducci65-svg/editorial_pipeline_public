"""Check public project files for sensitive data without exposing matched values."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = ("src", "templates", "docs", "skills", ".github", "examples", "tests")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
# Fragments prevent the denylist itself from containing the sensitive names.
NAMES = (
    "Redacted" + " " + "Author",
    "Redacted" + "Advisor",
    "Redacted" + "Advisor",
    "Redacted" + "Advisor",
)
PATTERNS = {
    "personal name": re.compile(r"\b(?:" + "|".join(NAMES) + r")\b", re.I),
    "personal surname": re.compile(r"\b" + "Redacted" + "Surname" + r"\b"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I),
    "Windows absolute path": re.compile(r"\b[A-Za-z]:(?:\\{1,2}|/)(?=[\w.-])"),
    "home path": re.compile(r"/(?:home|Users)/"),
    "static cloud ID": re.compile(
        r"\b(?:notebook_id|conversation_id)\s*[=:]\s*[\"']?[a-z0-9][a-z0-9_-]{5,}", re.I
    ),
}
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net"}


def clean_test_fixtures(path: Path, line: str) -> str:
    """Remove only exact known test literals, not arbitrary test content."""
    relative = path.relative_to(ROOT).as_posix()
    if relative == "tests/test_config.py":
        line = line.replace('"C:\\\\outside"', '"outside fixture"')
    if relative == "tests/test_visual_builder.py" and "assert not re.search(" in line:
        line = line.replace("/Users/|/home/", "home-pattern-fixture")
    return line


def main() -> int:
    violations = 0
    scanned = 0
    for directory in DIRECTORIES:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink() or SKIP_DIRS.intersection(path.parts):
                continue
            try:
                data = path.read_bytes()
                if b"\0" in data:
                    continue
                content = data.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                print(f"Cannot scan {path.relative_to(ROOT).as_posix()}")
                violations += 1
                continue
            scanned += 1
            for number, original_line in enumerate(content.splitlines(), 1):
                line = clean_test_fixtures(path, original_line)
                for category, pattern in PATTERNS.items():
                    for match in pattern.finditer(line):
                        if category == "email" and any(match.group().rsplit("@", 1)[1].lower() == domain or match.group().rsplit("@", 1)[1].lower().endswith("." + domain) for domain in EXAMPLE_DOMAINS):
                            continue
                        print(f"{path.relative_to(ROOT).as_posix()}:{number}: {category}")
                        violations += 1
    print(f"Zero-leak audit: {scanned} files scanned, {violations} violations.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
