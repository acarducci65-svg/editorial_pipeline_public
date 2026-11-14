# Verifica dei fatti con RAG

In F3 la redazione individua le asserzioni verificabili, consulta fonti indipendenti e registra per ciascuna l'esito e un riferimento preciso. Occorre distinguere una fonte primaria da una secondaria, controllare contesto, data e localizzatore, risolvere contraddizioni e non promuovere affermazioni prive di supporto. La revisione umana valuta anche copertura e affidabilità: il controllo locale non estrae tutti i claim dalla bozza e non legge o interpreta semanticamente le fonti.

## Porta e adapter

`RagProvider` è una classe astratta con `capabilities() -> set[str]` e `verify(claims: list[str], evidence_path: Path) -> list[Finding]`. `LocalRagProvider` legge `sources.json` e `factcheck.json` dalla directory di evidenza; funziona offline e riproduce le decisioni registrate, non effettua ricerche o inferenza. Entrambi i file devono contenere liste di oggetti e lo stesso `post_id`.

Per ogni testo richiesto, il provider cerca una sola corrispondenza esatta in `claims`: `verified`, `verified_external` o `grounded_primary`, con `source_key` presente nelle fonti e `locator` non vuoto, producono `OK`; `grounded_secondary` produce `WARN`; assenza, duplicati e altri casi producono `BLOCK`. Per `grounded_secondary` il codice non verifica chiave e locator: il revisore deve comunque esaminarli. I campi configurati in `[factcheck]` non modificano questa logica.

`NotebookLMAdapter` interroga un taccuino Google NotebookLM tramite l'eseguibile `nlm` del pacchetto `notebooklm-mcp-cli`: una domanda per claim, risposta JSON tradotta in un finding `OK`, `WARN` o `BLOCK`. È descritto nella sezione [NotebookLM](#notebooklm-via-nlm) qui sotto. `verify-facts` sceglie il provider dalla sezione facoltativa `[rag]` di `editorial.toml`; se manca, usa `[providers.rag].adapter`.

## NotebookLM via `nlm`

NotebookLM si usa su due livelli indipendenti. Il primo serve all'agente per trovare i passaggi, il secondo alla CLI per un controllo automatico aggiuntivo. Nessuno dei due sostituisce `sources.json`, `factcheck.json` o il Direttore.

### Livello agente: server MCP `notebooklm-mcp`

Se l'harness dell'agente (Claude Code, Codex CLI, Antigravity) ha collegato il server MCP `notebooklm-mcp`, l'agente può usarne gli strumenti durante:

- **F1 — Inventario fonti.** `notebook_list` e `notebook_get` per individuare il taccuino della redazione; `source_add` per caricare una fonte primaria già scelta (URL, testo, file, documento Drive); `source_describe` e `source_get_content` per controllare titolo, contenuto e tipo prima di registrarla in `sources.json`. Il taccuino non decide quali fonti entrano: l'elenco va comunque sottoposto al Direttore.
- **F3 — Fact-checking della bozza.** `notebook_query` con una domanda per claim, che chiede il passaggio testuale e il punto della fonte (pagina, sezione, tabella). L'agente confronta il passaggio con il claim e scrive in `factcheck.json` esito, `source_key` e `locator` ricavati dalla fonte, non dalla sintesi del modello.

Regole per l'agente:

- La risposta di NotebookLM è un **indizio per trovare il passaggio**, non una prova. Prova è il passaggio della fonte primaria, letto e localizzato. Una risposta senza citazione vale come nessuna risposta (tabella delle fonti in `skills/editorial-pipeline/references/factchecking_protocol.md` §1).
- Al massimo `[providers.rag].max_claims_per_turn` interrogazioni per messaggio.
- L'identificativo del taccuino resta nella sessione: non va in `sources.json`, `factcheck.json`, ricevute, commit o report. Dove serve un riferimento stabile si usa un alias (`alias` nel server MCP, `nlm alias set` da terminale).
- Gli strumenti MCP che modificano o condividono un taccuino (`notebook_delete`, `source_delete`, `notebook_share_*`) richiedono la conferma esplicita del Direttore.

### Livello CLI: `editorial verify-facts` con `provider = "notebooklm"`

Con NotebookLM configurato, `verify-facts`:

1. esegue **prima** la verifica locale completa (schema, digest, esiti, fonti, locator, `draft-review.json`): le evidenze registrate restano obbligatorie;
2. per ogni claim di `factcheck.json`, in ordine, lancia senza shell `nlm query notebook <taccuino> "<domanda sul claim>" --json --timeout <timeout_seconds>`;
3. aggiunge un finding `rag.claim` per claim, identificato dalla posizione (`Claim 1: ...`), senza copiare nel report né il testo del claim né la risposta del modello.

Classificazione della risposta:

| Risposta di `nlm` | Stato | Messaggio |
|---|---|---|
| Citazioni assenti o vuote, oppure formule di smentita («not supported», «no evidence», «non supportat…», «nessuna evidenza», …) | `BLOCK` | `Claim N: not supported by notebook sources` |
| Citazioni presenti, ma risposta vuota o con formule di incertezza («partial», «uncertain», «parzial…», «incert…», …) | `WARN` | `Claim N: requires review of notebook evidence` |
| Citazioni presenti, nessuna smentita né incertezza | `OK` | `Claim N: supported by notebook sources` |

La classificazione è lessicale e prudente: un `OK` remoto dice che il taccuino ha restituito una risposta con citazioni senza smentite, non che il passaggio sostenga davvero il claim. Il confronto passaggio ↔ claim resta a carico dell'agente in F3 e del Direttore al Gate 1.

Se la verifica remota non è possibile, la CLI non emette un report parziale: stampa `Error: RagUnavailableError` ed esce con codice `1`. Cause: corpus non configurato, `nlm` assente dal `PATH`, sessione scaduta (stderr con «login», «auth» o «cookie»), timeout, codice di uscita diverso da zero, JSON non valido. L'errore grezzo di `nlm` viene scartato perché potrebbe contenere credenziali, identificativi o percorsi locali: per la diagnosi lanciate `nlm` a mano.

Il testo di ogni claim viene inviato a Google. Non usate `provider = "notebooklm"` per bozze che non possono uscire dalla macchina; in quel caso restate su `local`.

### Installazione e accesso

```bash
uv tool install notebooklm-mcp-cli          # installa gli eseguibili nlm e notebooklm-mcp
# in alternativa, nello stesso ambiente del framework:
pip install "./editorial_pipeline_public[rag]"   # dal sorgente; l'extra rag richiede Python >= 3.11
nlm --version
```

Su Python 3.10 l'extra `rag` non installa nulla: usate `uv tool install`, che crea un ambiente isolato con un interprete compatibile. L'adapter cerca `nlm` nel `PATH`.

Accesso, eseguito dalla persona titolare dell'account Google, non dall'agente in una sessione non presidiata:

```bash
nlm login                          # apre il browser e salva la sessione
nlm auth storage set protected     # conserva le credenziali in modalità protetta anziché in chiaro su file
nlm notebook list                  # controllo: elenca i taccuini accessibili
```

Quando la sessione scade, `verify-facts` termina con `Error: RagUnavailableError`: ripetete `nlm login`.

### Identificativo del taccuino (zero-leak)

L'identificativo del taccuino non si scrive in file versionati. Due modi:

```bash
# 1. variabile d'ambiente, nella shell dell'operatore
export EDITORIAL_RAG_ID="<identificativo del taccuino>"      # PowerShell: $env:EDITORIAL_RAG_ID = "..."

# 2. alias locale di nlm, conservato nel profilo utente; la variabile contiene solo il nome dell'alias
nlm alias set redazione-corpus "<identificativo del taccuino>"
export EDITORIAL_RAG_ID="redazione-corpus"
```

`nlm query notebook` accetta sia l'identificativo sia l'alias.

### Configurazione in `editorial.toml`

```toml
[rag]
provider = "notebooklm"            # local | manual | none | notebooklm
corpus_id_env = "EDITORIAL_RAG_ID" # NOME della variabile, mai l'identificativo
timeout_seconds = 60               # timeout per singola interrogazione (> 0)
```

Se `[rag]` è presente prevale su `[providers.rag].adapter`. Senza `[rag]`, `[providers.rag].adapter = "notebooklm"` usa `[providers.rag].corpus_id_env` e un timeout di 60 secondi. Esiste anche la chiave `corpus_id`, che ha la precedenza sulla variabile d'ambiente: va lasciata vuota nei file versionati e usata solo dalla libreria Python con valori passati a runtime. Ogni claim è un'interrogazione separata: con molti claim e taccuini ricchi di fonti la verifica può richiedere minuti, e conviene alzare `timeout_seconds`.

### Sovranità umana

I finding dell'adapter NotebookLM sono controlli automatici, come quelli locali. Un report senza `BLOCK`:

- non approva il Gate 1 né il Gate 2;
- non genera, firma o integra ricevute in `approvals/`;
- non sostituisce il messaggio del Direttore in chat con la frase di approvazione.

`check-gate` rifà i controlli locali (non interroga NotebookLM) e accetta solo ricevute che riportano l'approvazione del Direttore. Un agente che presentasse un esito di NotebookLM come approvazione commetterebbe una Ghost Approval.

## Formato delle evidenze

Esempio minimo compatibile con il provider; i campi descrittivi aiutano la revisione e non sono tutti validati dal motore:

```json
{
  "schema_version": 1,
  "post_id": "post_01",
  "sources": [
    {"key": "fonte-1", "title": "Rapporto di esempio", "type": "report", "primary": true, "local_copy": "evidence/sources/rapporto.txt"}
  ]
}
```

```json
{
  "schema_version": 1,
  "post_id": "post_01",
  "claims": [
    {"id": "C1", "text": "Una misura riportata nel rapporto.", "outcome": "grounded_primary", "source_key": "fonte-1", "locator": "pagina 2, tabella 1"}
  ]
}
```

`key` identifica la fonte, `source_key` la collega al claim e `locator` precisa il punto consultato. La sandbox aggiunge campi come `url`, `accessed`, `tags`, `promotable` e `summary`; citazione, testo estratto, spiegazione e punteggio di confidenza possono essere annotati come metadati supplementari, ma non sono campi obbligatori né valutati dal codice. Non esiste nello schema implementato una classificazione `VERIFIED`/`CONTRADICTED`/`UNVERIFIABLE` o uno score di confidenza: gli esiti effettivi sono le stringhe minuscole sopra descritte e i finding `OK`/`WARN`/`BLOCK`.

## Uso CLI

Dalla radice del repository, usando la sandbox:

```bash
editorial-pipeline verify-facts post_01_valid --config examples/sample_blog/editorial.toml
editorial-pipeline verify-facts post_01_valid --config examples/sample_blog/editorial.toml --json
editorial-pipeline validate-draft post_01_valid --config examples/sample_blog/editorial.toml
```

Il nome è cercato in `paths.content`; l'identificativo ricavato determina la directory `paths.evidence/post_01/`. Non esistono le opzioni `--draft` e `--sources`: il post è posizionale e le fonti si trovano tramite configurazione. `verify-facts` legge i testi dal file di fact-check, richiede almeno un claim, stampa JSON anche senza `--json` e restituisce 1 in caso di `BLOCK` o errore, 0 altrimenti. Un `WARN` non produce da solo un errore. `validate-draft` verifica soltanto la presenza dei due file, non il loro contenuto.
