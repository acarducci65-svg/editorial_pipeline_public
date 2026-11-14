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

### 2.0 Policy audio vincolante

Direttiva del Direttore: **il podcast si produce solo con Google NotebookLM Studio.**

| Provider | Stato | Perché |
|---|---|---|
| `notebooklm` | **Standard editoriale, unico motore audio ammesso** | Audio Overview conversazionale a due conduttori, costruita sulle fonti del taccuino e guidata dai soli claim verificati |
| `script_only` | Unica alternativa | Copione documentale (`podcast_script.md`) per lettura umana o registrazione in studio con voci umane |
| `tts` e ogni altro TTS mono-voce (edge-tts, sintesi di sistema, servizi esterni) | **Vietato per la pubblicazione** | Audio robotico e di qualità scadente; il provider `tts` è deprecato e resta solo per compatibilità |

Conseguenze per l'agente:

- Non generate audio con strumenti di sintesi vocale diversi da NotebookLM, neppure «in attesa» o come bozza da mostrare.
- Un file prodotto da un TTS mono-voce non entra in `[paths].dist`, nel kit o nel pacchetto Gate 2. Se ne trovate uno, segnalatelo al Direttore: non cancellatelo e non sostituitelo da soli.
- Se NotebookLM non è disponibile, F5 si chiude con `script_only` **solo con l'assenso del Direttore**, oppure si rinvia. Mai con `tts`.

### 2.1 Prima di eseguire

- Leggete `[phases.optional].F5`. Con `false` la fase è `skipped`: dichiaratelo nel pacchetto Gate 2 e **non** lanciate il comando (si rifiuterebbe comunque: `Error: Phase F5 is disabled in editorial.toml`, exit 1, anche con `--dry-run`).
- `check-gate 1 <post>` deve dare `RECEIPT_VALID` e `verify-facts <post>` nessun `BLOCK`: con evidenze non valide il comando risponde `Error: Audio requires current validated draft evidence` (exit 1).
- Provider: `--provider` > `[audio].provider` > `[providers.audio].adapter` > `script_only`. Passate sempre `--provider notebooklm` in modo esplicito: così un problema di NotebookLM produce un errore visibile invece di un ripiego automatico.
- Prerequisiti NotebookLM: `nlm` nel `PATH` (`uv tool install notebooklm-mcp-cli`), `nlm login` eseguito **dal titolare dell'account** (mai dall'agente con credenziali altrui), identificativo o alias del taccuino nella variabile `[audio].corpus_id_env` (default `EDITORIAL_AUDIO_ID`). Il testo dei claim e i locator vengono inviati a Google.

### 2.2 Procedura NotebookLM Studio

**Passo 1 — Taccuino e alias** (una volta per unità o per serie, dal titolare dell'account o su sua indicazione):

```bash
nlm notebook create "Podcast post_07" --json           # oppure riusate il taccuino già usato in F1/F3
nlm alias set podcast-post07 <notebook_id>              # alias locale: l'identificativo non finisce nei file
nlm source add podcast-post07 --url https://fonte.example/documento --wait   # solo fonti di sources.json
export EDITORIAL_AUDIO_ID=podcast-post07                # PowerShell: $env:EDITORIAL_AUDIO_ID = "podcast-post07"
```

Il taccuino contiene **solo** le fonti approvate in F1 (`sources.json`): una fonte in più è materiale che i conduttori possono citare senza claim. `build-audio` non carica fonti. Identificativi di taccuino, fonti e artefatti non si scrivono mai in file versionati, report o pacchetti: si usano alias e variabili d'ambiente.

**Passo 2 — Generazione con la CLI della pipeline** (strada ordinaria):

```bash
editorial build-audio post_07 --provider notebooklm --dry-run --json              # percorso previsto
editorial build-audio post_07 --provider notebooklm --format m4a --language it --json
```

La CLI esegue nell'ordine `nlm audio create <taccuino> --language it --confirm --json --focus "<claim verificati con fonte e locator>"`, interroga `nlm studio status` (al massimo 30 volte ogni 2 secondi) e scarica con `nlm download audio` in una cartella temporanea; il file sostituisce `podcast.<formato>` in `[paths].dist/audio/<post_id>/` solo se il download è riuscito e non è vuoto. Esito atteso: `"status": "BUILT"`, `"provider": "notebooklm"`.

`--format` sceglie il **contenitore del file** (`m4a`, default e formato nativo di NotebookLM; `mp3` solo se la destinazione lo richiede). Non va confuso con `--format` di `nlm audio create`, che sceglie lo stile della puntata (`deep_dive`, `brief`, …).

### 2.3 Procedura manuale `nlm` (attesa lunga)

Una Audio Overview richiede spesso diversi minuti, più dell'attesa limitata di `build-audio`, che allora esce con `NotebookLM audio: generation still pending after bounded polling`. In quel caso completate a mano, sullo stesso taccuino e con lo stesso `--focus` (il testo dei claim verificati, uno per riga, con fonte e locator):

```bash
nlm audio create podcast-post07 --language it --confirm --json --focus "Genera un podcast solo sulle seguenti affermazioni verificate. Non aggiungere fatti non supportati: ..."
nlm studio status podcast-post07 --json --mcp-compatible --artifact-id <artifact_id>   # ripetere finché status = completed
nlm download audio podcast-post07 --id <artifact_id> --output dist/audio/post_07/podcast.m4a --no-progress
```

- `status` `in_progress` o `queued`: attendete e ripetete; qualsiasi altro stato diverso da `completed` è un fallimento da riferire.
- Scaricate solo nel percorso che `build-audio --dry-run` ha indicato, così l'audio resta nel bundle del Gate 2.
- L'`artifact_id` serve solo nel terminale: non annotatelo in file, report o pacchetti.
- Con gli strumenti MCP di NotebookLM (`studio_create` con `artifact_type="audio"`, `studio_status`, `download_artifact`) la sequenza è la stessa.

### 2.4 Errori

Gli errori arrivano come `NotebookLM audio: <motivo>. Retry or use --provider script_only.` (exit 1), senza output grezzo di `nlm` né identificativi. Un eventuale audio precedente resta intatto.

| Motivo | Cosa fare |
|---|---|
| `notebook corpus is not configured` | Chiedete al Direttore il taccuino (alias) e impostate la variabile d'ambiente |
| `CLI 'nlm' is unavailable` | Installare `notebooklm-mcp-cli`; riferite se non potete farlo |
| `authentication required; run 'nlm login'` | Il titolare ripete `nlm login`: l'agente non gestisce credenziali |
| `CLI request timed out` | Riprovare o alzare `[audio].timeout_seconds` (decisione del Direttore) |
| `generation still pending after bounded polling` | Procedura manuale §2.3 |
| `audio generation failed`, `download did not produce an audio file` | Riprovare; se persiste, riferite |

Riferite sempre il motivo al Direttore. Con `--provider notebooklm` esplicito non c'è ripiego automatico; se `notebooklm` arriva dalla configurazione e manca `nlm` o il taccuino, la CLI stampa `Warning: … Falling back to script_only.` e scrive il copione: dichiaratelo nel pacchetto Gate 2 come «F5: solo copione, NotebookLM non disponibile». Il ripiego non è mai su `tts`.

### 2.5 Dopo l'esecuzione

1. **Ascoltate l'audio per intero.** I conduttori di NotebookLM parafrasano, collegano e commentano. Confrontate ogni fatto, numero, data e attribuzione con `factcheck.json`: ciò che non ha un `claim_id`, o lo travisa, blocca l'audio. Si rigenera con un `--focus` più stretto o, con l'assenso del Direttore, si chiude F5 con `script_only`.
2. **Annotate l'ascolto** nella prova del kit o in una prova dedicata: durata, eventuali passaggi problematici con minutaggio, esito.
3. **Copione `script_only`:** contiene solo i claim di `factcheck.json`, uno per riga `[Speaker]`, ciascuno con il suo `Riferimento:` (locator). Verificate che nessuna frase introduca un fatto nuovo e applicate la checklist anti-cliché (`humanizer_checklist.md`) alle parti discorsive (intro, raccordi, outro).
4. **Trasparenza:** la descrizione della puntata dichiara che le voci sono generate con Google NotebookLM a partire dalle fonti verificate dell'articolo.
5. Inserite nel pacchetto Gate 2 il percorso dell'audio, l'esito dell'ascolto e, se presente, il copione integrale (o il suo percorso).

Ogni correzione si fa **prima** del pacchetto Gate 2. Rieseguire `build-audio` sovrascrive l'artefatto e, dopo il Gate 2, rende la ricevuta `stale`.

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
- [ ] Audio solo da NotebookLM Studio (`--provider notebooklm`) o, in alternativa, copione `script_only`; nessun file da TTS mono-voce in `dist/`.
- [ ] `build-audio` eseguito **prima** del pacchetto Gate 2; audio ascoltato per intero e confrontato con `factcheck.json`; copione riletto, nessun claim nuovo, checklist anti-cliché applicata.
- [ ] Pacchetto Gate 2 con percorso dell'audio, esito dell'ascolto, copione se presente, azioni proposte (`archive`, `export_markdown`) e destinazione.
- [ ] Frase del Direttore con le azioni; ricevuta scritta dopo; `check-gate 2` → `RECEIPT_VALID`.
- [ ] `publish --dry-run` mostrato; `publish` eseguito solo per i target autorizzati.
- [ ] Esito riferito con `bundle_digest`; nessun file aggiunto a `dist/` dopo la ricevuta.
