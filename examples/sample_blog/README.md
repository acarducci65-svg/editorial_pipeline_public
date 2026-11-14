# Sandbox editoriale fittizia: `sample_blog`

Progetto editoriale immaginario ("Appunti di Bottega Digitale", autrice fittizia
Ada Esempio) per provare Editorial Pipeline senza dati reali.

| File | Contenuto |
|---|---|
| `editorial.toml` | Configurazione operativa, registro attivo `tech_blog` |
| `author_profile.yaml`, `editorial_manifest.yaml` | Profilo e manifesto compilati con dati inventati |
| `content/posts/post_01_valid.md` | Bozza conforme al registro: il linter non segnala nulla |
| `content/posts/post_02_with_cliches.md` | Bozza con cliché intenzionali: il linter blocca |
| `evidence/post_01/` | Fonti, fact-check e revisione F2b (`draft-review.json`) legati al digest corrente della bozza: `verify-facts` restituisce zero `WARN` e zero `BLOCK` |
| `evidence/post_01/approvals/` | Ricevute dimostrative Gate 1 e Gate 2 (schema v1, bundle di digest) |
| `evidence/post_02/` | Fact-check con claim `unsupported`: esempio di evidenze che bloccano |
| `dist/social/post_01/` | Kit HTML del carosello, vincolato dalla ricevuta Gate 2 (versionato apposta, vedi `.gitignore`) |
| `templates/` | Copie dei template del framework (i test verificano che siano identiche) |

```python
from pathlib import Path
from editorial_pipeline.application import StyleChecker, aggregate_state
from editorial_pipeline.config import load_config

root = Path("examples/sample_blog")
config = load_config(root / "editorial.toml")
checker = StyleChecker.from_config(config, root)
findings = checker.scan_file(root / "content/posts/post_02_with_cliches.md")
print(aggregate_state(findings))  # VerificationState.BLOCK
```

Verifica da riga di comando, dalla radice del repository:

```bash
editorial-pipeline validate-draft post_01_valid.md --config examples/sample_blog/editorial.toml
editorial-pipeline verify-facts post_01_valid.md --config examples/sample_blog/editorial.toml
editorial-pipeline check-gate 2 post_01_valid --config examples/sample_blog/editorial.toml   # RECEIPT_VALID
```

Il linter segnala; non approva. Le ricevute in `approvals/` sono **dati di prova di una sandbox**: nessun Direttore reale le ha dettate. Mostrano il formato che `check-gate` accetta; in un progetto vero una ricevuta si scrive solo dopo il messaggio esplicito del Direttore. Qualsiasi modifica alla bozza, alle evidenze o a `dist/` le rende `stale`: vanno rigenerate insieme alle evidenze.
