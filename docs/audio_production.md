# Produzione audio F5 (`editorial build-audio`)

La fase F5 trasforma una bozza già approvata al Gate 1 in un podcast conversazionale prodotto con **Google NotebookLM Studio** o, in alternativa, in un copione da leggere e registrare con voci umane. È una fase **opzionale**: si attiva per progetto e non sostituisce né l'ascolto e la revisione umana né il Gate 2.

Posizione nel ciclo:

```text
F3 → Gate 1 → F4 ‖ F5 → controlli finali → Gate 2 → publish → F6
```

F5 lavora in parallelo a F4 (kit visual e social), sullo stesso digest approvato al Gate 1, e non modifica il file dell'unità. I suoi artefatti finiscono in `[paths].dist` e quindi nel bundle del Gate 2.

Riferimenti collegati: [`publishing.md`](publishing.md), [`rag_factcheck.md`](rag_factcheck.md) (NotebookLM per la verifica dei fatti), §4.3 del [manuale](manuale_configurazione_e_uso.md).

---

## 0. Standard editoriale: solo NotebookLM Studio

> **Direttiva del Direttore.** Il podcast di un'unità si produce **solo** con Google NotebookLM Studio (`provider = "notebooklm"`). I motori di sintesi vocale mono-voce generano audio di qualità scadente e non sono ammessi per la pubblicazione. L'unica alternativa è il copione documentale `script_only`.

Perché NotebookLM è il riferimento (gold standard) della redazione:

| | NotebookLM Studio (Audio Overview) | TTS sintetico mono-voce (`tts`, edge-tts, sintesi di sistema) |
|---|---|---|
| Forma | Conversazione a due conduttori, con domande, riprese e raccordi | Lettura continua di un testo da parte di una sola voce |
| Resa | Prosodia e ritmo vicini a un programma parlato; pause e intonazione seguono il senso | Cadenza piatta e uniforme, accenti e pause errati su numeri, sigle e nomi propri; resa percepita come robotica |
| Base | Fonti caricate nel taccuino più il `--focus` con i soli claim verificati, fonte e locator | Il copione così com'è, senza alcun legame con le fonti |
| Esito per la redazione | **Pubblicabile** dopo ascolto integrale e confronto con `factcheck.json` | **Non pubblicabile**: il provider `tts` è deprecato e resta solo per compatibilità |

Lo standard qualitativo non sospende il metodo: i conduttori di NotebookLM parafrasano e commentano, quindi l'audio si ascolta per intero e ogni fatto detto a voce deve avere il suo claim (§8). Le voci sono generate da un modello e la descrizione della puntata lo dichiara.

| Provider | Stato | Artefatto |
|---|---|---|
| `notebooklm` | Standard editoriale, unico motore audio ammesso | `podcast.m4a` (default) o `podcast.mp3` |
| `script_only` | Unica alternativa: copione per lettura umana o registrazione in studio | `podcast_script.md` |
| `tts` | Deprecato, vietato per la pubblicazione | — |

---

## 1. Sintassi

```text
editorial build-audio <post_id> [--provider notebooklm|script_only] [--format {m4a,mp3}] [--language it] [--dry-run] [--json] [--config editorial.toml]
```

| Argomento / opzione | Effetto |
|---|---|
| `<post>` | Unità di contenuto: `post_id`, nome file o percorso relativo dentro `[paths].content` |
| `--provider` | Provider audio: `notebooklm` (standard) o `script_only` (alternativa). Precedenza: `--provider` > `[audio].provider` > `[providers.audio].adapter` > `script_only`. `tts` è accettato solo per compatibilità, con avviso `DEPRECATED`, e non va usato |
| `--format` | Contenitore del file audio NotebookLM: `m4a` (default, formato nativo) o `mp3`. Non è lo stile della puntata (`deep_dive`, `brief`, … di `nlm audio create`) |
| `--language` | Lingua della puntata NotebookLM, codice breve (default `it`) |
| `--dry-run` | Restituisce il percorso previsto senza scrivere nulla e senza chiamare servizi esterni |
| `--json` | Stampa il risultato come JSON |
| `--config` | File di configurazione; la sua cartella è la radice del progetto |

## 2. La direttiva `phases.optional.F5`

```toml
[phases.optional]
F5 = true
```

Con `F5 = false` (valore del modello e della sandbox) il comando si rifiuta prima di ogni altra operazione:

```text
Error: Phase F5 is disabled in editorial.toml        (exit 1)
```

Il rifiuto vale anche con `--dry-run`: nessun file letto oltre alla configurazione, nessun provider chiamato, nessuna scrittura. Una fase disattivata si dichiara `skipped` nel pacchetto del Gate 2.

## 3. Prerequisiti: evidenze valide

Il copione si costruisce **solo** dalle affermazioni verificate. Prima di generare, `build-audio` esegue la verifica delle evidenze sulla bozza corrente (la stessa di `verify-facts`). Se c'è un `BLOCK` (evidenze mancanti, `factcheck.json` o `draft-review.json` `stale`, claim senza fonte) si ferma:

```text
Error: Audio requires current validated draft evidence        (exit 1)
```

Il materiale di partenza sono le fonti di `sources.json` e, per ciascuna, i claim di `factcheck.json` con il loro locator. Il provider non riceve frasi della bozza prive di claim e non aggiunge fatti.

## 4. Provider

### 4.1 `script_only` — copione offline (unica alternativa)

Provider di riserva: deterministico, senza rete, senza dipendenze aggiuntive. Si usa quando NotebookLM non è disponibile o l'unità non deve lasciare la macchina, e solo con l'assenso del Direttore. Scrive `podcast_script.md` con:

- titolo ricavato dalla prima intestazione `# ` della bozza (altrimenti il `post_id`);
- **Intro** con una domanda guida;
- un **Segmento** per ogni fonte, con ciascun claim in una riga `[Speaker]`, il suo `Riferimento:` (locator) e una `[Pausa]`;
- **Outro** con il rimando all'articolo, la nota sulla licenza (la licenza del software non copre i contenuti: valgono la licenza editoriale dell'articolo e quelle delle fonti) e il promemoria «revisione umana richiesta; pubblicazione soggetta al Gate 2».

Il copione è una base di lavoro: va riletto, passato dalla checklist anti-cliché e letto o registrato da voci umane. Non si converte in audio con un TTS mono-voce (§0). Rigenerarlo sovrascrive la versione precedente.

```bash
editorial build-audio post_07 --dry-run --json
editorial build-audio post_07
# BUILT: script_only
# dist/audio/post_07/podcast_script.md
```

### 4.2 `notebooklm` — Audio Overview con la CLI `nlm` (standard)

Genera il podcast conversazionale a due conduttori con Google NotebookLM Studio tramite la CLI `nlm` (pacchetto `notebooklm-mcp-cli`, lo stesso usato per la verifica dei fatti). Flusso:

1. `nlm audio create <taccuino> --confirm --json --focus "<claim verificati con fonte e locator>"`: il prompt chiede di parlare solo delle affermazioni verificate;
2. controllo dello stato con `nlm studio status`, al massimo 30 volte a intervalli di 2 secondi;
3. `nlm download audio` in una cartella temporanea; il file sostituisce `podcast.<formato>` solo se il download è riuscito e non è vuoto.

Una Audio Overview richiede spesso diversi minuti: se l'attesa limitata scade (`generation still pending after bounded polling`) si completa a mano con `nlm audio create`, `nlm studio status` e `nlm download audio` sullo stesso taccuino, scaricando nel percorso indicato da `--dry-run`. Procedura passo per passo: `skills/editorial-pipeline/references/publishing-and-audio.md` §2.3.

Prerequisiti:

```sh
uv tool install notebooklm-mcp-cli
nlm login                                   # eseguito dal titolare dell'account
nlm alias set podcast-post07 <notebook_id>   # alias locale del taccuino
export EDITORIAL_AUDIO_ID="podcast-post07"   # alias o id, mai in un file versionato
```

```toml
[phases.optional]
F5 = true

[audio]
provider = "notebooklm"
corpus_id_env = "EDITORIAL_AUDIO_ID"   # nome della variabile, non l'identificativo
timeout_seconds = 60                   # per ogni chiamata a nlm
```

Il taccuino deve esistere e contenere **solo** le fonti dell'unità (`sources.json`): l'adapter non carica corpus nuovi, e una fonte in più è materiale che i conduttori possono citare senza claim. Il testo dei claim e i locator vengono inviati a Google; per unità che non devono lasciare la macchina usate `script_only`.

Le chiavi `[audio]` accettate sono quelle della tabella del §5: formato e lingua si passano con `--format` e `--language` (default `m4a` e `it`).

Errori: ogni problema produce `AudioUnavailableError` con un messaggio protetto (nessun output grezzo di `nlm`, nessun identificativo) e exit `1`.

| Messaggio | Causa | Cosa fare |
|---|---|---|
| `notebook corpus is not configured` | Variabile `corpus_id_env` vuota o assente | Impostare la variabile d'ambiente |
| `CLI 'nlm' is unavailable` | `nlm` non installato o non nel `PATH` | Installare `notebooklm-mcp-cli` |
| `authentication required; run 'nlm login'` | Sessione scaduta | Il titolare ripete `nlm login` |
| `CLI request timed out` | Chiamata oltre `timeout_seconds` | Alzare il timeout o riprovare |
| `generation still pending after bounded polling` | Generazione non conclusa in circa un minuto | Riprovare più tardi |
| `audio generation failed`, `download did not produce an audio file` | Errore del servizio | Riprovare; un audio precedente resta intatto |

Ogni messaggio termina con `Retry or use --provider script_only.`: l'alternativa offline è sempre disponibile, ma la sceglie il Direttore. `duration_seconds` resta `null` quando la durata non è nota.

Ripiego automatico: se `notebooklm` arriva dalla configurazione (senza `--provider`) e manca `nlm` o il taccuino, la CLI stampa `Warning: … Falling back to script_only.` e scrive il copione. Con `--provider notebooklm` esplicito non c'è ripiego: exit 1. In nessun caso il ripiego è un TTS.

`--dry-run` con `notebooklm` non richiede credenziali, non esegue `nlm` e restituisce solo il percorso previsto.

## 5. Configurazione

| Chiave | Default | Note |
|---|---|---|
| `[phases.optional].F5` | `false` | Interruttore della fase; con `false` il comando si rifiuta |
| `[audio].provider` | `"script_only"` | `notebooklm` (raccomandato) o `script_only`. Se la sezione `[audio]` è presente prevale su `[providers.audio].adapter` |
| `[audio].corpus_id_env` | `"EDITORIAL_AUDIO_ID"` | **Nome** della variabile d'ambiente con l'identificativo del taccuino |
| `[audio].corpus_id` | assente | Ha la precedenza sulla variabile; non va valorizzato nei file versionati (zero-leak) |
| `[audio].timeout_seconds` | `60` | Timeout di ogni chiamata a `nlm`; numero finito maggiore di zero |
| `[providers.audio].adapter` | `"script_only"` | Usato solo senza `[audio]`: `notebooklm` (raccomandato), `script_only` o `none` (equivale a `script_only`). `tts` è deprecato e vietato per la pubblicazione; altri valori (`elevenlabs`, `openai_tts`, …) sono rifiutati con `Unsupported audio provider` |

## 6. Artefatti e Gate 2

Gli artefatti stanno in `[paths].dist/audio/<post_id>/`:

| Provider | File |
|---|---|
| `script_only` | `podcast_script.md` |
| `notebooklm` | `podcast.m4a` (default) o `podcast.mp3` |

La cartella deve restare dentro `[paths].dist` e fuori da `[paths].reports`: i report sono esclusi dal bundle del Gate 2, e un audio lì dentro sfuggirebbe all'approvazione. Il comando rifiuta sovrapposizioni con i report o con le cartelle editoriali protette.

Conseguenze pratiche:

- **F5 si chiude prima del Gate 2.** Copione e audio entrano negli `artifacts` del bundle e il Direttore li approva insieme al resto del kit.
- **Rigenerare dopo il Gate 2 lo invalida.** Un nuovo `build-audio`, o una modifica a mano del copione, cambia il bundle: `check-gate 2` risponde `Gate 2: stale receipt bundle or distribution kit` e `publish` si ferma con exit `2`. Serve un nuovo pacchetto e una nuova approvazione.
- **Distribuzione.** `publish --target dist_archive` include copione e audio nell'archivio; `static_site` esporta solo Markdown e asset visivi.

## 7. Risultato

```json
{
  "audio_files": [],
  "details": {},
  "duration_seconds": null,
  "provider": "script_only",
  "script_file": "dist/audio/post_01/podcast_script.md",
  "status": "DRY_RUN"
}
```

| `status` | Significato |
|---|---|
| `BUILT` | Artefatto scritto (`script_file` o `audio_files`) |
| `DRY_RUN` | Percorso previsto, nessuna scrittura |

Percorsi sempre relativi alla radice del progetto.

## 8. Procedura per l'agente

1. Controllate `[phases.optional].F5`. Se è `false`, dichiarate F5 `skipped` nel pacchetto del Gate 2 e non eseguite il comando.
2. Verificate che il Gate 1 sia valido (`check-gate 1 <post>`) e che `verify-facts` non abbia `BLOCK`.
3. `editorial build-audio <post_id> --provider notebooklm --dry-run --json` per il percorso previsto; poi `editorial build-audio <post_id> --provider notebooklm --format m4a --json`.
4. Ascoltate l'audio per intero e confrontatelo con `factcheck.json`: nessun fatto senza `claim_id`, nessun claim travisato. Annotate l'esito dell'ascolto. La descrizione della puntata dichiara le voci generate con NotebookLM.
5. Inserite audio, esito dell'ascolto (ed eventuale copione) nel pacchetto del Gate 2. Dopo la ricevuta del Gate 2 non rigenerate nulla in `[paths].dist`.

Con `notebooklm` in errore riferite il messaggio al Direttore e proponete `--provider script_only`: non cambiate provider da soli e non usate mai un TTS mono-voce. Un audio generato non approva nulla e non autorizza la pubblicazione.
