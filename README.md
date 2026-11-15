# Editorial Pipeline

[![CI](https://github.com/acarducci65-svg/editorial_pipeline_public/actions/workflows/ci.yml/badge.svg)](https://github.com/acarducci65-svg/editorial_pipeline_public/actions/workflows/ci.yml)
[![Status: Production/Stable v1.1.0](https://img.shields.io/badge/status-Production%2FStable%20v1.1.0-brightgreen)](pyproject.toml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-2a6db2.svg)](https://mypy-lang.org/)

**English** · [Italiano](#italiano)

A Python library, CLI and agent skill for the **augmented newsroom**: an editorial team
that works with AI models for drafting, checking and promotion, and keeps every decision
in human hands.

Editorial Pipeline does not write or publish for you. It gives the process structure:
style registers that flag clichés, offline consistency checks on registered evidence,
promotional carousels with integrity manifests, and two **binding human gates** that no
agent can cross on its own.

> **Status: Production/Stable (`v1.1.0`).** The core, CLI and local adapters are tested.
> The `notebooklm` RAG adapter is **optional**: it needs the external `nlm` CLI from
> `notebooklm-mcp-cli` and a Google NotebookLM notebook (see [RAG adapters](#rag-adapters)).

## Why

AI-assisted writing fails in predictable ways: unsourced numbers, invented anecdotes,
generic prose, and approvals that nobody actually gave. Editorial Pipeline turns each
of these into an explicit, checkable step:

- **Every fact has a source.** Claims are linked to a source key and a precise locator;
  `verify-facts` returns `BLOCK` when the link is missing.
- **Style review is not disguise.** Registers (`academic_essay`, `tech_blog`,
  `investigative`, `cultural_newsletter`) flag clichés to improve readability, not to make
  text "undetectable".
- **No ghost approval.** Only a person can approve the draft (Gate 1) and the publication
  (Gate 2). Agent reviews, IDE notifications or hooks never count.
- **Privacy by design.** Reports contain relative paths only; cloud identifiers live in
  environment variables, never in files.

## Lifecycle: six phases, two human gates

```mermaid
flowchart LR
    F0["F0 · Research<br/>(optional)"] -.-> F1["F1 · Sources<br/>inventory"]
    F1 --> F2["F2 · Drafting (F2a)<br/>+ humanizing (F2b)"]
    F2 --> F3["F3 · Fact-checking<br/>on evidence / RAG"]
    F3 --> G1{{"GATE 1<br/>Human approval<br/>of the draft"}}
    G1 --> F4["F4 · Promotional kit<br/>+ carousels"]
    G1 --> F5["F5 · Audio<br/>(optional, build-audio)"]
    F4 --> F6["F6 · Final checks<br/>+ snapshot"]
    F5 --> F6
    F6 --> G2{{"GATE 2<br/>Human approval<br/>of publication"}}
    G2 --> P(["editorial publish:<br/>only the authorised actions"])

    classDef gate fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#000;
    class G1,G2 gate;
```

The canonical order is declared in `editorial.toml` (`[phases]`, `gates.gate1.after`,
`gates.gate2.after`). If a file changes after a check, that check and everything that
depends on it must be redone, and an approved gate must be requested again: each approval
receipt is bound to the digests of the exact files the person saw
(see [Gates and bundle binding](#gates-and-bundle-binding)).

## Quickstart

### 1. Install

The package is not on PyPI yet: install it from a clone of the repository. It provides
**two equivalent commands**, `editorial` (short alias) and `editorial-pipeline`: every
example below works with either.

```sh
# with uv (recommended): the CLI becomes available globally
uv tool install ./editorial_pipeline_public

# or with pip, inside a virtual environment
python -m pip install ./editorial_pipeline_public

# optional extras: carousels (Jinja2 + Playwright) and audio
python -m pip install "./editorial_pipeline_public[social]"
playwright install chromium

# optional: NotebookLM fact-checking (provides nlm; the rag extra needs Python >= 3.11)
uv tool install notebooklm-mcp-cli      # or: python -m pip install "./editorial_pipeline_public[rag]"

editorial --version          # same as: editorial-pipeline --version
editorial --help
```

### 2. Try the fictional sandbox

`examples/sample_blog` is an invented blog with fictional author, posts, evidence and
demonstration receipts. Run the commands from the repository root:

```sh
# overall state: configuration, folders, findings for every post
editorial status --config examples/sample_blog/editorial.toml

# style linter + evidence files + versioned digest of the draft
editorial validate-draft post_01_valid --config examples/sample_blog/editorial.toml --json

# the second post contains deliberate clichés: the linter returns BLOCK (exit 1)
editorial-pipeline validate-draft post_02_with_cliches --config examples/sample_blog/editorial.toml

# offline consistency check of the registered evidence (sources, fact-check, F2b review)
editorial verify-facts post_01_valid --config examples/sample_blog/editorial.toml

# formal check of the demonstration receipts: "status": "RECEIPT_VALID" (exit 0)
editorial check-gate 1 post_01_valid --config examples/sample_blog/editorial.toml
editorial check-gate 2 post_01_valid --config examples/sample_blog/editorial.toml

# post-Gate 2 execution: the demo receipt authorises only the generic "publish" action,
# so the local adapter answers SKIPPED (exit 0, nothing written)
editorial publish post_01_valid --dry-run --config examples/sample_blog/editorial.toml
```

The sandbox ships with `phases.optional.F4_visual = false` and `phases.optional.F5 = false`,
so `build-visual` and `build-audio` refuse to run there (exit 1, nothing written). See
[Carousels](#carousels-build-visual) and [Audio and publishing](#audio-build-audio-and-publishing-publish)
to try them on a copy.

### 3. Start your own newsroom

```sh
editorial init my-newsroom
cd my-newsroom
# fill in the {{...}} placeholders in editorial.toml, the author profile and the manifesto
editorial status
```

### 4. Install the agent skill

```sh
# copies SKILL.md and references/ into <dir>/editorial-pipeline/
editorial install-skill .claude/skills
editorial install-skill .claude/skills --force   # overwrite an existing installation
```

`<dir>` is the **parent** skills folder of your agent (for example `.claude/skills/` for
Claude Code); the command creates `editorial-pipeline/` inside it. Without `--force` an
existing installation is left untouched (exit 1). The skill is read from the installed
package, so the command also works outside the repository.

## Command reference

| Command | Purpose | Main options |
| --- | --- | --- |
| `init <dir>` | Create a project with `editorial.toml` and templates; refuses an existing folder | — |
| `install-skill <dir>` | Install the agent skill into `<dir>/editorial-pipeline/` | `--force` |
| `view [<post_id>]` | Editorial Web Console of a post, or the newsroom index preview when `<post_id>` is omitted | `--all`, `--serve`, `--port PORT`, `--no-browser`, `--config` |
| `status` | Folder state + style/evidence report for every post | `--config` |
| `validate-draft <post>` | Register linter, evidence files present, versioned digest | `--json`, `--config` |
| `validate-all` | `validate-draft` on every post | `--json`, `--config` |
| `verify-facts <post>` | Consistency of `sources.json`, `factcheck.json` and `draft-review.json` with the draft | `--json`, `--config` |
| `build-visual <post>` | Carousel HTML (+ PNG/PDF) with SHA-256 manifest | `--dry-run`, `--html-only`, `--aspect-ratio {4:5,1:1}`, `--config` |
| `build-audio <post>` | Optional phase F5: podcast script or NotebookLM audio overview from verified claims, in `dist/audio/<post_id>/` | `--provider {script_only,notebooklm}`, `--dry-run`, `--json`, `--config` |
| `check-gate {1,2} <post>` | Formal verification of the human receipt and its bundle | `--config` (`--token` is deprecated and ignored) |
| `publish <post>` | After Gate 2 only: re-validates the receipt and runs only the authorised local actions (tar.gz package, static-site export or author website page) | `--target {dist_archive,static_site,author_website}`, `--dry-run`, `--json`, `--config` |

Global options: `--version` / `-v`, `--help`. `--config` defaults to `editorial.toml` in
the current folder; that folder becomes the project root. Output is JSON with relative
paths only.

Exit codes: `0` ok · `1` at least one `BLOCK` or an input/configuration error (including a
disabled phase) · `2` gate refused by `check-gate` or `publish` (missing, invalid or stale
receipt, actions not authorised).

## Versioned digest

Every file the pipeline tracks (draft, evidence, receipts, kit artifacts) is identified by
a deterministic, versioned digest:

```text
v1:<sha256( relative POSIX path + NUL byte + content with CRLF normalised to LF )>
```

- The `v1:` prefix names the algorithm; receipts reject digests without it.
- Line endings are normalised to LF before hashing, so the same text gives the same digest
  on Windows, macOS and Linux. The repository's `.gitattributes` keeps text files in LF.
- The relative path is part of the digest: moving or renaming a file changes it.

`validate-draft` prints the digest of the draft; `check-gate` prints, in its `bundle`
field, every digest it recomputed.

## Gates and bundle binding

A gate is crossed only after the human director writes the configured approval phrase in
the chat. **Then, and never before**, the agent that received the message records a
receipt in `evidence/<post_id>/approvals/gate<N>.json`, and `check-gate` verifies it:

```sh
editorial check-gate 1 post_07 --config editorial.toml
editorial check-gate 2 post_07 --config editorial.toml
```

| Receipt | Bundle bound by digest | Becomes stale when |
| --- | --- | --- |
| `gate1.json` | draft + `sources.json` + `factcheck.json` + `draft-review.json` (F2b) | the draft **or any of those evidence files** changes |
| `gate2.json` | draft + the `gate1.json` file + every file in `[paths].dist`, plus `allowed_actions` | the draft, the Gate 1 receipt or any file of the distribution kit changes |

`check-gate` also refuses a receipt when the schema is not exactly v1, the post or role
does not match, the `excerpt` lacks the unconditional approval phrase (negations,
conditions and `forbidden_excerpts` are rejected), Gate 2 actions are not allowed or not
written in the excerpt, or the draft still has `BLOCK` findings. On success it prints
`"status": "RECEIPT_VALID"` with gate, post, role, timestamp, authorised actions and the
recomputed bundle (exit 0); every refusal exits with code 2.

`RECEIPT_VALID` proves that a receipt is well-formed and bound to the current files. It is
**not** proof that a person approved: every field of a receipt can be written by an agent,
so a receipt written before the director's message is a ghost approval even if the CLI
accepts it. See [`docs/architecture.md`](docs/architecture.md) and chapter 5 of the
[manual](docs/manuale_configurazione_e_uso.md).

## Carousels (`build-visual`)

`build-visual` turns each `##` section of a post into a slide under
`dist/social/<post_id>/`, with a `manifest.json` listing the SHA-256 of every file.

| Option | Effect |
| --- | --- |
| *(none)* | HTML slides + PNG images + PDF (needs the `social` extra and `playwright install chromium`; without a browser it degrades to HTML with a note in the manifest) |
| `--html-only` | HTML slides + manifest only; Playwright is never started |
| `--dry-run` | Prints the files that would be written and **writes nothing**; combine with `--html-only` to preview the HTML-only plan |
| `--aspect-ratio 4:5\|1:1` | Slide format (default `4:5`) |

The command honours `[phases.optional].F4_visual`: when it is `false` (the default in the
template and in the sandbox) `build-visual` stops with `Phase F4_visual is disabled`,
exit 1, and writes nothing, not even with `--dry-run`. Enable the phase in your own project
to use it. Regenerating a carousel after Gate 2 makes the Gate 2 receipt stale.

## Audio (`build-audio`) and publishing (`publish`)

**Phase F5 — audio (optional).** `build-audio` runs only when `[phases.optional].F5 = true`;
otherwise it stops with `Phase F5 is disabled`, exit 1, and writes nothing, not even with
`--dry-run`. It also refuses drafts whose evidence has a `BLOCK`, and it builds only from the
claims in `factcheck.json` with their source and locator.

| Provider | Output in `dist/audio/<post_id>/` | Notes |
| --- | --- | --- |
| `script_only` (default) | `podcast_script.md` | Offline and deterministic: intro, one segment per source with each claim and its locator, outro with licence note and a human-review reminder |
| `notebooklm` | `podcast.m4a` | NotebookLM audio overview through `nlm audio create`, bounded status polling and atomic download. Needs `nlm login` and the notebook id in an environment variable (`EDITORIAL_AUDIO_ID` by default). Failures exit 1 with a protected message suggesting `--provider script_only` |

```toml
[phases.optional]
F5 = true

[audio]
provider = "script_only"              # or "notebooklm"
corpus_id_env = "EDITORIAL_AUDIO_ID"  # name of the variable, never the id
timeout_seconds = 60
```

Audio files live in `[paths].dist`, so they are part of the Gate 2 bundle: generate them
**before** asking for Gate 2. Regenerating them afterwards makes the receipt stale.

**Publishing after Gate 2.** `publish` first repeats the full `check-gate 2` verification;
any failure stops it with `GhostApprovalForbiddenError`, exit 2, nothing written (also with
`--dry-run`). It then runs only the actions that the director wrote in the Gate 2 approval:

| Target | Actions that enable it | Output (default folder) |
| --- | --- | --- |
| `dist_archive` (default) | `archive`, `dist_archive`, `export_package` | `dist/packages/<post_id>.tar.gz` with draft, both receipts, every bundle artifact and `publish_manifest.json` |
| `static_site` | `export_markdown`, `publish_markdown`, `static_site` | `dist/published/<post_id>/` with the Markdown draft and the visual assets, for an SSG |
| `author_website` | `author_website`, `publish_author_website`, `export_author_site` | `dist/author_site/<post_id>/index.html`: a self-contained article page with its approved assets, styled with `[theme]` |

`author_website` is meant for the author's personal site or portfolio: the folder can be
copied as it is to any static host, with no CMS or external SSG.

Generic actions such as `publish`, `schedule` or `sync` enable no adapter: the command
answers `SKIPPED` (exit 0) and writes nothing. Add `archive` and/or `export_markdown` to
`[gates.gate2].allowed_actions` to make them available for approval. Before writing, the
adapter re-reads every bundle file and re-checks its digest, and it never overwrites an
existing output. `--dry-run` returns the plan with zero writes.

```toml
[publishing]
target = "dist_archive"            # or "static_site", "author_website"
archive_dir = "public/packages"    # optional
static_site_dir = "public/posts"   # optional
author_website_dir = "public/site" # optional
```

Default destinations are inside `[paths].dist`, so a first publication changes the Gate 2
bundle and a second `publish` exits 2; configure destinations outside `dist/` when the
director authorises both actions. Everything stays local: uploading, sending or scheduling
are outside the CLI. Guides: [`docs/audio_production.md`](docs/audio_production.md) and
[`docs/publishing.md`](docs/publishing.md).

## Editorial Web Console (`view`) and visual theme

`view <post_id>` builds an offline Editorial Hub for one post in `dist/web/<post_id>.html`
and opens it in the browser. One page, six views:

1. **Article**: the formatted draft with its table of contents;
2. **Social**: the copy of the social kit, channel by channel;
3. **Podcast**: an audio player for the F5 output (or the script);
4. **Carousel**: the slides of `build-visual`, browsable with the arrow keys;
5. **Sources & transparency**: the RAG-verified sources and claims of `sources.json` and `factcheck.json`;
6. **Publishing**: Gate 1 and Gate 2 receipt state and the publication outputs.

Without `<post_id>` (or with `--all`) the command regenerates every post console plus the
newsroom index `dist/web/index.html`. The pages are static HTML with relative links, so they
work from `file://`; `--serve` serves the project on `127.0.0.1` until Ctrl+C (`--port`,
default `8000`, `0` picks a free port), and `--no-browser` only writes the files. The console
is a read-only preview: it approves nothing. Its files live under `[paths].dist`, so
generate them before asking for Gate 2.

**Visual identity.** The optional `[theme]` section of `editorial.toml` styles the console,
the newsroom index, the carousel slides and the `author_website` page:

```toml
[theme]
palette = "cobalt_tech"        # "cobalt_tech" (default), "emerald", "nordic_minimal" or "custom"
accent_color = "#2563eb"       # optional: explicit colours override the palette
background_color = "#f8fafc"
ink_color = "#0f172a"
font_family = "sans"           # or "serif"
```

The three presets are contrast-checked (WCAG AA). `custom` starts from `cobalt_tech` and
applies the colours you set; colours must be `#rrggbb` values.

## RAG adapters

`verify-facts` chooses its behaviour from `[rag].provider` (optional section) or, when
`[rag]` is absent, from `[providers.rag].adapter`:

| Adapter | Status | What it does |
| --- | --- | --- |
| `local` (also `manual`) | **Implemented, offline** | Checks the formal consistency of the *registered* evidence: schemas and `post_id`; `draft_digest` of `factcheck.json` and `draft-review.json` equal to the current draft; every claim with an allowed outcome, an existing source and a locator; `grounded_primary` only on primary sources; no circular sources; local copies inside the project; every claim found in the draft; every F2b item `pass`. It does **not** search or read the sources and does not judge whether a claim is true. |
| `none` | Implemented | Always returns `BLOCK` (`rag.unavailable`): evidence cannot be verified. |
| `notebooklm` | **Implemented, optional, online** | Runs the local checks, then asks a Google NotebookLM notebook about each claim through `nlm query notebook --json` and adds one `rag.claim` finding per claim: no citations or a denial → `BLOCK`, hedged answer → `WARN`, cited answer → `OK`. Reports never copy claim text or model answers. If `nlm` is missing, the session has expired or the notebook is not configured, it stops with `RagUnavailableError` (exit 1). |

Finding the passage that supports a claim is research work for the agent or the person;
the local adapter then checks that what was recorded is coherent.

NotebookLM works at two levels. Agents whose harness exposes the `notebooklm-mcp` server
can use `notebook_query`, `source_add` and related tools in F1 (source inventory) and F3
(fact-checking) to find passages, which they still record with source and locator in
`sources.json` and `factcheck.json`. The CLI level is configured like this:

```sh
uv tool install notebooklm-mcp-cli
nlm login                                   # done by the account owner
nlm auth storage set protected
export EDITORIAL_RAG_ID="<notebook id or nlm alias>"   # never in a versioned file
```

```toml
[rag]
provider = "notebooklm"
corpus_id_env = "EDITORIAL_RAG_ID"   # name of the variable, not the id
timeout_seconds = 60                 # per claim query
```

Claim text is sent to Google: keep `local` for drafts that must not leave the machine.
Remote findings are automated checks. They never approve Gate 1 or Gate 2, never sign
receipts and never replace the Director's message in chat. Full guide:
[`docs/rag_factcheck.md`](docs/rag_factcheck.md).

## Documentation

| Document | Content |
| --- | --- |
| [**`docs/manuale_configurazione_e_uso.md`**](docs/manuale_configurazione_e_uso.md) · [**PDF (A4)**](docs/manuale_configurazione_e_uso.pdf) | **Official complete user & configuration manual** (Markdown and A4 PDF, Italian) |
| [`docs/architecture.md`](docs/architecture.md) | Ports & Adapters layout, components, gates and human sovereignty |
| [`docs/configuration.md`](docs/configuration.md) | Full reference of `editorial.toml`, path validation, registers and templates |
| [`docs/rag_factcheck.md`](docs/rag_factcheck.md) | `RagProvider` port, local and NotebookLM adapters (MCP and `nlm` CLI levels, setup), evidence format |
| [`docs/audio_production.md`](docs/audio_production.md) | Optional phase F5: `build-audio`, `script_only` and `notebooklm` providers, `[audio]`, Gate 2 binding |
| [`docs/publishing.md`](docs/publishing.md) | `publish` after Gate 2: `allowed_actions`, `dist_archive` and `static_site` adapters, `--dry-run`, `[publishing]` |
| [`docs/author_guide.md`](docs/author_guide.md) | Guide for the director: what the system does, what it asks, how to approve |
| [`docs/humanizer_guide.md`](docs/humanizer_guide.md) | De-AI-ing checklist and style review evidence |
| [`docs/transparency_pages.md`](docs/transparency_pages.md) | Specs for the `/metodo/`, `/correzioni/`, `/per-chi-scrive/` transparency pages and SSG/CMS integration |
| [`skills/editorial-pipeline/SKILL.md`](skills/editorial-pipeline/SKILL.md) | Operating skill for AI agents: phases, commands, gate protocol |
| [`skills/editorial-pipeline/references/`](skills/editorial-pipeline/references/) | Fact-checking protocol, humanizer checklist, gates and evidence, F5 audio and publishing |
| [`examples/sample_blog/`](examples/sample_blog/) | Fictional sandbox used by tests and the quickstart |

The detailed guides are currently written in Italian.

## Multi-agent support

The skill in `skills/editorial-pipeline/` is plain Markdown plus shell commands, so any
agent harness that can read files and run a terminal can use it. Install it with
`editorial install-skill <skills-dir>`.

| Agent | How to use it |
| --- | --- |
| **Antigravity IDE** | `editorial install-skill .agents/skills` (or the workspace skills folder); run the CLI from the integrated terminal. |
| **Claude Code** | `editorial install-skill .claude/skills`; the skill is picked up by its `name` and `description`. |
| **Codex CLI** | Install the skill in a project folder and reference its `SKILL.md` from `AGENTS.md`; run the CLI through the shell tool. |

Whatever the harness, an agent stops at each gate, asks the configured question and ends
its turn. Tool auto-approval modes concern shell permissions, never editorial gates.

## Contributing

Bug reports, ideas and pull requests are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the `uv` workflow, the checks (pytest, ruff, strict mypy) and Conventional Commits.
Report vulnerabilities privately as described in [`SECURITY.md`](SECURITY.md).

## License

[Apache License 2.0](LICENSE).

---

## Italiano

**[English](#editorial-pipeline)** · Italiano

Libreria Python, CLI e skill per agenti dedicata alla **redazione aumentata**: una
redazione che usa modelli AI per scrivere, verificare e promuovere, e tiene ogni
decisione nelle mani delle persone.

Editorial Pipeline non scrive e non pubblica al posto vostro. Dà struttura al processo:
registri di stile che segnalano i cliché, controllo offline della coerenza delle evidenze
registrate, caroselli promozionali con manifest di integrità e due **gate umani
vincolanti** che nessun agente può attraversare da solo.

> **Stato: stabile (`v1.1.0`).** Nucleo, CLI e adapter locali sono testati.
> L'adapter RAG `notebooklm` è **opzionale**: richiede la CLI esterna `nlm`
> (`notebooklm-mcp-cli`) e un taccuino Google NotebookLM.

### Perché

La scrittura assistita dall'AI sbaglia in modi prevedibili: numeri senza fonte, aneddoti
inventati, prosa generica, approvazioni che nessuno ha davvero dato. Editorial Pipeline
trasforma ciascuno di questi rischi in un passaggio esplicito e verificabile:

- **Ogni fatto ha una fonte.** Ogni claim è collegato a una chiave di fonte e a un locator
  preciso; `verify-facts` restituisce `BLOCK` se il collegamento manca.
- **La revisione di stile non è mascheramento.** I registri segnalano i cliché per
  migliorare la leggibilità, non per rendere il testo «non rilevabile».
- **Nessuna approvazione fantasma.** Solo una persona approva la bozza (Gate 1) e la
  pubblicazione (Gate 2). Revisioni di altri agenti, notifiche dell'IDE o hook non valgono.
- **Privacy dalla progettazione.** I report contengono solo percorsi relativi; gli
  identificativi cloud stanno in variabili d'ambiente, mai nei file.

### Ciclo di vita: sei fasi, due gate umani

| Fase | Contenuto | Esito |
| --- | --- | --- |
| F0 *(opzionale)* | Ricerca bibliografica | Elenco di letture |
| F1 | Inventario delle fonti con locator | `sources.json` |
| F2 | Stesura (F2a) e umanizzazione in un passaggio separato (F2b) | Bozza + `draft-review.json` |
| F3 | Verifica dei fatti su evidenze / RAG | `factcheck.json`, `verify-facts` senza `BLOCK` |
| **Gate 1** | **Approvazione umana della bozza** | `approvals/gate1.json` con bundle di digest |
| F4 | Kit promozionale e caroselli | Testi per canale, manifest SHA-256 |
| F5 *(opzionale)* | Audio con `build-audio` | `dist/audio/<post_id>/`: copione `podcast_script.md` o audio `podcast.m4a` |
| F6 | Controlli finali e snapshot | Report senza `BLOCK` |
| **Gate 2** | **Approvazione umana della pubblicazione** | `approvals/gate2.json` con le azioni autorizzate |
| Pubblicazione | `publish`: solo le azioni scritte dal Direttore | Archivio `tar.gz` o esportazione per sito statico |

Il diagramma completo è nella [sezione inglese](#lifecycle-six-phases-two-human-gates).

### Avvio rapido

Il pacchetto installa **due comandi equivalenti**: `editorial` (alias breve) ed
`editorial-pipeline`.

```sh
# 1. Installazione da un clone del repository (non ancora su PyPI)
uv tool install ./editorial_pipeline_public
# oppure: python -m pip install ./editorial_pipeline_public
# extra opzionali: "[social]" per i caroselli, "[audio]" per l'audio
editorial --version                 # equivale a: editorial-pipeline --version

# 2. Sandbox fittizia, dalla radice del repository
editorial status --config examples/sample_blog/editorial.toml
editorial validate-draft post_01_valid --config examples/sample_blog/editorial.toml --json
editorial verify-facts post_01_valid --config examples/sample_blog/editorial.toml
editorial check-gate 2 post_01_valid --config examples/sample_blog/editorial.toml   # RECEIPT_VALID
# la ricevuta dimostrativa autorizza solo "publish": l'adapter locale risponde SKIPPED (exit 0)
editorial publish post_01_valid --dry-run --config examples/sample_blog/editorial.toml

# 3. Nuova redazione e installazione della skill per l'agente
editorial init mia-redazione
editorial install-skill .claude/skills          # crea .claude/skills/editorial-pipeline/
```

| Comando | Opzioni principali |
| --- | --- |
| `init <cartella>` | — |
| `install-skill <cartella>` | `--force` per sovrascrivere un'installazione esistente |
| `view [<post_id>]` | Console redazionale locale / indice newsroom: `--all`, `--serve`, `--port PORT`, `--no-browser`, `--config` |
| `status`, `validate-all` | `--json`, `--config` |
| `validate-draft <post>`, `verify-facts <post>` | `--json`, `--config` |
| `build-visual <post>` | `--dry-run` (nessuna scrittura), `--html-only` (niente Playwright), `--aspect-ratio {4:5,1:1}` |
| `build-audio <post>` | Fase F5: `--provider {script_only,notebooklm}`, `--dry-run`, `--json` |
| `check-gate {1,2} <post>` | `--config`; `--token` è deprecato e ignorato |
| `publish <post>` | Solo dopo il Gate 2: `--target {dist_archive,static_site,author_website}`, `--dry-run` (nessuna scrittura), `--json` |

Codici di uscita: `0` ok · `1` almeno un `BLOCK` o errore di input (anche una fase
disattivata) · `2` gate rifiutato da `check-gate` o da `publish` (ricevuta assente, non
valida o `stale`, azioni non autorizzate).

### Digest, gate e bundle binding

- **Digest versionato.** Ogni file è identificato da `v1:` seguito dallo SHA-256 di
  percorso relativo + byte NUL + contenuto con i fine riga normalizzati in LF: lo stesso
  testo dà lo stesso digest su Windows, macOS e Linux.
- **Gate 1.** Dopo la frase del Direttore in chat, e mai prima, l'agente scrive
  `evidence/<post_id>/approvals/gate1.json`, che vincola con i loro digest la bozza,
  `sources.json`, `factcheck.json` e `draft-review.json` (F2b). Se una di queste evidenze
  cambia, la ricevuta diventa `stale` e il gate va richiesto di nuovo.
- **Gate 2.** `gate2.json` vincola la bozza, il file `gate1.json`, ogni file di
  `[paths].dist` e le azioni autorizzate (`allowed_actions`, scritte dal Direttore).
- **`check-gate`** verifica ricevute e bundle e risponde `"status": "RECEIPT_VALID"`
  (exit 0) oppure rifiuta con exit 2. `RECEIPT_VALID` attesta la coerenza formale della
  ricevuta con i file attuali: non sostituisce la decisione umana e non prova l'identità
  di chi approva.

### Caroselli e adapter RAG

- `build-visual` rispetta `[phases.optional].F4_visual`: se la fase è disattivata (come
  nel modello e nella sandbox) si ferma con exit 1 senza scrivere nulla. `--dry-run` elenca
  i file previsti senza scriverli; `--html-only` produce solo HTML e manifest, senza
  rasterizzazione Playwright.
- Adapter RAG: `local` (e `manual`) verifica offline la **coerenza formale delle evidenze
  registrate**, senza leggere le fonti né giudicare la verità dei claim; `none` restituisce
  sempre `BLOCK`; `notebooklm` esegue i controlli locali e poi interroga un taccuino Google
  NotebookLM con `nlm query notebook`, aggiungendo un finding `OK`/`WARN`/`BLOCK` per claim.
  Si attiva con `[rag] provider = "notebooklm"` e `corpus_id_env = "EDITORIAL_RAG_ID"`, dopo
  `uv tool install notebooklm-mcp-cli` e `nlm login`; l'identificativo (o un alias `nlm`) del
  taccuino sta solo nella variabile d'ambiente. Se `nlm` manca o la sessione è scaduta termina
  con `RagUnavailableError` (exit 1). Gli agenti con il server MCP `notebooklm-mcp` possono
  usarlo in F1 e F3 per trovare i passaggi, che registrano comunque in `sources.json` e
  `factcheck.json`. I finding remoti non approvano mai il Gate 1 né il Gate 2: decide il
  Direttore in chat. Guida: [`docs/rag_factcheck.md`](docs/rag_factcheck.md).

### Audio F5 e pubblicazione

- `build-audio` rispetta `[phases.optional].F5`: con `false` (modello e sandbox) si ferma
  con exit 1 senza scrivere nulla, anche in `--dry-run`. Si rifiuta anche se le evidenze
  hanno `BLOCK`, e usa solo i claim di `factcheck.json` con fonte e locator. Provider:
  `script_only` (predefinito, offline) scrive il copione `podcast_script.md`; `notebooklm`
  genera `podcast.m4a` con `nlm audio create`, con il taccuino nella variabile
  `EDITORIAL_AUDIO_ID` (`[audio].corpus_id_env`). Gli artefatti stanno in
  `dist/audio/<post_id>/`, quindi nel bundle del Gate 2: si generano **prima** del Gate 2.
  Guida: [`docs/audio_production.md`](docs/audio_production.md).
- `publish` ripete la verifica completa di `check-gate 2`: se fallisce si ferma con
  `GhostApprovalForbiddenError`, exit 2, senza scrivere nulla. Poi esegue **solo** le azioni
  scritte dal Direttore: `archive` → adapter `dist_archive` (`dist/packages/<post_id>.tar.gz`
  con bozza, ricevute, artefatti e `publish_manifest.json`); `export_markdown` → adapter
  `static_site` (`dist/published/<post_id>/` con Markdown e asset visivi);
  `author_website` → adapter `author_website` (`dist/author_site/<post_id>/index.html`,
  pagina autonoma dell'articolo con i suoi asset approvati e lo stile di `[theme]`, pronta
  per il sito personale o il portfolio dell'autore senza CMS né SSG esterni). Le azioni
  generiche (`publish`, `schedule`, `sync`) non attivano nessun adapter: esito `SKIPPED`,
  exit 0. `--dry-run` restituisce il piano a zero scritture; le cartelle si configurano in
  `[publishing]`. Guida: [`docs/publishing.md`](docs/publishing.md).

### Console redazionale (`view`) e tema visivo

- `view <post_id>` genera l'Editorial Hub offline del post in `dist/web/<post_id>.html` e
  lo apre nel browser. Una pagina, sei viste: **Articolo** formattato con indice dei
  paragrafi; **Social** con i copy del kit per canale; **Podcast** con il player audio F5 (o
  il copione); **Carosello** con le slide di `build-visual`, sfogliabili con le frecce;
  **Fonti e trasparenza** con fonti e claim verificati su RAG (`sources.json`,
  `factcheck.json`); **Pubblicazione** con lo stato delle ricevute dei gate e gli output
  pubblicati.
- Senza `<post_id>` (o con `--all`) rigenera tutte le console e l'indice della redazione
  `dist/web/index.html`. Le pagine sono HTML statico con link relativi e funzionano da
  `file://`; `--serve` serve il progetto su `127.0.0.1` fino a Ctrl+C (`--port`,
  predefinita `8000`, `0` sceglie una porta libera); `--no-browser` scrive solo i file. La
  console è un'anteprima in sola lettura e non approva nulla; i suoi file stanno in
  `[paths].dist`, quindi si generano prima di chiedere il Gate 2.
- La sezione facoltativa `[theme]` di `editorial.toml` definisce l'identità visiva di
  console, indice, slide del carosello e pagina `author_website`: `palette`
  (`cobalt_tech` predefinita, `emerald`, `nordic_minimal`, `custom`), i colori
  `accent_color`, `background_color`, `ink_color` (valori `#rrggbb`, che prevalgono sulla
  palette) e `font_family` (`sans` o `serif`). Le tre palette predefinite rispettano il
  contrasto WCAG AA; `custom` parte da `cobalt_tech`. Esempio nella
  [sezione inglese](#editorial-web-console-view-and-visual-theme).

### Documentazione

- [**Manuale Ufficiale di Configurazione e Uso**](docs/manuale_configurazione_e_uso.md) · [**Edizione PDF A4**](docs/manuale_configurazione_e_uso.pdf): guida completa capitolo per capitolo, con comandi, configurazione, gate e ricevute, checklist de-aizing e tutorial pratico.
- Le guide tematiche in [`docs/`](docs/) approfondiscono singoli aspetti: architettura, configurazione, verifica dei fatti, produzione audio F5, pubblicazione dopo il Gate 2, guida per il Direttore, umanizzazione e pagine di trasparenza (`/metodo/`, `/correzioni/`, `/per-chi-scrive/`). La skill operativa per agenti è in [`skills/editorial-pipeline/`](skills/editorial-pipeline/SKILL.md). La tabella completa è nella [sezione inglese](#documentation).

### Agenti supportati

La skill funziona con **Antigravity IDE**, **Claude Code** e **Codex CLI**, e con
qualunque ambiente capace di leggere Markdown ed eseguire comandi di shell; si installa
con `editorial install-skill <cartella-skill>`. In ogni caso l'agente si ferma ai gate,
pone la domanda configurata e chiude il turno: le modalità di auto-approvazione dei
comandi riguardano i permessi degli strumenti, mai i gate editoriali.

### Contribuire e licenza

Leggete [`CONTRIBUTING.md`](CONTRIBUTING.md) per il flusso di lavoro con `uv`, i controlli
e le convenzioni di commit, e [`SECURITY.md`](SECURITY.md) per le segnalazioni di
sicurezza. Licenza [Apache 2.0](LICENSE).
