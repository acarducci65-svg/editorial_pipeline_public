# Gate umani ed evidenze

Reference per i due gate del ciclo editoriale: cosa mostrare al Direttore, come si calcola il digest versionato, come si scrive la ricevuta (schema v1 con bundle di digest) e come la verifica `check-gate`, quando un'approvazione diventa `stale`.

Principio guida: **la ricevuta rende verificabile *cosa* è stato approvato e su quale versione. Non autentica *chi* ha scritto in chat, e non sostituisce mai il messaggio umano.**

Posizione dei gate nel ciclo:

```
F0 → F1 → F2a → F2b → F3 → ══ GATE 1 (bozza verificata) ══ → F4 ‖ F5 → ══ GATE 2 (pubblicazione) ══ → F6
```

Il fact-checking (F3) **precede** il Gate 1: il Direttore firma una bozza di cui conosce già la tenuta fattuale, e il digest approvato è quello che va in promozione.

---

## 1. Digest versionato

La CLI identifica una versione di un file (unità, evidenza, ricevuta, artefatto del kit) con un digest versionato:

```
v1:<sha256( <percorso relativo POSIX dalla radice del progetto> + "\0" + <byte del file con CRLF normalizzato a LF> )>
```

- Il prefisso `v1:` indica l'algoritmo. Un digest senza prefisso o con un'altra versione non è accettato nelle ricevute.
- Il percorso relativo fa parte del digest: rinominare o spostare il file cambia il digest.
- I fine riga `CRLF` sono normalizzati a `LF` prima del calcolo: lo stesso file ha lo stesso digest su Windows e su Linux. Qualsiasi altra modifica (testo, frontmatter compreso `status:`, spazi) cambia il digest.
- Il digest corrente dell'unità si legge dal campo `digest` del report:

```bash
editorial-pipeline validate-draft content/posts/post_07_titolo.md --json
```

```json
{
  "posts": [
    {
      "digest": "v1:3f9a1c2e7b…e41d",
      "evidence": "evidence/post_07",
      "findings": [],
      "rel_path": "content/posts/post_07_titolo.md",
      "state": "OK"
    }
  ]
}
```

Il digest delle evidenze e degli artefatti non ha un comando dedicato: lo stesso algoritmo si applica a ogni file, e `check-gate` stampa nel campo `bundle` i digest che ha ricalcolato.

Nei pacchetti si mostra il **digest abbreviato** (`v1:` + primi 8–12 caratteri); nelle evidenze e nelle ricevute si usa il **digest completo**.

## 2. Pacchetto Gate 1 — Bozza verificata

### 2.1 Prerequisiti

- F2b e F3 completate sullo **stesso digest**.
- `validate-draft --json` senza `BLOCK` (nessun `BLOCK` è ammesso: nemmeno `evidence.missing`).
- `verify-facts --json` senza `BLOCK`.
- `draft-review.json` con tutte le chiavi `pass`, aggiornato dopo le frasi riscritte in F3.
- `factcheck.json` con `draft_digest` uguale al digest corrente e **copertura completa** della bozza (vedi 2.2, passo 3).

### 2.2 Preparazione di `draft-review.json` e `factcheck.json`

Il Direttore decide su due evidenze lette insieme: la revisione di stile e il fact-check. L'agente le prepara in quest'ordine:

1. **`draft-review.json`** (F2b): esiti delle voci di `humanizer_checklist.md`. Campi letti dalla CLI:

   ```json
   {
     "schema_version": 1,
     "post_id": "post_07",
     "draft_digest": "v1:3f9a1c2e7b…e41d",
     "reviewer": "<etichetta del revisore>",
     "reviewer_is_author": false,
     "items": {
       "empty_emphasis": "pass",
       "negative_parallelism": "pass",
       "isolated_lines": "pass",
       "vague_attribution": "pass",
       "decorative_bold": "pass",
       "invented_autobiography": "pass"
     }
   }
   ```

   `post_id` e `draft_digest` devono coincidere con l'unità corrente; ogni voce di `[humanizer].required_items` deve valere `pass`. Altri campi (`reviewer`, `items_detail`, …) sono documentali. Prova testuale in `draft-review.md`.
2. **`factcheck.json`** (F3): claim estratti dalla bozza **dopo** F2b, ciascuno con `text` presente alla lettera nella bozza, esito, `source_key`, locator; claim esclusi per natura in `excluded`; errori in `pre_publication_errors`. Schema in `factchecking_protocol.md` §5.
3. **Controllo con la CLI.** `verify-facts` controlla entrambi i file: digest uguale a quello corrente (`rag.stale_factcheck`, `humanizer.stale_review` → `BLOCK`), voci F2b a `pass`, esiti, fonti e locator, e la presenza di ogni `claims[].text` nella bozza (`rag.claim_not_in_draft` → `WARN`). Il pacchetto si compone solo con zero `BLOCK` e zero `rag.claim_not_in_draft`.
4. **Controllo di copertura, a carico dell'agente.** La CLI non sa quali frasi della bozza sono fattuali. Prima del pacchetto l'agente verifica a mano che ogni frase con numeri, date, nomi propri, attribuzioni o virgolette abbia un claim o una voce in `excluded`.
5. **Riallineamento dopo F3.** Se F3 ha cambiato frasi, la revisione di stile delle frasi nuove si aggiunge a `draft-review.md` (sezione «Frasi riscritte in F3») e `draft-review.json` e `factcheck.json` ricevono il nuovo digest. I tre digest (report, `draft-review.json`, `factcheck.json`) devono coincidere.

Esempio completo e funzionante: `examples/sample_blog/evidence/post_01/`.

### 2.3 Contenuto del pacchetto

Presentato in chat in un unico messaggio:

| # | Voce | Fonte del dato |
|---|---|---|
| 1 | Percorso del file integrale e invito esplicito a leggerlo per intero; se è una ripresentazione, diff rispetto alla versione precedente | file dell'unità |
| 2 | Titolo, sommario, numero di parole e tempo di lettura stimato | calcolo sull'unità |
| 3 | Registro di stile attivo | `editorial.toml [register].active` |
| 4 | Esito di `validate-draft`: nessun `BLOCK`; elenco dei `WARN` con motivazione | report CLI |
| 5 | Checklist anti-cliché: esito di ciascuna delle 10 voci | `draft-review.json` + prova |
| 6 | Tabella dei claim: `id`, testo, esito, fonte (`key`), locator, `promotable` | `factcheck.json` |
| 7 | Claim esclusi per natura (opinioni, previsioni) con motivo | `factcheck.json` `excluded` |
| 8 | Esito di `verify-facts`: totale claim, `OK`, `WARN` (`grounded_secondary` dichiarati nel testo) | report CLI |
| 9 | Errori intercettati in stesura, revisione e F3, con prima/dopo | `pre_publication_errors` + note di revisione |
| 10 | Frasi cambiate da F3, prima/dopo | `draft-review.md` |
| 11 | Dichiarazione di copertura: «ogni frase fattuale della bozza è in `factcheck.json` o in `excluded`, controllato a mano» | controllo 2.2, passo 4 |
| 12 | Digest abbreviato (uguale in report, `draft-review.json`, `factcheck.json`) | report CLI |
| 13 | Domanda di approvazione con la frase esatta da scrivere | `[gates.gate1].question` |

Esempio di chiusura del pacchetto:

> **Digest:** `v1:3f9a1c2e7b`
> Approvi questa bozza verificata (digest `v1:3f9a1c2e7b`) per passare alla promozione? Rispondi «Approvo Gate 1 #post_07» oppure indica le correzioni.

Dopo la domanda l'agente **termina il turno**. In esecuzione non interattiva scrive il pacchetto in `evidence/<post_id>/gate1-package.md` ed esce.

Il Gate 1 autorizza **solo** il passaggio a F4/F5 sul digest indicato. Non autorizza pubblicazione, programmazione, sincronizzazione, commit o push.

## 3. Pacchetto Gate 2 — Pubblicazione

Prerequisiti: Gate 1 valido sul digest corrente; F4 (e F5, se attiva) completate; controlli finali rieseguiti (`validate-draft` e `verify-facts` senza `BLOCK`, stesso digest del Gate 1).

| # | Voce | Fonte del dato |
|---|---|---|
| 1 | Conferma che il digest corrente coincide con quello approvato al Gate 1 | report CLI + `approvals/gate1.json` |
| 2 | Esito di `verify-facts`: totale claim, `OK`, `WARN` | report CLI |
| 3 | Anteprime del carosello (prima e ultima slide almeno) e percorso del manifest | `build-visual` |
| 4 | Testi integrali di ogni copy promozionale, per canale; copione audio se F5 è attiva | kit F4/F5 |
| 5 | Tabella dati promozionali: dato, `claim_id`, esito, fonte, locator | `factcheck.json` |
| 6 | Esito della revisione anti-cliché del kit | `social-review.json` + prova |
| 6-bis | Solo `investigative`: richieste di replica (destinatario per ruolo, data, canale, esito o assenza di risposta) e conferma che data ed esito compaiono nel testo | prova testuale F2b |
| 7 | Data e ora di uscita nel fuso del progetto, con equivalente UTC | `[project].timezone` |
| 8 | Elenco dei file che verranno pubblicati o sincronizzati (percorsi relativi, compilato dall'agente se il progetto non ha un comando di deploy con dry-run) | agente |
| 9 | Azioni **proposte**, scelte tra `[gates.gate2].allowed_actions` (es. `publish`, `schedule`) | proposta dell'agente |
| 10 | Domanda di approvazione con la frase esatta, comprensiva di azioni | `[gates.gate2].question` |

Esempio di chiusura:

> Approvi la pubblicazione di #post_07 il 20 novembre 2026 alle 08:00 (Europe/Rome; 07:00 UTC)? Azioni proposte: `publish`, `schedule`. Rispondi «Approvo Gate 2 #post_07 azioni: publish, schedule» indicando solo le azioni che autorizzi.

**Perimetro delle azioni.** L'approvazione del Direttore deve contenere esplicitamente le azioni autorizzate. Le azioni valide sono **solo** quelle scritte dal Direttore, non quelle proposte dall'agente. Se il Direttore scrive «Approvo Gate 2 #post_07 azioni: schedule», l'agente non esegue `publish`. Una frase senza elenco di azioni non vale come Gate 2: si chiede quali azioni autorizza.

## 4. Ricevute (schema v1)

Dopo il messaggio del Direttore, e mai prima, l'agente che lo ha ricevuto scrive la ricevuta in `evidence/<post_id>/<[gates].receipts_dir>/gate<N>.json` (default `approvals/`). Lo schema è **chiuso**: un campo in più, un tipo diverso o un digest senza prefisso `v1:` rendono la ricevuta invalida.

`approvals/gate1.json`:

```json
{
  "schema_version": 1,
  "gate": 1,
  "post_id": "post_07",
  "role": "Direttore",
  "decision": "approved",
  "timestamp": "2026-11-18T10:42:00+01:00",
  "excerpt": "Approvo Gate 1 #post_07",
  "bundle": {
    "draft_digest": "v1:…",
    "sources_digest": "v1:…",
    "factcheck_digest": "v1:…",
    "review_digest": "v1:…"
  }
}
```

`approvals/gate2.json`:

```json
{
  "schema_version": 1,
  "gate": 2,
  "post_id": "post_07",
  "role": "Direttore",
  "decision": "approved",
  "timestamp": "2026-11-19T17:05:00+01:00",
  "excerpt": "Approvo Gate 2 #post_07 azioni: publish, schedule",
  "allowed_actions": ["publish", "schedule"],
  "bundle": {
    "draft_digest": "v1:…",
    "gate1_digest": "v1:…",
    "artifacts": {
      "dist/social/post_07/manifest.json": "v1:…",
      "dist/social/post_07/slide_01.html": "v1:…"
    }
  }
}
```

| Campo | Regola |
|---|---|
| `schema_version`, `gate` | Interi (`1`; `1` o `2`), non stringhe |
| `post_id` | Uguale al `post_id` dell'unità |
| `role` | Uguale a `[gates].approver_role`: etichetta del **ruolo**, mai un nome proprio |
| `decision` | Solo `approved`. Rifiuti e richieste di correzione non si scrivono qui (vedi sotto) |
| `timestamp` | Data e ora ISO 8601 con offset di fuso esplicito (`+01:00` o `Z`) |
| `excerpt` | Messaggio del Direttore parola per parola. Deve contenere la frase `[gates.gateN].approval_phrase` con `{unit_id}` risolto, come frase intera; non deve contenere negazioni o condizioni (`non`, `se`, `salvo`, `purché`, `qualora`, `a patto`, `not`, `if`, `unless`, `pending`, …) né voci di `[gates].forbidden_excerpts` |
| `bundle` (Gate 1) | Digest `v1:` di bozza, `sources.json`, `factcheck.json`, `draft-review.json` al momento del pacchetto |
| `bundle` (Gate 2) | Digest della bozza, digest del file `approvals/gate1.json`, e mappa `percorso relativo → digest` di **ogni** file in `[paths].dist` |
| `allowed_actions` (Gate 2) | Non vuoto, senza duplicati, sottoinsieme di `[gates.gate2].allowed_actions`; ogni azione deve comparire nell'`excerpt`. Si copia dalla frase del Direttore, mai dalla proposta dell'agente |

Regole:

- **Rifiuti.** «Rifiuto Gate N», una richiesta di correzioni o un'approvazione condizionata («approvo, ma cambia X») si registrano in un file separato, `approvals/gateN-changes-<n>.json` (estratto letterale, timestamp, fase di ritorno), che la CLI non legge. Un `gateN.json` non più valido si elimina.
- **Metadati di sessione.** Riferimenti al messaggio, ora di pubblicazione, elenco dei file da pubblicare e etichetta dell'agente che registra vanno in un file a parte (es. `approvals/gate2-notes.md`), non nella ricevuta. Riferimenti solo **locali e opachi** (es. `sessione-2026-11-18/msg-14`): mai identificativi di conversazione, notebook o progetto di piattaforme cloud.
- Una ricevuta non si scrive sulla base di un'approvazione riferita da un altro agente, né si ricostruisce a posteriori.

Esempio completo e funzionante: `examples/sample_blog/evidence/post_01/approvals/`.

## 5. Verifica con `check-gate`

```bash
editorial-pipeline check-gate 1 content/posts/post_07_titolo.md
editorial-pipeline check-gate 2 content/posts/post_07_titolo.md
```

Sequenza dei controlli, che si ferma al primo fallimento:

1. Linter di stile e verifica delle evidenze (gli stessi di `validate-draft` e `verify-facts`): un solo `BLOCK` ferma il gate.
2. `approvals/gate1.json`: schema v1, `gate` e `post_id` corrispondenti, `role` uguale a `[gates].approver_role`, `excerpt` valido.
3. Bundle del Gate 1 ricalcolato sui file correnti e confrontato con la ricevuta.
4. Solo Gate 2: `approvals/gate2.json` con le stesse regole, `allowed_actions` ammesse e citate nell'`excerpt`, bundle ricalcolato (bozza, `gate1.json`, ogni file in `[paths].dist`).

| Esito | Exit | Significato | Cosa fare |
|---|---|---|---|
| JSON con `"status": "RECEIPT_VALID"`, `gate`, `post_id`, `role`, `timestamp`, `allowed_actions`, `bundle` | 0 | Ricevuta formalmente valida e legata ai file correnti | Proseguire, solo se il messaggio del Direttore esiste davvero |
| `Gate blocked by BLOCK findings: <codici>` | 2 | Linter o evidenze con `BLOCK` | Risolvere e rifare il pacchetto |
| `Gate N: missing or invalid receipt` | 2 | Ricevuta assente, JSON non valido o schema non rispettato | Nessun gate senza ricevuta conforme |
| `Gate N: receipt gate/post mismatch`, `receipt approver role mismatch` | 2 | Ricevuta di un altro gate, unità o ruolo | Correggere solo se è un errore di trascrizione del messaggio esistente |
| `receipt excerpt lacks unconditional human approval` | 2 | Frase assente, condizionata o con formule vietate | Chiedere di nuovo con la frase esatta |
| `Gate 1: stale receipt bundle` | 2 | Bozza o evidenze cambiate dopo l'approvazione | Nuovo pacchetto e nuovo Gate 1 |
| `Gate 2: actions not permitted or absent from excerpt` | 2 | Azioni non configurate, duplicate o non scritte dal Direttore | Chiedere quali azioni autorizza |
| `Gate 2: stale receipt bundle or distribution kit` | 2 | Bozza, `gate1.json` o un file di `[paths].dist` cambiati | Nuovo pacchetto e nuovo Gate 2 |
| `Gate: invalid or unreadable bundle` | 2 | Un file del bundle (es. `draft-review.json`) è illeggibile | Ripristinare l'evidenza |
| `Error: …` | 1 | Unità non trovata o configurazione non valida | Correggere percorso o `editorial.toml` |

L'opzione `--token` è deprecata: è accettata per compatibilità ma ignorata, e non sostituisce mai la ricevuta.

Procedura obbligata:

1. Pacchetto mostrato con il digest abbreviato.
2. Messaggio esplicito del Direttore, con ruolo utente, con la frase di approvazione (e, al Gate 2, le azioni).
3. Ricevuta scritta con i digest ricalcolati sui file mostrati nel pacchetto.
4. `check-gate` con esito `RECEIPT_VALID`.
5. Output della CLI salvato accanto alla ricevuta (es. `approvals/gate1.check.json`), fuori da `[paths].dist`.

**Limite formale.** `check-gate` dimostra che la ricevuta è conforme e legata ai file correnti; non può dimostrare che un essere umano l'abbia dettata. Ogni campo della ricevuta è scrivibile dall'agente: una ricevuta scritta prima del messaggio del Direttore, o senza di esso, è una Ghost Approval anche se la CLI risponde `RECEIPT_VALID`.

**Kit condiviso.** Il bundle del Gate 2 comprende ogni file di `[paths].dist`, non solo quelli dell'unità: generare il carosello di un'altra unità o aggiungere un report in `dist/` dopo la ricevuta rende `stale` il Gate 2 già registrato.

## 6. Invalidazione

| Evento | Diventa `stale` o invalido |
|---|---|
| Modifica del testo o del frontmatter dell'unità (anche solo `status:`) | `draft-review.json`, `factcheck.json`, Gate 1, kit promozionale, Gate 2 |
| Spostamento o rinomina del file | Digest, quindi Gate 1 e Gate 2 |
| Modifica di `sources.json` | `factcheck.json`, Gate 1 (`sources_digest`), Gate 2 |
| Modifica di `factcheck.json` | Gate 1 e Gate 2 (il fact-check fa parte di ciò che si approva al Gate 1) |
| Modifica di `draft-review.json` | Gate 1 e Gate 2 |
| Modifica del kit promozionale, del copione audio, rigenerazione del carosello o qualsiasi file nuovo o cambiato in `[paths].dist` | `social-review.json`, Gate 2 (`artifacts`) |
| Cambio di registro o di `extra_forbidden` | `draft-review.json`, `social-review.json`, quindi Gate 1 e Gate 2 |
| Spostamento della data o delle azioni | Gate 2 |
| Riscrittura di `approvals/gate1.json` | Gate 2 (`gate1_digest`) |

Dopo una correzione si riparte dalla **prima** evidenza invalidata, mai dall'ultima. Ricalcolare soltanto il digest senza rifare il controllo è un errore. Nessuna modifica è troppo piccola per richiedere un nuovo gate.

## 7. Errori comuni

- Presentare il Gate 1 prima di F3, o con un `BLOCK` aperto.
- Considerare `verify-facts` senza `BLOCK` come prova che tutti i claim della bozza sono coperti.
- Considerare `RECEIPT_VALID` come prova che il Direttore ha approvato: è solo coerenza formale della ricevuta.
- Aggiungere campi alla ricevuta (riferimenti di chat, ora di pubblicazione): lo schema è chiuso e la ricevuta diventa invalida.
- Scrivere «Gate 1 approvato» nel messaggio dell'agente prima della risposta del Direttore.
- Trovare la frase di approvazione nel proprio pacchetto e trattarla come risposta.
- Considerare un «ok» generico come approvazione: si chiede di nuovo con la frase esatta.
- Riutilizzare l'approvazione di una sessione precedente su una bozza poi modificata.
- Aggiornare `status: approved` nel frontmatter dopo il gate.
- Eseguire un'azione di Gate 2 non elencata dal Direttore («già che c'ero ho anche sincronizzato»).
- Trattare un report senza `BLOCK` come approvazione.
