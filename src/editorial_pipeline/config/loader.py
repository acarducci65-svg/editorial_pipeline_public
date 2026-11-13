import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from editorial_pipeline.config.models import EditorialConfig


def load_config(path: Path | str) -> EditorialConfig:
    with Path(path).open("rb") as stream:
        return EditorialConfig.model_validate(tomllib.load(stream))
