from pathlib import Path

import pytest
from pydantic import ValidationError

from editorial_pipeline.config import EditorialConfig, load_config


def test_load_example() -> None:
    config = load_config("editorial.example.toml")
    assert config.gates.gate1.required and config.gates.gate2.required
    assert config.paths.content == "content"


def test_reject_disabled_gate() -> None:
    data = load_config("editorial.example.toml").model_dump()
    data["gates"]["gate1"]["required"] = False
    with pytest.raises(ValidationError):
        EditorialConfig.model_validate(data)


@pytest.mark.parametrize("value", ["/outside", "C:\\outside", "../outside", "\\\\server\\share"])
def test_reject_host_paths(value: str) -> None:
    data = load_config("editorial.example.toml").model_dump()
    data["author"]["profile"] = value
    with pytest.raises(ValidationError):
        EditorialConfig.model_validate(data)


def test_missing_and_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml")
    path = tmp_path / "bad.toml"
    path.write_text("[bad", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_gate2_and_nested_paths_are_validated() -> None:
    config = load_config("editorial.example.toml")
    data = config.model_dump()
    data["gates"]["gate2"]["required"] = False
    with pytest.raises(ValidationError):
        EditorialConfig.model_validate(data)
    data = config.model_dump()
    data["transparency"]["templates"]["method"] = "/private"
    with pytest.raises(ValidationError):
        EditorialConfig.model_validate(data)
    data = config.model_dump()
    data["privacy"]["reject_absolute_paths"] = False
    with pytest.raises(ValidationError):
        EditorialConfig.model_validate(data)


def test_resolve_paths_and_reject_symlink_escape(tmp_path: Path) -> None:
    config = load_config("editorial.example.toml")
    paths = config.resolve_paths(tmp_path)
    assert paths["paths.content"] == (tmp_path / config.paths.content).resolve()
    assert paths["author.profile"] == (tmp_path / config.author.profile).resolve()
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    try:
        (tmp_path / config.paths.content).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="outside"):
        config.resolve_paths(tmp_path)


def test_operative_rejects_nested_placeholders() -> None:
    config = load_config("editorial.example.toml")
    with pytest.raises(ValueError, match="placeholder"):
        config.validate_operative()
    data = config.model_dump()

    def replace(value: object) -> object:
        if isinstance(value, str):
            import re

            return re.sub(r"\{\{.*?\}\}", "sample", value)
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return value

    EditorialConfig.model_validate(replace(data)).validate_operative()
