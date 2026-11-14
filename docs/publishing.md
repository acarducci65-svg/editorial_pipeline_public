# Pubblicazione dopo il Gate 2 (`editorial publish`)

Questa guida descrive l'ultimo passo del ciclo editoriale: l'esecuzione materiale delle azioni che il Direttore ha autorizzato al Gate 2. Il comando `editorial publish` (equivalente: `editorial-pipeline publish`) non decide nulla. Ricontrolla la ricevuta del Gate 2, esegue **solo** le azioni che vi sono elencate e produce un pacchetto o un'esportazione locale.

Posizione nel ciclo:

```text
F3 → Gate 1 → F4 ‖ F5 → controlli finali → GATE 2 → publish → F6
```

Riferimenti collegati: capitolo 5 del [manuale](manuale_configurazione_e_uso.md) (gate e ricevute), [`architecture.md`](architecture.md) (porte e adapter), [`audio_production.md`](audio_production.md) (fase F5, che produce file inclusi nel bundle del Gate 2).

---

## 1. Sintassi

```text
editorial publish <post> [--target dist_archive|static_site] [--dry-run] [--json] [--config editorial.toml]
```

| Argomento / opzione | Effetto |
|---|---|
| `<post>` | Unità di contenuto: `post_id`, nome file o percorso relativo dentro `[paths].content` |
| `--target` | Adapter di pubblicazione. Precedenza: `--target` > `[publishing].target` > `dist_archive` |
| `--dry-run` | Esegue tutti i controlli e calcola il piano, **senza scrivere alcun file** |
| `--json` | Stampa il risultato come JSON (chiavi ordinate, percorsi relativi) |
| `--config` | File di configurazione; la sua cartella è la radice del progetto |

## 2. Gate 2 è inviolabile

`publish` parte sempre dalla stessa verifica di `check-gate 2`: linter e verifica delle evidenze sulla bozza corrente (ogni `BLOCK` ferma), validità del Gate 1, ricevuta `approvals/gate2.json` conforme allo schema, ruolo uguale a `[gates].approver_role`, frase di approvazione senza condizioni, azioni ammesse dal catalogo `[gates.gate2].allowed_actions` e scritte nell'estratto, bundle uguale ai file correnti (bozza, `gate1.json`, ogni file di `[paths].dist` esclusi i report).

Se un solo controllo fallisce, il comando si ferma subito con `GhostApprovalForbiddenError`:

| Situazione | Messaggio su standard error | Exit | File scritti |
|---|---|---|---|
| Ricevuta assente, JSON non valido, schema non rispettato | `Gate 2: invalid or unreadable bundle` | 2 | nessuno |
| Bozza, `gate1.json` o un file di `dist/` cambiati dopo l'approvazione | `Gate 2: invalid or unreadable bundle` | 2 | nessuno |
| Azione non nel catalogo o non scritta dal Direttore | `Gate 2: invalid or unreadable bundle` | 2 | nessuno |
| File del bundle modificato **durante** l'esecuzione (dopo il controllo, prima della scrittura) | `Approved publishing input changed` o `Gate 2 changed before publishing` | 2 | nessuno |

`publish` riporta un messaggio unico per tutti i rifiuti del controllo iniziale. Per conoscere il motivo preciso eseguite `editorial check-gate 2 <post>`, che stampa la causa (tabella al §5.7 del manuale).

Il rifiuto vale anche con `--dry-run`: senza un Gate 2 valido non si ottiene nemmeno il piano.

**Doppio controllo.** Dopo la verifica iniziale l'adapter rilegge in memoria tutti i file del bundle (bozza, `gate1.json`, `gate2.json`, artefatti di `dist/`), rivalida la ricevuta e ricalcola i digest `v1:`. Pubblica **i byte appena verificati**, non quelli che si trovano sul disco un istante dopo: una modifica concorrente blocca l'operazione invece di finire nel pacchetto.

## 3. Solo le azioni autorizzate (`allowed_actions`)

Il Direttore elenca le azioni nella frase di Gate 2, per esempio `Approvo Gate 2 #post_07 azioni: archive`. L'agente le copia in `allowed_actions` della ricevuta; `check-gate` verifica che ognuna compaia nell'estratto come parola intera e appartenga al catalogo `[gates.gate2].allowed_actions`.

Ogni adapter esegue solo le azioni della ricevuta che lo riguardano:

| Adapter | Azioni che lo attivano | Azione consigliata |
|---|---|---|
| `dist_archive` | `archive`, `dist_archive`, `export_package` | `archive` |
| `static_site` | `export_markdown`, `publish_markdown`, `static_site` | `export_markdown` |

Un'azione generica non basta: `publish`, `schedule` o `sync` **non** attivano nessuno dei due adapter. Se la ricevuta non contiene un'azione dell'adapter scelto, il comando non scrive nulla e risponde `SKIPPED` (exit `0`), con l'avviso `No approved action authorizes this target` su standard error. È il caso della sandbox `examples/sample_blog`, la cui ricevuta autorizza solo `publish`.

Per usare gli adapter, aggiungete le azioni al catalogo:

```toml
[gates.gate2]
approval_phrase = "Approvo Gate 2 #{unit_id}"
allowed_actions = ["publish", "schedule", "archive", "export_markdown"]
```

Il catalogo dice che cosa **si può** autorizzare; solo la frase del Direttore dice che cosa **è** autorizzato per quell'unità. Se il Direttore scrive `azioni: export_markdown`, `publish --target dist_archive` risponde `SKIPPED`.

## 4. Gli adapter

Entrambi lavorano in locale. Nessuno dei due carica file su server remoti, invia newsletter o pubblica su social: questi passi restano fuori dalla CLI e richiedono a loro volta un'azione autorizzata al Gate 2.

### 4.1 `dist_archive` — pacchetto `tar.gz` completo

Scrive `<archive_dir>/<post_id>.tar.gz` (default `[paths].dist/packages/`). L'archivio contiene:

- la bozza approvata, con i percorsi assoluti eventualmente presenti sostituiti da `[redacted]`;
- `evidence/<post_id>/approvals/gate1.json` e `gate2.json`;
- ogni artefatto del bundle del Gate 2 (carosello, kit promozionale, copione o audio F5);
- `publish_manifest.json` con `post_id`, `timestamp` UTC, `executed_actions`, `bundle_digest` (`v1:` del bundle del Gate 2) e lo SHA-256 di ogni file dell'archivio.

Se l'archivio esiste già il comando si ferma con exit `1` e non lo sovrascrive.

### 4.2 `static_site` — esportazione per siti statici e SSG

Scrive in `<static_site_dir>/<post_id>/` (default `[paths].dist/published/`):

- il file Markdown della bozza, con lo stesso nome;
- gli asset visivi del bundle (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.pdf`, `.html`, `.css`), con il loro percorso relativo.

Il copione e l'audio di F5 non vengono esportati da questo adapter: si distribuiscono con `dist_archive` o con un passo separato autorizzato. Se la cartella di destinazione esiste già il comando si ferma con exit `1`.

### 4.3 Destinazioni ammesse

`archive_dir` e `static_site_dir` devono essere percorsi relativi, dentro la radice del progetto, senza collegamenti simbolici, e non possono sovrapporsi alle cartelle editoriali protette (contenuti, evidenze, fonti, modelli, pagine, correzioni). Una destinazione non ammessa produce exit `1` prima di qualsiasi scrittura.

```toml
[publishing]
target = "dist_archive"          # oppure "static_site"
archive_dir = "dist/packages"     # facoltativo
static_site_dir = "public/posts"  # facoltativo; es. la cartella dei contenuti dell'SSG
```

## 5. Anteprima con `--dry-run`

`--dry-run` esegue gli stessi controlli della pubblicazione reale (Gate 2, azioni, destinazione, rilettura del bundle) e restituisce il piano:

```json
{
  "details": {
    "archive_members": ["content/posts/post_01_valid.md", "...", "publish_manifest.json"],
    "bundle_digest": "v1:053d0609...",
    "planned_actions": ["archive"]
  },
  "executed_actions": [],
  "published_files": ["dist/packages/post_01.tar.gz"],
  "status": "DRY_RUN",
  "target": "dist_archive"
}
```

Nessun file, cartella o archivio viene creato. `executed_actions` è vuoto; le azioni previste sono in `details.planned_actions`.

## 6. Risultato ed exit code

| `status` | Significato | Exit |
|---|---|---|
| `PUBLISHED` | Azioni eseguite; `published_files` elenca i file scritti | 0 |
| `DRY_RUN` | Piano calcolato, nessuna scrittura | 0 |
| `SKIPPED` | Nessuna azione autorizzata per l'adapter scelto; nessuna scrittura | 0 |
| — (`Error: ...`) | Configurazione, destinazione non ammessa o già esistente | 1 |
| — (`Gate 2: ...`) | Gate 2 assente, non valido, `stale` o cambiato durante l'esecuzione | 2 |

Senza `--json` il comando stampa una riga, ad esempio `PUBLISHED: dist_archive`.

## 7. Una pubblicazione per ricevuta

Le destinazioni predefinite (`dist/packages/`, `dist/published/`) stanno dentro `[paths].dist`, e ogni file di `[paths].dist` fa parte del bundle del Gate 2. Dopo la prima pubblicazione il bundle cambia e la ricevuta diventa `stale`: un secondo `publish` (per esempio verso l'altro adapter) esce con exit `2`.

Se il Direttore autorizza entrambe le azioni (`azioni: archive, export_markdown`):

- eseguite prima `--dry-run` per ciascun target e verificate i piani;
- configurate `archive_dir` e `static_site_dir` **fuori** da `[paths].dist` (per esempio `public/packages` e `public/posts`): così le due esportazioni non alterano il bundle;
- altrimenti, dopo la prima pubblicazione, serve un nuovo pacchetto Gate 2 e una nuova approvazione.

## 8. Procedura per l'agente

1. Verificate che `check-gate 2 <post>` risponda `RECEIPT_VALID` e che la ricevuta sia stata scritta **dopo** il messaggio del Direttore in questa sessione.
2. Leggete `allowed_actions` e scegliete il target corrispondente. Se nessuna azione riguarda un adapter, non c'è nulla da eseguire: lo riferite.
3. Eseguite `editorial publish <post> --target <adapter> --dry-run --json` e mostrate il piano.
4. Eseguite `editorial publish <post> --target <adapter> --json`.
5. Riferite `status`, `executed_actions`, `published_files` e `bundle_digest`. Dopo la pubblicazione si passa a F6 (registro correzioni, pagine di trasparenza).

Cosa l'agente non fa mai: scrivere o correggere `gate2.json` per far passare `publish`, aggiungere azioni al catalogo o alla ricevuta, eseguire un target per cui non c'è un'azione autorizzata, interpretare `SKIPPED` come errore da aggirare. Un esito `PUBLISHED` attesta che i file sono stati prodotti dal bundle approvato, non che il Direttore abbia approvato: quello lo prova solo il suo messaggio in chat.
