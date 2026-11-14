"""Check public project files for sensitive data without exposing matched values."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = ("src", "templates", "docs", "skills", ".github", "examples", "tests", "scripts")
# Public files in the repository root: scanned by suffix or exact name.
ROOT_SUFFIXES = {".md", ".toml", ".txt", ".cfg", ".ini", ".yaml", ".yml", ".json", ".lock"}
ROOT_NAMES = {"LICENSE", ".gitignore", ".gitattributes"}
# Internal coordination files are git-ignored (D-004) and never published.
ROOT_EXCLUDED = {"AGENTS.md", "GEMINI.md", "CLAUDE.md"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
# Fragments prevent the denylist itself from containing the sensitive names.
NAMES = (
    "Redacted" + " " + "Author",
    "Redacted" + "Advisor",
    "Redacted" + "Advisor",
    "Redacted" + "Advisor",
)
PATTERNS = {
    "personal name": re.compile(r"\b(?:" + "|".join(NAMES) + r")\b", re.IGNORECASE),
    "personal surname": re.compile(r"\b" + "Redacted" + "Surname" + r"\b"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE),
    "Windows absolute path": re.compile(r"\b[A-Za-z]:(?:\\{1,2}|/)(?=[\w.-])"),
    "home path": re.compile(r"/(?:home|Users)/"),
    "static cloud ID": re.compile(
        r"\b(?:notebook_id|conversation_id)\s*[=:]\s*[\"']?[a-z0-9][a-z0-9_-]{5,}", re.IGNORECASE
    ),
}
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net"}
# Comment in editorial.example.toml documenting the rejected absolute paths;
# split so this source file does not match its own patterns.
REJECTED_PATHS_DOC = '(es. "C' + ':\\..." o "/' + 'home/...")'


def clean_test_fixtures(path: Path, line: str) -> str:
    """Remove only exact known fixture literals, not arbitrary file content."""
    relative = path.relative_to(ROOT).as_posix()
    if relative == "tests/test_config.py":
        line = line.replace('"C:\\\\outside"', '"outside fixture"')
    if relative == "tests/test_visual_builder.py" and "assert not re.search(" in line:
        line = line.replace("/Users/|/home/", "home-pattern-fixture")
    if relative == "editorial.example.toml":
        line = line.replace(REJECTED_PATHS_DOC, "(rejected-path-fixture)")
    if relative == "scripts/zero_leak_scan.py" and "home-pattern-fixture" in line:
        line = line.replace("/Users/|/home/", "home-pattern-fixture")
    return line


def iter_files() -> list[Path]:
    """Return public root files followed by the files of each scanned directory."""
    files = [
        path
        for path in sorted(ROOT.iterdir())
        if path.is_file()
        and path.name not in ROOT_EXCLUDED
        and (path.suffix.lower() in ROOT_SUFFIXES or path.name in ROOT_NAMES)
    ]
    for directory in DIRECTORIES:
        base = ROOT / directory
        if base.exists():
            files.extend(sorted(base.rglob("*")))
    return files


def is_example_email(address: str) -> bool:
    domain = address.rsplit("@", 1)[1].lower()
    return any(domain == item or domain.endswith("." + item) for item in EXAMPLE_DOMAINS)


def main() -> int:
    violations = 0
    scanned = 0
    for path in iter_files():
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
                    if category == "email" and is_example_email(match.group()):
                        continue
                    print(f"{path.relative_to(ROOT).as_posix()}:{number}: {category}")
                    violations += 1
    print(f"Zero-leak audit: {scanned} files scanned, {violations} violations.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
