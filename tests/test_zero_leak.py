"""Privacy scanner regressions using only fictional sensitive values."""

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def scanner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    source = Path(__file__).resolve().parents[1] / "scripts" / "zero_leak_scan.py"
    spec = importlib.util.spec_from_file_location("zero_leak_scan", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


@pytest.mark.parametrize("token", ["Fictional", "Example Reviewer", "Example Middle Reviewer"])
def test_hashed_match_blocks_without_disclosing_value(
    scanner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    token: str,
) -> None:
    digest = hashlib.sha256(
        ("editorial_pipeline_zero_leak_v1" + token.lower()).encode()
    ).hexdigest()
    monkeypatch.setattr(scanner, "FORBIDDEN_HASHES", {digest}, raising=False)
    (tmp_path / "probe.txt").write_text(f"Before ({token.upper()}) after", encoding="utf-8")

    assert scanner.main() == 1
    output = capsys.readouterr().out
    assert "probe.txt:1: FORBIDDEN_NAME_MATCH" in output
    assert token.lower() not in output.lower()


def test_hashed_match_respects_word_boundaries(
    scanner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    digest = hashlib.sha256(b"editorial_pipeline_zero_leak_v1fictional").hexdigest()
    monkeypatch.setattr(scanner, "FORBIDDEN_HASHES", {digest}, raising=False)
    (tmp_path / "probe.txt").write_text("prefictional fictionalized", encoding="utf-8")

    assert scanner.main() == 0
    assert "0 violations" in capsys.readouterr().out


@pytest.mark.parametrize("text, expected", [("fictional", 0), ("Fictional", 1), ("FICTIONAL", 0)])
def test_legacy_case_sensitive_entry_avoids_common_word_matches(
    scanner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    expected: int,
) -> None:
    digest = hashlib.sha256(b"editorial_pipeline_zero_leak_v1fictional").hexdigest()
    monkeypatch.setattr(scanner, "FORBIDDEN_HASHES", {digest})
    monkeypatch.setattr(scanner, "CASE_SENSITIVE_HASHES", {digest})
    (tmp_path / "probe.txt").write_text(text, encoding="utf-8")
    assert scanner.main() == expected
