import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from editorial_pipeline.config.models import EditorialConfig


def load_config(path: Path | str) -> EditorialConfig:
    # "utf-8-sig" strips a leading UTF-8 BOM (common on Windows editors) that
    # tomllib would otherwise reject as an invalid statement at line 1.
    text = Path(path).read_text(encoding="utf-8-sig")
    return EditorialConfig.model_validate(tomllib.loads(text))
