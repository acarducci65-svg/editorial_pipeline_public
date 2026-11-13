<!--
Thanks for contributing! / Grazie per il contributo!
Keep the PR focused on one change. Link the related issue when there is one.
-->

## Summary / Descrizione

<!-- What changes and why. One short paragraph is enough. -->

Closes #

## Type of change / Tipo di modifica

- [ ] `feat` — new capability
- [ ] `fix` — bug fix
- [ ] `docs` — documentation only
- [ ] `refactor` — no behaviour change
- [ ] `test` — tests only
- [ ] `build` / `ci` / `chore` — packaging, CI, tooling

## Quality checks / Controlli di qualità

<!-- All commands must pass locally. Paste the summary line of each if useful. -->

- [ ] `uv run --extra dev pytest --cov=editorial_pipeline --cov-branch --cov-fail-under=91` passes
- [ ] `uv run --extra dev ruff check .` and `uv run --extra dev ruff format --check src tests` pass
- [ ] `uv run --extra dev mypy src tests` passes (strict mode)
- [ ] New or changed behaviour is covered by tests that use fictional fixtures only
- [ ] Documentation (`docs/`, `README.md`, `skills/editorial-pipeline/`) is updated where behaviour changed
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)

## Zero-Leak

- [ ] No personal names, e-mail addresses, credentials, tokens or API keys
- [ ] No cloud identifiers (notebook, corpus, conversation IDs): only environment variable names
- [ ] No absolute host paths in code, templates, tests, fixtures or JSON reports
- [ ] No private editorial content: examples use the fictional sandbox or invented data

## Human sovereignty / Sovranità umana

- [ ] Gate 1 (draft) and Gate 2 (publication) remain binding: no code path, flag, default or
      automation lets an agent approve, publish, schedule or sync on its own
- [ ] `HumanApproval` / `check-gate` checks are not weakened (origin, token, timestamp, digest binding)
- [ ] CLI output still distinguishes "evidence is consistent" from "content is approved"

## Notes for reviewers / Note per i revisori

<!-- Trade-offs, follow-ups, anything you are unsure about. -->
