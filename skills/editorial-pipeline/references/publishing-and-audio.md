# Produzione audio F5 e pubblicazione dopo il Gate 2

Reference per **F5** (`build-audio`) e per l'esecuzione delle azioni autorizzate al **Gate 2** (`publish`). Integra `gates_and_evidence.md`, che resta la norma per pacchetti, ricevute e invalidazione: questi comandi non cambiano le regole dei gate, le applicano.

Posizione nel ciclo: `F3 → Gate 1 → F4 ‖ F5 → controlli finali → Gate 2 → publish → F6`.

---

## 1. Regole che non cambiano

1. `build-audio` **non approva nulla**. Un copione o un audio generato è materiale da rivedere e da mostrare al Direttore nel pacchetto Gate 2.
2. `publish` **non decide nulla**. Esegue solo le azioni che il Direttore ha scritto nella frase di Gate 2 e che sono state copiate da quella frase in `allowed_actions` della ricevuta.
3. Non scrivete, correggete o completate `gate2.json` per far funzionare `publish`. Non aggiungete azioni al catalogo `[gates.gate2].allowed_actions` né alla ricevuta. Non cambiate provider o target per aggirare un errore: riferite al Direttore.
4. Dopo il Gate 2 non si genera né si modifica nulla in `[paths].dist`: ogni file di `dist/` (report esclusi) fa parte del bundle.

## 2. F5 — `build-audio`

### 2.1 Prima di eseguire

- Leggete `[phases.optional].F5`. Con `false` la fase è `skipped`: dichiaratelo nel pacchetto Gate 2 e **non** lanciate il comando (si rifiuterebbe comunque: `Error: Phase F5 is disabled in editorial.toml`, exit 1, anche con `--dry-run`).
- `check-gate 1 <post>` deve dare `RECEIPT_VALID` e `verify-facts <post>` nessun `BLOCK`: con evidenze non valide il comando risponde `Error: Audio requires current validated draft evidence` (exit 1).
- Provider: `--provider` > `[audio].provider` > `[providers.audio].adapter` > `script_only`. Se il Direttore non ha indicato `notebooklm`, restate su `script_only`.

### 2.2 Esecuzione

```bash
editorial-pipeline build-audio <post> --dry-run --json      # percorso previsto, nessuna scrittura
editorial-pipeline build-audio <post> --json                # status BUILT
```

| Provider | Artefatto in `[paths].dist/audio/<post_id>/` | Requisiti |
|---|---|---|
| `script_only` | `podcast_script.md` | Nessuno: offline e deterministico |
| `notebooklm` | `podcast.m4a` | `nlm` installato, `nlm login` fatto dal titolare dell'account, identificativo del taccuino nella variabile `[audio].corpus_id_env` (default `EDITORIAL_AUDIO_ID`). Il testo dei claim viene inviato a Google |

Con `notebooklm` gli errori arrivano come `NotebookLM audio: <motivo>. Retry or use --provider script_only.` (exit 1): corpus non configurato, `nlm` assente, autenticazione scaduta, timeout, generazione non conclusa o fallita, download vuoto. Riferite il motivo al Direttore e proponete `script_only`; non passate da soli all'altro provider. Un eventuale audio precedente resta intatto.

### 2.3 Dopo l'esecuzione

1. **Rileggete il copione.** Contiene solo i claim di `factcheck.json`, uno per riga `[Speaker]`, ciascuno con il suo `Riferimento:` (locator). Verificate che nessuna frase introduca un fatto nuovo; ogni dato detto a voce deve avere il suo `claim_id`.
2. **Checklist anti-cliché** (`humanizer_checklist.md`) sulle parti discorsive (intro, raccordi, outro); registrate la revisione con la prova del kit o in una prova dedicata.
3. Se il copione viene registrato con voci sintetiche, la descrizione della puntata lo dichiara.
4. Inserite nel pacchetto Gate 2 il copione integrale (o il suo percorso) e il percorso dell'audio.

Se dopo la revisione il copione va corretto, correggetelo **prima** del pacchetto Gate 2. Rieseguire `build-audio` lo sovrascrive.

## 3. Pubblicazione — `publish`

### 3.1 Azioni e adapter

| Azione scritta dal Direttore | Adapter (`--target`) | Risultato |
|---|---|---|
| `archive` (alias `dist_archive`, `export_package`) | `dist_archive` | `<archive_dir>/<post_id>.tar.gz` (default `dist/packages/`): bozza, `gate1.json`, `gate2.json`, tutti gli artefatti del bundle, `publish_manifest.json` con `bundle_digest` e SHA-256 dei file |
| `export_markdown` (alias `publish_markdown`, `static_site`) | `static_site` | `<static_site_dir>/<post_id>/` (default `dist/published/`): Markdown della bozza e asset visivi (immagini, PDF, HTML, CSS). Copione e audio non sono inclusi |
| `publish`, `schedule`, `sync`, altre | nessuno | `SKIPPED`, exit 0, nessuna scrittura. Sono azioni da eseguire fuori dalla CLI, con i loro strumenti, solo se autorizzate |

Nel pacchetto Gate 2, se il catalogo le prevede, proponete le azioni locali per nome (`archive`, `export_markdown`) e indicate target e cartella di destinazione. Il Direttore sceglie; voi copiate.

### 3.2 Esecuzione

1. Verificate che il messaggio del Direttore esista in questa sessione, che la ricevuta sia stata scritta **dopo** di esso e che `check-gate 2 <post>` dia `RECEIPT_VALID`.
2. Leggete `allowed_actions` e scegliete il target corrispondente. Se nessuna azione riguarda un adapter, non c'è nulla da eseguire con `publish`: ditelo.
3. Anteprima, a zero scritture:
   ```bash
   editorial-pipeline publish <post> --target dist_archive --dry-run --json
   ```
   Controllate `published_files`, `details.planned_actions` e, per l'archivio, `details.archive_members`.
4. Esecuzione:
   ```bash
   editorial-pipeline publish <post> --target dist_archive --json
   ```
5. Riferite `status`, `executed_actions`, `published_files` e `details.bundle_digest`. Poi F6.

### 3.3 Esiti

| Esito | Exit | Significato | Cosa fare |
|---|---|---|---|
| `PUBLISHED` | 0 | File scritti dal bundle approvato | Riferire e passare a F6 |
| `DRY_RUN` | 0 | Piano calcolato, nulla scritto | Mostrare il piano |
| `SKIPPED` | 0 | Nessuna azione autorizzata per quell'adapter | Riferire; **non** è un errore da aggirare |
| `Gate 2: invalid or unreadable bundle` | 2 | Ricevuta assente, non valida, `stale`, azioni non permesse, `BLOCK` aperti | Eseguire `check-gate 2` per il motivo; se il bundle è cambiato, nuovo pacchetto Gate 2 |
| `Approved publishing input changed`, `Gate 2 changed before publishing` | 2 | Un file del bundle è cambiato durante l'esecuzione | Fermarsi e riferire |
| `Error: publishing destination already exists` | 1 | Output già presente; nulla sovrascritto | Riferire; non cancellare l'output esistente senza istruzione |
| `Error: publishing destination overlaps protected project inputs` (o percorso non ammesso) | 1 | Cartella di `[publishing]` non valida | Riferire; la configurazione la decide il Direttore |

### 3.4 Una pubblicazione per ricevuta

Le destinazioni predefinite sono dentro `[paths].dist`, che fa parte del bundle del Gate 2: dopo la prima pubblicazione la ricevuta diventa `stale` e un secondo `publish` esce con exit 2. Se il Direttore autorizza sia `archive` sia `export_markdown`, le due strade sono: cartelle di `[publishing]` fuori da `dist/` (decisione di configurazione del Direttore), oppure un nuovo pacchetto Gate 2 dopo la prima pubblicazione. Non rigenerate la ricevuta da soli.

## 4. Checklist rapida

- [ ] F5 attiva? Se no: `F5: skipped` nel pacchetto Gate 2.
- [ ] `build-audio` eseguito **prima** del pacchetto Gate 2; copione riletto, nessun claim nuovo, checklist anti-cliché applicata.
- [ ] Pacchetto Gate 2 con copione, percorso dell'audio, azioni proposte (`archive`, `export_markdown`) e destinazione.
- [ ] Frase del Direttore con le azioni; ricevuta scritta dopo; `check-gate 2` → `RECEIPT_VALID`.
- [ ] `publish --dry-run` mostrato; `publish` eseguito solo per i target autorizzati.
- [ ] Esito riferito con `bundle_digest`; nessun file aggiunto a `dist/` dopo la ricevuta.
