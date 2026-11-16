# Produzione audio F5 e pubblicazione dopo il Gate 2

Reference per **F5** (`build-audio`), per l'esecuzione delle azioni autorizzate al **Gate 2** (`publish`) e per la console webredazionale (`view`, §5). Integra `gates_and_evidence.md`, che resta la norma per pacchetti, ricevute e invalidazione: questi comandi non cambiano le regole dei gate, le applicano.

Posizione nel ciclo: `F3 → view (bozza, fonti e claim) → Gate 1 → F4 ‖ F5 → view (kit e audio, preparazione console) → controlli finali → Gate 2 → publish → consultazione console → F6`.

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
- **Divieto di ripiego autonomo su `script_only` dopo l'avvio di NotebookLM.** Se `build-audio --provider notebooklm` ha già avviato (o agganciato) una generazione in Studio ed esce con `generation still pending after bounded polling`, NotebookLM sta **ancora producendo l'audio sul cloud**. È vietato lanciare di propria iniziativa `editorial build-audio --provider script_only` per «chiudere il task»: la console mostrerebbe «Audio non disponibile» mentre la puntata esiste. Si attende, si scarica e si verifica il file (§2.3); `script_only` resta una decisione del Direttore.

### 2.1 Prima di eseguire

- Leggete `[phases.optional].F5`. Con `false` la fase è `skipped`: dichiaratelo nel pacchetto Gate 2 e **non** lanciate il comando (si rifiuterebbe comunque: `Error: Phase F5 is disabled in editorial.toml`, exit 1, anche con `--dry-run`).
- `check-gate 1 <post>` deve dare `RECEIPT_VALID` e `verify-facts <post>` nessun `BLOCK`: con evidenze non valide il comando risponde `Error: Audio requires current validated draft evidence` (exit 1).
- Provider: `--provider` > `[audio].provider` > `[providers.audio].adapter` > `script_only`. Passate sempre `--provider notebooklm` in modo esplicito: così un problema di NotebookLM produce un errore visibile invece di un ripiego automatico.
- Prerequisiti NotebookLM: `nlm` nel `PATH` (`uv tool install notebooklm-mcp-cli`), `nlm login` eseguito **dal titolare dell'account** (mai dall'agente con credenziali altrui), alias del Micro-Taccuino d'Articolo `<slug>-<post_id>` nella variabile `[audio].corpus_id_env` (default `EDITORIAL_AUDIO_ID`). Il testo dei claim e i locator vengono inviati a Google.

### 2.2 Procedura NotebookLM Studio

**Passo 1 — Taccuino: il Micro-Taccuino d'Articolo.** Lo standard per F5 è il **Micro-Taccuino** `<slug>-<post_id>` creato a fine F1 e già usato in F3 (`verification-and-rag.md` §0 e §2.1): contiene solo le fonti di `sources.json`, quindi la puntata resta calzante sull'articolo, senza divagazioni su post già pubblicati o su fonti di altre unità. **Non** usate il Taccuino Maestro per l'audio.

```bash
export EDITORIAL_AUDIO_ID=lavoro-remoto-post_07          # PowerShell: $env:EDITORIAL_AUDIO_ID = "lavoro-remoto-post_07"
nlm studio status "$EDITORIAL_AUDIO_ID" --json --mcp-compatible   # controllo dello Studio prima di generare
```

Se il Micro-Taccuino non esiste (redazione con un solo taccuino, oppure F1 svolta senza NotebookLM), createlo ora con la stessa procedura, dal titolare dell'account o su sua indicazione:

```bash
nlm notebook create "lavoro-remoto-post_07" --json
nlm alias set lavoro-remoto-post_07 <notebook_id>       # alias locale: l'identificativo non finisce nei file
nlm source add lavoro-remoto-post_07 --url https://fonte.example/documento --wait   # solo fonti di sources.json
```

Il taccuino contiene **solo** le fonti approvate in F1 (`sources.json`): una fonte in più è materiale che i conduttori possono citare senza claim. `build-audio` non carica fonti. Identificativi di taccuino, fonti e artefatti non si scrivono mai in file versionati, report o pacchetti: si usano alias e variabili d'ambiente. Con un taccuino condiviso fra più unità vale l'avvertenza sul riuso degli artefatti in fondo al passo 2.

**Passo 2 — Generazione con la CLI della pipeline** (strada ordinaria):

```bash
editorial build-audio post_07 --provider notebooklm --dry-run --json              # percorso previsto
editorial build-audio post_07 --provider notebooklm --format m4a --language it --json
editorial build-audio post_07 --provider notebooklm --length short --overview-format deep_dive --json   # i default, scritti per esteso
```

La CLI esegue nell'ordine:

1. **Ricognizione dello Studio** (saltata con `--new`). `nlm studio status <taccuino> --json --mcp-compatible`: se nel taccuino esiste già un artefatto audio `completed`, lo scarica subito; se ne esiste uno `in_progress` o `queued`, si aggancia al suo polling. In entrambi i casi **non avvia una seconda generazione** (niente puntate duplicate né quota sprecata).
2. **Generazione**, solo se lo Studio non contiene audio riutilizzabile o se è stato passato `--new`: `nlm audio create <taccuino> --language it --confirm --json --format <overview_format> --length <length> --focus "<regole editoriali + claim verificati con fonte e locator>"`.
3. **Attesa limitata**: `nlm studio status … --artifact-id <id>` fino a **120 controlli ogni 5 secondi (10 minuti)**. Uno stato diverso da `completed`, `in_progress` o `queued` è un fallimento (`audio generation failed`).
4. **Download** con `nlm download audio` in una cartella temporanea; il file sostituisce `podcast.<formato>` in `[paths].dist/audio/<post_id>/` solo se il download è riuscito e non è vuoto.

Esito atteso: `"status": "BUILT"`, `"provider": "notebooklm"`. Conseguenza del riuso: rilanciare `build-audio --provider notebooklm` dopo un timeout **riprende** la generazione in corso e scarica la puntata appena è pronta. Per contro, il riuso guarda il taccuino, non l'unità: se nel taccuino resta una puntata `completed` di un tentativo precedente (un `--focus` ormai superato) o di un'altra unità che condivide lo stesso taccuino, la CLI riusa quella. Prima di lanciare `build-audio` controllate `nlm studio status` e, se c'è una puntata che non appartiene a questa unità, riferitelo: va eliminata dallo Studio dal titolare dell'account, o con il suo assenso, prima di generare, oppure si rigenera con `--new`. Con il Micro-Taccuino d'Articolo il problema delle altre unità non si pone.

**Flag `--new`: forzare una nuova puntata.**

```bash
editorial build-audio post_07 --provider notebooklm --new --dry-run --json
editorial build-audio post_07 --provider notebooklm --new --format m4a --language it --json
```

`--new` salta la ricognizione dello Studio e avvia sempre una nuova `nlm audio create`, ignorando gli artefatti `completed` (e anche quelli `in_progress`/`queued`) già presenti nel taccuino. Vale solo con `--provider notebooklm`: con un altro provider la CLI esce con errore (`--new is supported only by the notebooklm audio provider`).

Quando usarlo:

- la puntata `completed` nello Studio è stata generata con un `--focus` superato (claim corretti in F3, bozza cambiata e riapprovata al Gate 1);
- l'ascolto integrale (§2.5) ha bocciato la puntata e il Direttore ha chiesto di rigenerarla;
- lo Studio contiene una puntata di un'altra unità (taccuino condiviso) e il Direttore preferisce non eliminarla.

Quando **non** usarlo:

- dopo `generation still pending after bounded polling`: la puntata è ancora in produzione, si rilancia `build-audio` **senza** `--new` per agganciarla (§2.3). Con `--new` si avvia una seconda generazione, si spreca quota e la prima resta orfana nello Studio;
- come rilancio ripetuto: ogni esecuzione con `--new` è una nuova generazione sulla quota del Direttore. Una per decisione, non una serie.

**Pulizia dello Studio dopo un `--new`: un solo artefatto audio attivo.** `--new` non elimina nulla: le puntate precedenti restano nello Studio accanto alla nuova. Quando il Direttore autorizza una rigenerazione con `--new`, gli artefatti audio superati vanno eliminati dal taccuino, così nel Micro-Taccuino resta una sola puntata, quella valida. Altrimenti un rilancio successivo **senza** `--new` (per esempio per riscaricare dopo un timeout) passa dalla ricognizione dello Studio e può riscaricare una puntata vecchia, bocciata o generata con un `--focus` superato al posto di quella approvata.

1. Elencate gli artefatti: `nlm studio status <taccuino> --json --mcp-compatible`. Riferite al Direttore quali puntate audio sono superate (`artifact_id`, titolo, data di creazione) e quale resta attiva.
2. L'eliminazione è una decisione del Direttore, titolare dell'account, ed è **irreversibile**. Due strade:
   - il Direttore elimina le puntate superate dall'interfaccia di NotebookLM Studio;
   - oppure, **solo dopo la sua conferma esplicita in chat per quegli `artifact_id`**, l'agente esegue `nlm studio delete <taccuino> <artifact_id> --confirm`, una volta per artefatto.
3. Il momento è dopo che la nuova puntata è `completed` e scaricata: se la nuova generazione fallisce, le vecchie restano disponibili finché il Direttore non decide. Non eliminate mai un artefatto `in_progress` o `queued` né la puntata appena generata.
4. Ricontrollate `nlm studio status`: deve restare un solo artefatto audio `completed`. Annotate nella prova dell'ascolto (§2.5, punto 5) gli `artifact_id` eliminati e chi li ha eliminati.

Senza l'autorizzazione del Direttore non si elimina nulla, nemmeno una puntata palesemente superata: la si segnala nel pacchetto Gate 2. Rigenerare l'audio dopo il pacchetto Gate 2 rende la ricevuta `stale` (§2.5).

**Durata e formato della puntata: `--length` e `--overview-format`.**

| Opzione `build-audio` | Chiave `[audio]` | Valori | Default | Diventa in `nlm audio create` |
|---|---|---|---|---|
| `--length` | `length` | `short`, `default`, `long` | **`short`** | `--length` |
| `--overview-format` | `overview_format` | `deep_dive`, `brief`, `critique`, `debate` | `deep_dive` | `--format` |

Precedenza: opzione della CLI > `[audio]` di `editorial.toml` > default del modello. Un valore fuori elenco è rifiutato dalla CLI o dalla validazione di `editorial.toml`.

```toml
[audio]
provider = "notebooklm"
length = "short"               # default: puntata breve, indicativamente 6–10 minuti
overview_format = "deep_dive"  # conversazione di approfondimento a due conduttori
```

- **`short` è il default editoriale.** Con `default` o `long` la puntata arriva facilmente a 20 minuti e oltre, e il tempo in più si riempie di raccordi, ripetizioni e divagazioni senza claim. Un articolo con pochi claim verificati regge una puntata breve. Passate a `default` o `long` solo su indicazione del Direttore (un'inchiesta lunga con molti claim, per esempio), non per «arricchire» l'audio.
- **`--overview-format`** sceglie lo stile della Audio Overview: `deep_dive` (approfondimento, lo standard), `brief` (sintesi), `critique` e `debate` (commento o contraddittorio). Questi ultimi due spingono i conduttori a valutazioni proprie: usateli solo se il Direttore lo chiede, e all'ascolto controllate con più attenzione.
- `--format` di `build-audio` resta il **contenitore del file** (`m4a`, default e formato nativo di NotebookLM; `mp3` solo se la destinazione lo richiede). Non confondetelo con `--overview-format`, che la CLI traduce in `--format` di `nlm audio create`.
- La ricognizione dello Studio (passo 1 della sequenza qui sopra) non guarda durata, formato né `--focus`: una puntata `completed` generata con impostazioni diverse viene riscaricata com'è. Per cambiare `--length` o `--overview-format` su un taccuino che contiene già una puntata serve una nuova generazione con `--new`, quindi l'autorizzazione del Direttore (§2.5).

**Regole editoriali nel `--focus` (vincolanti, inviate in automatico).** La CLI non manda a NotebookLM solo i claim. Il `--focus` comincia con un blocco di vincoli per i conduttori e poi elenca le affermazioni verificate, una per riga, nella forma `- <testo> (fonte <key>, <locator>)`. I vincoli:

1. **Registro sobrio e giornalistico**: tono asciutto, pacato, analitico; niente toni entusiastici, sensazionalistici o da spettacolo.
2. **Niente enfasi né frasi fatte**: niente iperboli, esclamazioni a effetto, domande retoriche teatrali, né formule come «immersione profonda», «viaggio illuminante», «forze titaniche», «saltare sulla sedia», «rivoluzione», «cambia tutto», «senza precedenti», «i modelli non mentono».
3. **Niente metafore né esempi inventati**: nessun paragone di vita quotidiana (il prezzo di beni comuni, per esempio), nessun esempio numerico, aliquota, età o scenario ipotetico che non compaia nei claim.
4. **Rigore causale e temporale**: il risultato condizionato di un modello non diventa una previsione certa né una ricetta universale. Le definizioni si rispettano alla lettera (benessere o utilità non sono gettito fiscale), e così gli orizzonti temporali (un decennio non diventa «per sempre»).
5. **Perimetro chiuso**: solo le affermazioni verificate e i loro locator, nessun fatto esterno o non supportato.
6. **Espressioni vietate dal progetto**, solo se ce ne sono: la CLI aggiunge l'elenco di `[register].extra_forbidden` di `editorial.toml`, le stesse formule che `validate-draft` blocca nella bozza. Per vietare un'espressione anche nell'audio non serve un'opzione a parte: va aggiunta a `extra_forbidden` prima di generare. È una decisione del Direttore, perché vale anche per la bozza.

Le regole del `--focus` **non sono una garanzia**: NotebookLM di solito le segue, non sempre. Il controllo che conta resta l'ascolto integrale (§2.5). Non riscrivete né allentate il `--focus` a mano per avere una puntata più «vivace»; nella procedura manuale (§2.3) usate lo stesso testo che produrrebbe la CLI.

### 2.3 Procedura manuale `nlm` (attesa lunga)

Una Audio Overview può superare anche i 10 minuti di attesa di `build-audio`, che allora esce con `NotebookLM audio: generation still pending after bounded polling` (exit 1). **La generazione non è fallita: prosegue in background su NotebookLM.** Non ripiegate su `script_only` (§2.0) e non avviate una nuova `nlm audio create`. Procedete così:

1. **Controllate lo stato** dell'artefatto già avviato:
   ```bash
   nlm studio status "$EDITORIAL_AUDIO_ID" --json --mcp-compatible        # PowerShell: nlm studio status $env:EDITORIAL_AUDIO_ID --json --mcp-compatible
   ```
   `in_progress` o `queued`: attendete qualche minuto e ripetete. Qualsiasi altro stato diverso da `completed` è un fallimento da riferire al Direttore.
2. **Scaricate la puntata.** Strada preferita: rilanciate `editorial build-audio post_07 --provider notebooklm --format m4a --json` (**senza** `--new`), che trova l'artefatto `completed` (o ancora in corso) e lo scarica senza rigenerarlo. In alternativa, a mano:
   ```bash
   nlm download audio "$EDITORIAL_AUDIO_ID" --id <artifact_id> --output dist/audio/post_07/podcast.m4a --no-progress
   ```
3. **Verificate il file su disco** prima di andare avanti: deve esistere e non essere vuoto.
   ```bash
   test -s dist/audio/post_07/podcast.m4a && ls -l dist/audio/post_07/   # PowerShell: Get-Item dist/audio/post_07/podcast.m4a | Select-Object Length
   ```
4. **Solo dopo**, rigenerate la console: `editorial view post_07 --no-browser`. Senza il file la scheda Podcast mostra «Audio non disponibile».

Se il Direttore preferisce non attendere, la decisione (rinvio o `script_only`) è sua: chiedetela, non prendetela.

Se manca del tutto una generazione (nessun artefatto audio nello Studio), la procedura manuale completa usa lo stesso taccuino e lo stesso `--focus` (il testo dei claim verificati, uno per riga, con fonte e locator):

```bash
nlm audio create podcast-post07 --language it --confirm --json --format deep_dive --length short --focus "Genera un podcast esclusivamente sulle affermazioni verificate elencate in fondo. Vincoli editoriali obbligatori per i conduttori: ... Affermazioni verificate (testo, fonte, locator): ..."
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
| `generation still pending after bounded polling` | La puntata è ancora in produzione sul cloud: attendete, rilanciate `build-audio --provider notebooklm` senza `--new` (riprende l'artefatto) o scaricate con `nlm download audio`, verificate il file (§2.3). **Mai** `--provider script_only` di propria iniziativa |
| `audio generation failed`, `download did not produce an audio file` | Riprovare; se persiste, riferite |

Il suggerimento `Retry or use --provider script_only` stampato dalla CLI è rivolto al Direttore, non è un'autorizzazione per l'agente: dopo l'avvio di una generazione NotebookLM il ripiego su `script_only` richiede il suo assenso esplicito (§2.0).

**PowerShell: variabile d'ambiente e UUID.** Non scrivete mai `$env:` davanti all'identificativo letterale (`$env:1a2b3c4d-…`): PowerShell non lo espande, `nlm` riceve un argomento che comincia con `-` e risponde `No such option: -…`. Assegnate prima la variabile e poi passatela per nome:

```powershell
$env:EDITORIAL_AUDIO_ID = "podcast-post07"            # alias (preferito) o identificativo del taccuino
nlm studio status $env:EDITORIAL_AUDIO_ID --json --mcp-compatible
```

Riferite sempre il motivo al Direttore. Con `--provider notebooklm` esplicito non c'è ripiego automatico; se `notebooklm` arriva dalla configurazione e manca `nlm` o il taccuino, la CLI stampa `Warning: … Falling back to script_only.` e scrive il copione: dichiaratelo nel pacchetto Gate 2 come «F5: solo copione, NotebookLM non disponibile». Il ripiego non è mai su `tts`.

### 2.5 Dopo l'esecuzione

1. **Ascoltate l'audio per intero.** NotebookLM Studio non legge il copione né i claim di `factcheck.json` parola per parola: genera un dialogo naturale fra due conduttori sulle fonti caricate nel Micro-Taccuino, che parafrasano, collegano e commentano. Confrontate ogni fatto, numero, data e attribuzione con `factcheck.json` e, per i passaggi di contorno, con le fonti del taccuino: un fatto che travisa un claim, o un'affermazione materiale che non trova riscontro né nei claim né nelle fonti, blocca l'audio. La sola assenza di un `claim_id` per una frase di raccordo non è un difetto (vedi punto 3). Se l'agente non può ascoltare, una trascrizione automatica (ASR) serve come **ispezione di supporto** per preparare i rilievi con il minutaggio, ma **non sostituisce l'ascolto umano**: dichiaratelo nel pacchetto Gate 2 e lasciate l'ascolto al Direttore.
2. **Controllo anti-cliché e anti-estrapolazione (pre-Gate 2).** Sullo stesso ascolto, o sulla trascrizione di supporto, applicate la checklist anti-cliché (`humanizer_checklist.md`) e le regole del `--focus` (§2.2). Cercate in particolare:
   - enfasi e frasi fatte: iperboli, esclamazioni, domande retoriche teatrali, le formule del punto 2 del `--focus`, ogni voce di `[register].extra_forbidden`;
   - metafore ed esempi inventati: paragoni di vita quotidiana, prezzi, cifre, aliquote, età o scenari ipotetici che non compaiono in nessun claim;
   - estrapolazioni: un risultato condizionato presentato come certezza o come ricetta valida ovunque, un orizzonte temporale allargato («per sempre», «d'ora in poi» al posto del periodo studiato), una correlazione raccontata come causa;
   - confusioni concettuali: definizioni scambiate fra loro (benessere o utilità al posto di gettito, stima al posto di misura, campione al posto di popolazione);
   - durata fuori scala rispetto a `length` e riempitivi senza claim.
3. **Materialità: cosa blocca e cosa no.** Classificate ogni rilievo prima di riferirlo.
   - **Bloccanti (finding P1, esito `fail`):** numeri, percentuali, date o scale inventati o alterati; errori fattuali o affermazioni contraddette dai claim o dalle fonti del taccuino; inversioni o confusioni concettuali gravi (benessere o utilità spacciati per gettito fiscale, il risultato di una coorte esteso a tutta la forza lavoro, una correlazione raccontata come causa); toni enfatici, cliché, formule del `--focus` o voci di `[register].extra_forbidden`.
   - **Non bloccanti (al più una nota P3 per l'ascolto del Direttore):** normali raccordi discorsivi coerenti con le fonti del taccuino, che non introducono cifre, attribuzioni o tesi assenti dalle fonti; piccole variazioni stilistiche di sintesi che non cambiano il senso di un claim; ambiguità tipiche della trascrizione automatica (ASR, `faster-whisper`), cioè parole mal trascritte, nomi storpiati o frasi spezzate, da verificare a orecchio sull'audio originale prima di trattarle come difetti.
   - Nel dubbio fra le due classi, riportate la frase con il minutaggio e la vostra classificazione motivata: decide il Direttore. Una nota P3 non fa fallire F5 e non autorizza a dichiarare la puntata difettosa; va solo segnalata nel pacchetto Gate 2.
4. **Se il controllo fallisce: finding P1, nessuna rigenerazione autonoma.** Ogni passaggio bloccante (punto 3) è un finding **P1** da riferire al Direttore con minutaggio, frase (testuale, o ricavata dalla trascrizione), regola violata e `claim_id` coinvolto (o «nessun claim»). La puntata non entra nel pacchetto Gate 2 come «ascoltata e conforme». **Non lanciate `build-audio --new` senza l'autorizzazione esplicita del Direttore**: ogni `--new` è una nuova generazione sulla sua quota, e le puntate precedenti restano nello Studio. Decide il Direttore: rigenerare con `--new` (senza `--new` la CLI riscaricherebbe la stessa puntata `completed`), eventualmente con `--length` più breve o con nuove voci in `extra_forbidden`, e poi eliminare dal taccuino la puntata bocciata, a mano su Studio o con `nlm studio delete <taccuino> <artifact_id> --confirm` previa sua conferma esplicita, così resta un solo artefatto audio attivo (§2.2, «Pulizia dello Studio dopo un `--new`»); accettare la puntata dichiarando i rilievi; chiudere F5 con `script_only`; dichiarare F5 `skipped`.
5. **Annotate l'ascolto** nella prova del kit o in una prova dedicata: durata, `length` e `overview_format` usati, passaggi problematici con minutaggio, regola violata e classe (P1 o nota P3), esito, e se l'ispezione è stata fatta con ascolto umano o su trascrizione di supporto.
6. **Copione `script_only`:** contiene solo i claim di `factcheck.json`, uno per riga `[Speaker]`, ciascuno con il suo `Riferimento:` (locator). Verificate che nessuna frase introduca un fatto nuovo e applicate la checklist anti-cliché (`humanizer_checklist.md`) alle parti discorsive (intro, raccordi, outro).
7. **Trasparenza:** la descrizione della puntata dichiara che le voci sono generate con Google NotebookLM a partire dalle fonti verificate dell'articolo.
8. Inserite nel pacchetto Gate 2 il percorso dell'audio, l'esito dell'ascolto e del controllo del punto 2, gli eventuali finding P1, le note P3 da verificare a orecchio e, se presente, il copione integrale (o il suo percorso).

Ogni correzione si fa **prima** del pacchetto Gate 2. Rieseguire `build-audio` sovrascrive l'artefatto e, dopo il Gate 2, rende la ricevuta `stale`.

## 3. Pubblicazione — `publish`

### 3.1 Azioni e adapter

| Azione scritta dal Direttore | Adapter (`--target`) | Risultato |
|---|---|---|
| `archive` (alias `dist_archive`, `export_package`) | `dist_archive` | `<archive_dir>/<post_id>.tar.gz` (default `dist/packages/`): bozza, `gate1.json`, `gate2.json`, tutti gli artefatti del bundle, `publish_manifest.json` con `bundle_digest` e SHA-256 dei file |
| `export_markdown` (alias `publish_markdown`, `static_site`) | `static_site` | `<static_site_dir>/<post_id>/` (default `dist/published/`): Markdown della bozza (`index.md` con `static_site_layout = "hugo_bundle"`), immagini (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`), documenti `.pdf` e, con l'azione `static_site` (o `publish_audio`) nella ricevuta, l'audio approvato (`.mp3`, `.m4a`, `.ogg`, `.wav`). **Mai** `.html` né `.css`; il copione non è incluso. Dettagli: §3.6 |
| `author_website` (alias `publish_author_website`, `export_author_site`) | `author_website` | `<author_website_dir>/<post_id>/` (default `dist/author_site/`): `index.html` long-form per il sito personale dell'autore e `assets/` con slide, PDF e podcast approvati. Il copione non è incluso |
| `publish`, `schedule`, `sync`, altre | nessuno | `SKIPPED`, exit 0, nessuna scrittura. Sono azioni da eseguire fuori dalla CLI, con i loro strumenti, solo se autorizzate |

Nel pacchetto Gate 2, se il catalogo le prevede, proponete le azioni locali per nome (`archive`, `export_markdown`, `author_website`) e indicate target e cartella di destinazione. Il Direttore sceglie; voi copiate.

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
| `Error: publishing destination already exists` | 1 | Output già presente; nulla sovrascritto (`[publishing].allow_overwrite = false`, default) | Riferire; non cancellare l'output esistente e non attivare `allow_overwrite` senza istruzione del Direttore (§3.6) |
| `Error: publishing destination overlaps protected project inputs` (o percorso non ammesso) | 1 | Cartella di `[publishing]` non valida | Riferire; la configurazione la decide il Direttore |

### 3.4 Una pubblicazione per ricevuta

Le destinazioni predefinite sono dentro `[paths].dist`, che fa parte del bundle del Gate 2: dopo la prima pubblicazione la ricevuta diventa `stale` e un secondo `publish` esce con exit 2. Se il Direttore autorizza sia `archive` sia `export_markdown`, le due strade sono: cartelle di `[publishing]` fuori da `dist/` (decisione di configurazione del Direttore), oppure un nuovo pacchetto Gate 2 dopo la prima pubblicazione. Non rigenerate la ricevuta da soli.

### 3.5 Canale «sito personale dell'autore» (`author_website`)

Per chi pubblica anche su un sito proprio (portfolio, blog personale) oltre che sul sito della redazione.

1. **Catalogo.** Il Direttore aggiunge `author_website` a `[gates.gate2].allowed_actions`. Facoltativo: `[publishing].target = "author_website"` e `author_website_dir = "<cartella>"`. Una cartella fuori da `[paths].dist` evita che l'export renda `stale` la ricevuta (§3.4).
2. **Gate 2.** Proponete l'azione per nome nel pacchetto; il Direttore la scrive nella frase di approvazione.
3. **Esecuzione.**
   ```bash
   editorial publish <post_id> --target author_website --dry-run --json
   editorial publish <post_id> --target author_website --json
   ```
4. **Contenuto dell'export.** `index.html` è generato dal template `templates/publish/author_website_article.html.jinja2`. Se esiste, ha la precedenza la copia del progetto in `[paths].templates/publish/`. La pagina contiene:
   - testata con nome dell'autore (`display_name` del profilo YAML, oppure `author` nel front matter della pagina Markdown) e bio breve;
   - titolo, sommario, data e tempo di lettura;
   - indice laterale fisso su desktop, con evidenza della sezione corrente;
   - player del podcast, se `podcast.m4a`/`.mp3` è nel bundle;
   - carosello sfogliabile (frecce e tastiera) con le slide approvate, iframe in `sandbox`, e link al PDF;
   - sezione «Chi scrive» e collegamenti alle pagine di trasparenza (`[transparency]`) su `[project].base_url`;
   - colophon con il `bundle_digest` del Gate 2.

   La pagina è offline-first: niente CDN, font remoti o tracker. I colori vengono da `[theme]`, il carattere del corpo da `font_family`.
5. **Pubblicazione in rete.** La CLI non carica nulla. Copiare la cartella sul server o sull'hosting del sito personale è un'operazione umana, fuori dalla CLI.

### 3.6 Sito statico (`static_site`): contenuto dell'export e opzioni Hugo

**Cosa viene esportato.** Filtro per estensione, senza distinzione tra maiuscole e minuscole, sugli artefatti del bundle Gate 2:

| Categoria | Estensioni | Condizione |
|---|---|---|
| Testo | Markdown della bozza | Sempre. Nome originale del file con `static_site_layout = "flat"`, `index.md` con `"hugo_bundle"` |
| Immagini | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg` | Sempre, se presenti nel bundle |
| Documenti | `.pdf` | Sempre (es. PDF del carosello) |
| Audio | `.mp3`, `.m4a`, `.ogg`, `.wav` | Solo se la ricevuta contiene l'azione `static_site` o `publish_audio`. Con il solo `export_markdown` l'audio **non** esce |
| Esclusi | `.html`, `.css` e ogni altra estensione | Sempre: slide HTML del carosello, console web offline (`dist/web/`), copione `podcast_script.md`, manifest JSON |

L'esclusione di `.html` e `.css` è deliberata e non si aggira: Hugo tratta un `.html` dentro `content/` come pagina da renderizzare, e l'HTML grezzo ricade sotto le policy di sicurezza di Hugo (`security.allowContent`, rendering non sicuro di Goldmark). Se servono le slide nel sito, si pubblicano come immagini o PDF, non come HTML.

Gli asset mantengono il percorso relativo al progetto sotto la cartella dell'unità: `dist/social/post_07/slide_01.png` diventa `<static_site_dir>/post_07/dist/social/post_07/slide_01.png`. I collegamenti nel Markdown vanno scritti di conseguenza (in un page bundle Hugo, relativi a `index.md`).

**Opzioni in `[publishing]`** (decisione di configurazione del Direttore, mai dell'agente):

```toml
[publishing]
target = "static_site"
static_site_dir = "site/content/posts"   # cartella content/ del sito Hugo
static_site_layout = "hugo_bundle"       # "flat" (default) | "hugo_bundle"
allow_overwrite = true                    # default false
```

- `static_site_layout = "hugo_bundle"`: ogni unità diventa un **leaf bundle** Hugo `<static_site_dir>/<post_id>/index.md` con i media accanto; l'URL dell'articolo è `/posts/<post_id>/` (salvo permalink diversi in `hugo.toml`) e i media sono disponibili come `.Resources`. Con `"flat"` il Markdown conserva il nome della bozza.
- `allow_overwrite = true`: se `<static_site_dir>/<post_id>/` esiste già, i file vengono riscritti invece di uscire con `Error: publishing destination already exists`. Serve per la **ripubblicazione** di un'unità già uscita (es. dopo una correzione F6 approvata e un nuovo Gate 2). Non cancella i file che nel nuovo bundle non ci sono più: si rimuovono a mano, su istruzione del Direttore. L'opzione vale solo per `static_site`; `dist_archive` e `author_website` non sovrascrivono mai.
- Con `static_site_dir` fuori da `[paths].dist` (come `site/content/posts`) la pubblicazione non rende `stale` il Gate 2 (§3.4). Il gate resta obbligatorio a ogni ripubblicazione: `allow_overwrite` non sostituisce una nuova ricevuta quando il bundle è cambiato.

La struttura del sito Hugo che riceve l'export (configurazione, pagine di trasparenza, layout con date localizzate, container Docker/Nginx, parametri Coolify, codifica UTF-8 senza BOM) è descritta in `SKILL.md`, §4 «Hugo Scaffolding».

## 4. Checklist rapida

- [ ] F5 attiva? Se no: `F5: skipped` nel pacchetto Gate 2.
- [ ] Audio solo da NotebookLM Studio (`--provider notebooklm`) o, in alternativa, copione `script_only`; nessun file da TTS mono-voce in `dist/`.
- [ ] Audio generato dal Micro-Taccuino d'Articolo `<slug>-<post_id>` (`EDITORIAL_AUDIO_ID`), non dal Taccuino Maestro.
- [ ] Dopo un `generation still pending`: nessun ripiego autonomo su `script_only` e nessun `--new`; puntata attesa e scaricata (§2.3).
- [ ] `--new` usato solo su autorizzazione esplicita del Direttore, per sostituire una puntata superata o bocciata all'ascolto, una volta per decisione.
- [ ] Dopo un `--new` riuscito: puntate superate eliminate dal taccuino (dal Direttore su Studio, oppure `nlm studio delete <taccuino> <artifact_id> --confirm` solo dopo la sua conferma esplicita); `nlm studio status` mostra un solo artefatto audio `completed` (§2.2).
- [ ] `--length short` (default) salvo diversa indicazione del Direttore; `--overview-format` scelto consapevolmente; regole del `--focus` lasciate intatte, voci da vietare aggiunte a `[register].extra_forbidden`.
- [ ] Con NotebookLM: `dist/audio/<post_id>/podcast.<m4a|mp3>` presente su disco e non vuoto **prima** di `editorial view <post_id>`.
- [ ] `build-audio` eseguito **prima** del pacchetto Gate 2; audio ascoltato per intero e confrontato con `factcheck.json`; controllo anti-cliché e anti-estrapolazione fatto (§2.5, punto 2); rilievi classificati per materialità (§2.5, punto 3): cifre, date o scale alterate, fatti contraddetti, inversioni concettuali gravi, enfasi, cliché ed `extra_forbidden` come finding P1 bloccanti; raccordi discorsivi coerenti con le fonti del taccuino, variazioni stilistiche e ambiguità ASR al più come note P3 per il Direttore, senza bloccare F5; copione riletto, nessun claim nuovo, checklist anti-cliché applicata.
- [ ] Pacchetto Gate 2 con percorso dell'audio, esito dell'ascolto, eventuali finding P1 e note P3, copione se presente, azioni proposte (`archive`, `export_markdown`) e destinazione.
- [ ] Frase del Direttore con le azioni; ricevuta scritta dopo; `check-gate 2` → `RECEIPT_VALID`.
- [ ] `publish --dry-run` mostrato; `publish` eseguito solo per i target autorizzati.
- [ ] Esito riferito con `bundle_digest`; nessun file aggiunto a `dist/` dopo la ricevuta.

## 5. Console Webredazionale (Editorial Hub)

La console riunisce gli asset locali di un articolo in una pagina responsive utilizzabile offline. Al termine del flusso, il Direttore o il redattore può consultarla per copiare i copy social, ascoltare il podcast ed esportare i file tramite download. Mostra ciò che esiste: una sezione «Non disponibile» indica un asset assente, che `view` non genera.

### 5.1 Funzionalità: sei schede

La console è una dashboard a schede, non una pagina a scorrimento continuo. Ogni scheda ha un indirizzo proprio (`#articolo`, `#social`, `#podcast`, `#carosello`, `#fonti`, `#pubblicazione`) e si raggiunge anche con le frecce della tastiera. In testa restano titolo, autore, registro, le fasi completate (F1–F5, G1, G2) e i badge dei due gate con data e ora in italiano nel fuso `[project].timezone` (per esempio «14 novembre 2026, ore 20:55»).

- **Articolo:** impaginazione da rivista, con sommario, firma, tempo di lettura e indice delle sezioni. Il Markdown della versione pubblicata (o della bozza) è reso come testo tipografico, senza riquadri monospaziati; i rimandi `[n]` aprono la fonte corrispondente nella scheda «Fonti». Se esistono entrambe le versioni, la bozza resta consultabile in «Confronta con la bozza di lavoro».
- **Social:** quattro schede affiancate per LinkedIn, Twitter/X, Newsletter (per esempio Substack/Ghost) e Instagram, con contatore rispetto al limite del canale (per X: numero di post del thread e lunghezza del più lungo su 280) e pulsante «Copia testo». Il successo mostra «Copiato!» e «Testo copiato». Se il browser impedisce l'accesso agli appunti compare l'istruzione di copiare con `Ctrl+C` o `Cmd+C`.
- **Podcast:** player per `podcast.m4a` o `podcast.mp3` con durata, formato, dimensione e download; il copione (`script.txt` o `podcast_script.md`) si apre con «Leggi il copione». La console riproduce l'audio già scaricato da NotebookLM Studio; non accede al taccuino e non avvia generazioni. L'ascolto integrale richiesto in F5 resta obbligatorio.
- **Carosello:** visualizzatore delle slide HTML o immagini con frecce, numeri, tastiera e swipe; download della slide corrente e del deck PDF quando esiste.
- **Fonti e trasparenza:** per ogni fonte titolo, autori, editore, data, tipologia e badge «Fonte ufficiale primaria» o «Fonte secondaria», più «Accesso libero» o «Accesso riservato» se `access` è dichiarato. I pulsanti aprono la pagina web (`url`), scaricano il PDF (`pdf`, oppure `url` che termina in `.pdf`), aprono la scheda DOI e la copia locale (`local_copy`). Le affermazioni collegate mostrano testo, citazione letterale, posizione nella fonte ed esito in chiaro: «Dato verificato · riscontro letterale» significa che la frase dell'articolo corrisponde a un passaggio testuale della fonte, alla pagina o sezione indicata.
- **Pubblicazione:** stato del Gate 2 con le azioni autorizzate, i tre passi (approvazione, esportazione, archiviazione con `publish`) e un'area per piattaforma: Ghost (copia Markdown), Substack e Medium (copia dell'articolo formattato), Hugo/Jekyll (download di `<post_id>.md` con front matter `title`, `description`, `date`, `author`). Segue l'elenco dei file **di questa unità**, raggruppati per tipo, e l'archivio `dist/packages/<post_id>.tar.gz` se esiste: non è un'esportazione dell'intero sito.

Gli stati dei gate derivano dai report o dalle ricevute disponibili: **non sono una nuova verifica** e non autorizzano alcuna azione. Colori e carattere seguono `[theme]` di `editorial.toml` (§5.4).

### 5.1-bis Indice della redazione

`editorial view` senza `<post_id>`, oppure `editorial view --all`, rigenera le console di tutte le unità e scrive `[paths].dist/web/index.html`: un catalogo con titolo, data, autore, fasi completate (F1 Fonti, F2 Bozza, F3 Verifica, G1, F4 Visual e social, F5 Audio, G2), stato sintetico («In lavorazione», «In produzione», «Pronto per la pubblicazione», «Pubblicato») e il link alla console di ciascun articolo. Ogni console rimanda all'indice con «← Tutti gli articoli». Un'unità illeggibile compare con il motivo, senza bloccare le altre. Anche l'indice è in `dist/`: rigenerarlo dopo la ricevuta Gate 2 la rende `stale`.

### 5.2 Modalità standard: file locale

Eseguite dalla radice del progetto editoriale:

```bash
editorial view post_07
editorial view post_07 --no-browser
```

Il comando genera `[paths].dist/web/post_07.html` (default `dist/web/post_07.html`) e, senza `--no-browser`, lo apre nel browser come file locale. `--no-browser` genera comunque l'HTML e stampa il percorso relativo. Serve Jinja2, incluso nell'extra `editorial-pipeline[social]`. CSS e JavaScript sono incorporati; audio e download usano collegamenti relativi: mantenete la struttura delle cartelle quando spostate la console.

**Preparazione e Gate 1.** Prima di porre la domanda del Gate 1 eseguite `editorial-pipeline view <post_id> --no-browser` e indicate al Direttore `dist/web/<post_id>.html` e `dist/web/index.html`: la console mostra bozza, fonti primarie e claim verificati. I file di `dist/` non fanno parte del bundle Gate 1, quindi `view` non invalida alcun digest di quel gate e non approva nulla.

**Preparazione e Gate 2.** Generate la console prima di calcolare il bundle del Gate 2, dopo aver ultimato kit e audio. `view` riscrive il file anche se esiste già; generarlo o rigenerarlo dopo la ricevuta può renderla `stale`. Dopo il Gate 2/pubblicazione, aprite direttamente l'HTML già preparato per consultarlo senza scritture. Se serve aggiornarlo con nuovi asset, riferite il cambiamento e presentate un nuovo pacchetto Gate 2 prima di ulteriori azioni soggette al gate. Non correggete la ricevuta per adattarla alla console.

### 5.3 Modalità di rete: server HTTP locale

```bash
editorial view post_07 --serve
editorial view post_07 --serve --port 8080 --no-browser
editorial view post_07 --serve --port 0
```

`--serve` rigenera la console e avvia un server HTTP locale fino a `Ctrl+C`, stampando l'URL da aprire. La porta predefinita è `8000`; `--port PORT` accetta `0`–`65535`, con `0` per una porta libera scelta dal sistema. Una porta esplicita occupata produce errore; `--port` ha effetto sul server solo con `--serve`. `--no-browser` mantiene attivo il server senza aprire automaticamente una finestra. Anche questa modalità va preparata prima del Gate 2 per evitare la rigenerazione dopo l'approvazione.

Il server ascolta **solo su `127.0.0.1`** e serve la console con i file collegati, senza elenchi di directory né configurazione. È utile per le prove HTTP sul computer della redazione. Il collegamento diretto da cellulare o da un altro computer della rete locale **non è supportato**: non esiste un'opzione per esporre il server sulla LAN. Per verificare il layout mobile sullo stesso computer usate l'emulazione dispositivi del browser; l'accesso da un dispositivo reale richiede un inoltro o un servizio separato configurato dalla redazione. La sola scelta della porta non abilita l'accesso dalla rete.

### 5.4 Tema visivo (`[theme]`)

```toml
[theme]
palette = "cobalt_tech"        # cobalt_tech | emerald | nordic_minimal | custom
accent_color = "#2563eb"       # facoltativo: prevale sul preset
background_color = "#f8fafc"
ink_color = "#0f172a"
font_family = "sans"           # sans | serif (corpo dell'articolo e delle slide)
```

La tabella è facoltativa: senza `[theme]` vale `cobalt_tech`. I colori sono accettati solo come `#rrggbb`. Lo stesso tema si applica a console, indice e slide generate da `build-visual`. Le slide già presenti in `dist/social/` mantengono l'aspetto con cui sono state generate finché non vengono ricostruite, e la ricostruzione richiede un nuovo Gate 2.
