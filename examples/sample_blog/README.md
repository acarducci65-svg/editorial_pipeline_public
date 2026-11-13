# Sandbox editoriale fittizia: `sample_blog`

Progetto editoriale immaginario ("Appunti di Bottega Digitale", autrice fittizia
Ada Esempio) per provare Editorial Pipeline senza dati reali.

| File | Contenuto |
|---|---|
| `editorial.toml` | Configurazione operativa, registro attivo `tech_blog` |
| `author_profile.yaml`, `editorial_manifest.yaml` | Profilo e manifesto compilati con dati inventati |
| `content/posts/post_01_valid.md` | Bozza conforme al registro: il linter non segnala nulla |
| `content/posts/post_02_with_cliches.md` | Bozza con cliché intenzionali: il linter blocca |
| `evidence/post_0N/` | Fonti e fact-check simulati |
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

Il linter segnala; non approva. Il passaggio di Gate 1 resta una decisione umana.
