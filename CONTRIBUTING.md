# Contributing

Discuss substantial changes in an issue before starting. Submit focused pull requests with
a description, rationale, and tests. Do not include personal data, credentials, private
editorial content, or machine-specific paths in contributions. Use fictional fixtures.

Install Python 3.10 or newer and run:

```sh
python -m pip install -e ".[dev]"
ruff check src tests
ruff format --check src tests
mypy src
pytest --cov=editorial_pipeline --cov-branch --cov-fail-under=91
```

Format changes with `ruff format src tests`. Keep public interfaces typed and maintain coverage
above 90%. The two human gates are mandatory; no automated contribution may approve a
draft or authorize publication. Contributions are made under the Apache 2.0 license.
