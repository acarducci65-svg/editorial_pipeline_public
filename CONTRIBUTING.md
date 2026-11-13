# Contributing to Editorial Pipeline

*[Italiano più sotto](#contribuire-a-editorial-pipeline)*

Thanks for helping. Editorial Pipeline is a tool for newsrooms that work with AI models
while keeping every editorial decision human. Two rules shape every contribution:

1. **Human sovereignty.** Gate 1 (draft approval) and Gate 2 (publication approval) are
   binding. No code path, flag, default value or automation may let an agent approve its
   own work, publish, schedule or sync. Contributions that weaken this are declined.
2. **Zero-Leak.** No personal data, e-mail addresses, credentials, tokens, cloud
   identifiers (notebook, corpus or conversation IDs) or absolute host paths in code,
   templates, tests, fixtures, JSON reports or commit messages. Use fictional data: the
   sandbox in `examples/sample_blog` is the reference.

## Before you start

- For anything larger than a small fix, open an issue first (bug report or feature request)
  so the design can be discussed before you write code.
- Read [`docs/architecture.md`](docs/architecture.md) for the layering
  (domain → config → application → adapters → cli) and
  [`docs/configuration.md`](docs/configuration.md) for the `editorial.toml` schema.
- Security problems go through the private **Security → Report a vulnerability** form,
  as described in [`SECURITY.md`](SECURITY.md).

## Development setup

Requirements: Python 3.10–3.13 and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/<your-fork>/editorial_pipeline_public.git
cd editorial_pipeline_public
uv sync --extra dev
```

`uv sync` creates `.venv/` and installs the package in editable mode with the development
tools (pytest, pytest-cov, ruff, mypy). Add `--extra social` if you work on the carousel
builder; Playwright browsers are installed separately with
`uv run playwright install chromium`.

## Checks

Run all of them before pushing. CI runs the same checks on Linux, macOS and Windows with
Python 3.10, 3.11, 3.12 and 3.13.

```sh
uv run --extra dev pytest --cov=editorial_pipeline --cov-branch --cov-fail-under=91
uv run --extra dev ruff check .
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src tests
```

Quick loop while coding: `uv run --extra dev pytest -q`. Format with
`uv run --extra dev ruff format src tests`.

Standards:

- **Typing:** mypy runs in `strict` mode; public interfaces are fully annotated.
- **Coverage:** keep total branch coverage above 90 %. New behaviour needs tests.
- **Fixtures:** fictional only. Tests that touch the sandbox must keep it reproducible.
- **Reports:** JSON output uses relative paths only; never serialise host paths.
- **Dependencies:** core dependencies stay minimal (Pydantic v2, PyYAML). Heavy
  integrations go behind an optional extra and an adapter.

## Commits

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short imperative summary>

<optional body: what and why, wrapped at 72 columns>

<optional footer: Closes #123, BREAKING CHANGE: ...>
```

| Type | Use for |
| --- | --- |
| `feat` | a new capability |
| `fix` | a bug fix |
| `docs` | documentation only |
| `refactor` | code change with no behaviour change |
| `test` | adding or fixing tests |
| `build` / `ci` | packaging, dependencies, GitHub Actions |
| `chore` | maintenance that fits nowhere else |

Common scopes: `cli`, `config`, `domain`, `rag`, `visual`, `gates`, `skill`, `docs`.
Example: `fix(rag): reject claims whose source_key is missing from sources.json`.

## Pull requests

1. Fork the repository and create a branch from `main`
   (`feat/remote-rag-adapter`, `fix/check-gate-timezone`).
2. Keep the PR focused on one change; split unrelated work.
3. Run the checks above and update `docs/`, `README.md` or `skills/editorial-pipeline/`
   when behaviour changes.
4. Open the PR and complete the template checklist, including the Zero-Leak and human
   sovereignty sections.
5. A maintainer reviews the change. Approval of a pull request is a human decision:
   automated reviews, bots or agents do not count as approval.

Contributions are made under the [Apache License 2.0](LICENSE).

---

# Contribuire a Editorial Pipeline

Grazie per il contributo. Editorial Pipeline serve alle redazioni che lavorano con modelli
AI mantenendo umana ogni decisione editoriale. Due regole valgono per ogni contributo:

1. **Sovranità umana.** Il Gate 1 (approvazione della bozza) e il Gate 2 (approvazione
   della pubblicazione) sono vincolanti. Nessun percorso di codice, opzione, valore
   predefinito o automazione può permettere a un agente di approvare il proprio lavoro,
   pubblicare, programmare o sincronizzare. I contributi che indeboliscono questa regola
   non vengono accettati.
2. **Zero-Leak.** Nessun dato personale, indirizzo e-mail, credenziale, token,
   identificativo cloud o percorso assoluto dell'host in codice, template, test, fixture,
   report JSON o messaggi di commit. Usate dati inventati, come nella sandbox
   `examples/sample_blog`.

## Prima di iniziare

- Per modifiche non banali aprite prima una issue, così il progetto si discute prima del
  codice.
- Leggete [`docs/architecture.md`](docs/architecture.md) e
  [`docs/configuration.md`](docs/configuration.md).
- Le vulnerabilità si segnalano in privato, come indicato in [`SECURITY.md`](SECURITY.md).

## Ambiente di sviluppo

Servono Python 3.10–3.13 e [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/<vostro-fork>/editorial_pipeline_public.git
cd editorial_pipeline_public
uv sync --extra dev
```

## Controlli

Da eseguire tutti prima del push; la CI li ripete su Linux, macOS e Windows.

```sh
uv run --extra dev pytest --cov=editorial_pipeline --cov-branch --cov-fail-under=91
uv run --extra dev ruff check .
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src tests
```

mypy è in modalità `strict`, la copertura deve restare sopra il 90 %, le fixture sono
solo inventate e i report JSON contengono solo percorsi relativi.

## Commit e pull request

I messaggi seguono [Conventional Commits](https://www.conventionalcommits.org/)
(`feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`), ad esempio
`docs(skill): chiarire la ricevuta del Gate 2`.

Create un branch da `main`, mantenete la PR su una sola modifica, eseguite i controlli,
aggiornate la documentazione e compilate la checklist del template. L'approvazione di
una pull request è una decisione umana: revisioni automatiche, bot o agenti non valgono
come approvazione.

I contributi sono rilasciati con [licenza Apache 2.0](LICENSE).
