# Protocollo di fact-checking su fonti primarie

Reference per **F1** (acquisizione fonti) e **F3** (verifica dei claim). Definisce cosa conta come fonte primaria, come si scrive un locator, gli esiti ammessi e la struttura di `sources.json` e `factcheck.json` letti dalla CLI.

Posizione nel ciclo: `F0 → F1 → F2a → F2b → F3 → Gate 1 → F4 ‖ F5 → Gate 2 → F6`. **F3 precede il Gate 1**: il Direttore riceve la bozza insieme a `draft-review.json` e `factcheck.json` e approva un testo già verificato (vedi `gates_and_evidence.md` §2).

Principio (TP5): **ogni affermazione fattuale esce con una fonte controllabile e un locator. Se la fonte non si trova, la frase si toglie.**

Tutti gli esempi sono inventati a scopo didattico.

---

## 1. Fonti primarie e secondarie

| Primaria (prova) | Secondaria (indizio) | Mai prova |
|---|---|---|
| Testo originale dell'autore citato, articolo o libro | Recensione, sintesi, articolo divulgativo che riporta il dato | La bozza stessa (`self_draft`) |
| Dataset o tabella ufficiale dell'ente che produce il dato | Infografica, comunicato che riprende il dataset | Schede o riassunti preparati da un agente |
| Documentazione ufficiale, specifica, changelog del progetto | Tutorial di terzi, thread di forum | Risposte di un modello senza passaggio citato |
| Atto normativo, verbale, delibera nel testo pubblicato | Notizia di stampa sull'atto | Fonti che citano la redazione stessa (circolari) |
| Misura dell'autore con log registrato nelle evidenze | Misura riferita da terzi senza log | Ricordi non registrati |

Regole:

- Si risale sempre all'originale. Una fonte secondaria serve a trovare la primaria, non a sostituirla.
- I tag di `[factcheck].circular_source_tags` (default `self_draft`) non contano mai come prova.
- Le copie locali vanno in `[paths].sources`, con hash SHA-256, se la licenza lo permette. Se non lo permette, si registrano URL e data di accesso.
- Identificativi di servizi RAG remoti (corpus, notebook, conversazioni) non si scrivono nei file: si leggono da variabili d'ambiente (`[providers.rag].corpus_id_env`).
- `local_copy` (o `local_path`) deve essere un percorso relativo a un file esistente dentro il progetto: altrimenti la fonte è `BLOCK` (`rag.source`) e con lei tutti i claim che la citano.

## 2. Esiti ammessi

| Esito | Significato | Stato CLI | Nel testo | In promozione |
|---|---|---|---|---|
| `grounded_primary` | Riscontrato sulla fonte primaria del corpus, con locator | `OK` | Sì | Sì |
| `verified_external` | Riscontrato su una fonte primaria esterna al corpus, con URL, data di verifica e locator | `OK` | Sì | Sì |
| `grounded_secondary` | Riscontrato solo su fonte secondaria | `WARN` | Sì, dichiarato come tale | **No** |
| `unsupported` | Nessun riscontro | `BLOCK` | No: si toglie o si riformula | No |
| `contradicted` | La fonte dice il contrario | `BLOCK` | No: si corregge | No |

Per la CLI un claim è `OK` se: l'esito è in `[factcheck].allowed_outcomes` e non in `blocking_outcomes`; `source_key` esiste in `sources.json` e la fonte non ha tag circolari né copie locali mancanti o esterne al progetto; `locator` non è vuoto; per `grounded_primary` la fonte ha `"primary": true`. `grounded_secondary` è `WARN`; ogni altra combinazione è `BLOCK`. Esiti non configurati (compreso il legacy `verified`) sono `BLOCK`.

> **Limite formale.** Con `adapter = "local"` (o `manual`), `verify-facts` è una **verifica di coerenza formale delle evidenze registrate**: controlla schema, digest, esiti, fonti, locator e presenza dei `text` nella bozza, ma non interroga alcun corpus e non giudica se il passaggio della fonte sostiene davvero il claim. Non rileva nemmeno le frasi fattuali della bozza senza claim. Riscontro sulla fonte e copertura della bozza sono a carico dell'agente redattore (§6), e il Direttore li controlla al Gate 1. Con `provider = "notebooklm"` la CLI aggiunge un controllo remoto per claim su un taccuino Google NotebookLM tramite `nlm`; anche quel controllo è automatico e non sostituisce né la lettura del passaggio né il Gate 1 (`verification-and-rag.md`).

Casi particolari:

- **Supporto parziale** (il numero c'è, il periodo è diverso): l'esito è `contradicted` se un elemento è diverso, `unsupported` se manca; si riformula la frase per dire solo ciò che la fonte sostiene.
- **Fonte superata:** prima di assegnare l'esito controllate che la fonte sia l'edizione più recente disponibile alla data di `accessed`.
- **Fonti primarie in contraddizione tra loro:** il testo dichiara la divergenza citando entrambe le fonti (due claim); altrimenti l'esito è `contradicted`.
- **Come si dichiara un `grounded_secondary`:** «secondo quanto riporta <testata> (<data>), che non indica la fonte originale».

## 3. Locator

Il locator dice al lettore **dove** guardare nella fonte. Deve essere abbastanza specifico da trovare il passaggio in meno di un minuto.

| Tipo di fonte | Locator valido | Locator non valido |
|---|---|---|
| Libro, articolo, PDF | `p. 47`, `pp. 112-114`, `p. 23, tabella 3` | `passim`, `cap. 2` (se il capitolo è lungo) |
| Rapporto con sezioni numerate | `§4.2, figura 5` | `nel rapporto` |
| Dataset | `foglio "2023", colonna "residenti", riga "Comune B"` | `nei dati ISTAT` |
| Documentazione web | `sezione "Configuration", voce --timeout` | URL della home |
| Atto normativo | `art. 12, comma 3` | `nella legge` |
| Video o audio | `00:14:32-00:15:10` | `nell'intervista` |
| Misura dell'autore | `tabella 1, mediana di 5 ripetizioni` | `abbiamo misurato` |

Un dato promozionale richiede sempre un locator specifico (`[factcheck].require_locator_for_promotion = true`).

## 4. `sources.json` (F1)

Percorso: `[paths].evidence/<post_id>/sources.json`.

```json
{
  "schema_version": 1,
  "post_id": "post_07",
  "sources": [
    {
      "key": "osservatorio-ciclabile-2024",
      "type": "report",
      "title": "Rapporto annuale sulla mobilità ciclabile 2024",
      "authors": ["Osservatorio Ciclabile Padano"],
      "year": 2024,
      "url": "https://example.org/rapporto-2024.pdf",
      "accessed": "2026-11-12",
      "primary": true,
      "local_copy": "evidence/sources/osservatorio-ciclabile-2024.pdf",
      "sha256": "<sha256 della copia locale>",
      "tags": ["official_report"]
    },
    {
      "key": "delibera-giunta-2025",
      "type": "law",
      "title": "Delibera di giunta n. 0/2025 — Rete ciclabile, secondo lotto",
      "url": "https://example.org/delibera-2025.pdf",
      "accessed": "2026-11-13",
      "primary": true,
      "local_copy": null,
      "tags": ["external"]
    },
    {
      "key": "rivista-quartiere-2025",
      "type": "article",
      "title": "Più bici in centro: cosa dicono i numeri",
      "url": "https://example.org/articolo",
      "accessed": "2026-11-12",
      "primary": false,
      "local_copy": null,
      "tags": ["secondary"]
    }
  ]
}
```

| Campo | Obbligatorio | Note |
|---|---|---|
| `post_id` | Sì | Identico al `post_id` dell'unità e a quello di `factcheck.json` |
| `sources[].key` | Sì | Stringa stabile, minuscole e trattini; non si rinomina dopo F3 |
| `type` | Sì | `report`, `article`, `book`, `dataset`, `documentation`, `law`, `measurement`, `media` |
| `title`, `accessed` | Sì | Data ISO |
| `url` / `local_copy` | Almeno uno | `local_copy` relativo alla radice del progetto |
| `primary` | Sì | `false` per fonti secondarie |
| `sha256` | Se c'è `local_copy` | Permette di rilevare copie cambiate |
| `tags` | No | Usate `self_draft` per marcare fonti circolari |

## 5. `factcheck.json` (F3)

Percorso: `[paths].evidence/<post_id>/factcheck.json`.

```json
{
  "schema_version": 1,
  "post_id": "post_07",
  "draft_digest": "v1:<digest completo dell'unità verificata>",
  "verifier": "<agente o persona che ha eseguito la verifica>",
  "rag_provider": "local",
  "claims": [
    {
      "id": "C1",
      "text": "Nel 2024 gli spostamenti in bicicletta in centro sono cresciuti del 18%.",
      "outcome": "grounded_primary",
      "source_key": "osservatorio-ciclabile-2024",
      "locator": "p. 14, tabella 2",
      "promotable": true
    },
    {
      "id": "C2",
      "text": "La nuova pista collega la stazione al polo universitario.",
      "outcome": "verified_external",
      "source_key": "delibera-giunta-2025",
      "locator": "allegato A, tavola 3",
      "verified_at": "2026-11-13T09:30:00+01:00",
      "promotable": true
    },
    {
      "id": "C3",
      "text": "Molti commercianti hanno visto aumentare gli incassi.",
      "outcome": "grounded_secondary",
      "source_key": "rivista-quartiere-2025",
      "locator": "paragrafo 3",
      "promotable": false
    }
  ],
  "pre_publication_errors": [
    {
      "id": "ERR-post_07-01",
      "claim_id": "C1",
      "category": "number",
      "before": "cresciuti di un quarto",
      "after": "cresciuti del 18%",
      "explanation": "La bozza arrotondava il dato della tabella 2."
    }
  ],
  "excluded": [
    {"text": "La pista cambierà il modo di vivere il centro.", "reason": "forecast"}
  ],
  "summary": {"total": 3, "blocking": 0, "promotable": 2}
}
```

| Campo | Obbligatorio | Note |
|---|---|---|
| `post_id` | Sì | Deve coincidere con `sources.json` e con l'unità, altrimenti la CLI rifiuta (`rag.schema`) |
| `draft_digest` | Sì | Digest `v1:` completo dell'unità verificata, letto da `validate-draft --json`. Se diverso dal digest corrente: `BLOCK` `rag.stale_factcheck` |
| `claims` | Sì | Lista non vuota. `id` (o `claim_id`) unico: un duplicato invalida l'intero file |
| `claims[].text` | Sì | Frase o tratto di frase della bozza **alla lettera**, compreso il codice in linea tra backtick. Il confronto ignora i rimandi numerici `[1]`, gli spazi multipli e gli a capo, e tratta come uguali virgolette tipografiche e diritte (`«»`, `“”`, `’`); il codice tra backtick resta esatto. Se il `text` non compare nella bozza: `WARN` `rag.claim_not_in_draft` |
| `claims[].outcome` | Sì | Uno degli esiti di `[factcheck].allowed_outcomes` (§2) |
| `claims[].source_key` | Per esiti `OK` | Deve esistere in `sources.json` |
| `claims[].locator` | Per esiti `OK` | Non vuoto, specifico (§3) |
| `claims[].verified_at` | Per `verified_external` | Data e ora con offset di fuso (documentale) |
| `claims[].promotable` | Consigliato | `true` solo per `grounded_primary` / `verified_external` con locator |
| `excluded` | Se presenti | Frasi escluse per natura, con `text` e `reason` (`opinion`, `forecast`, `author_judgment`). Mostrate al Gate 1 |
| `pre_publication_errors` | Se presenti | Diventano voci della sezione A di `/correzioni/` dopo l'uscita |

`verify-facts` legge anche `draft-review.json` (F2b) nella stessa cartella: `post_id`, `draft_digest` uguale al digest corrente e ogni voce di `[humanizer].required_items` a `pass` (schema in `gates_and_evidence.md` §2.2). Esempio completo e funzionante: `examples/sample_blog/evidence/post_01/`.

## 6. Procedura di F3

F3 parte dalla bozza **dopo** F2b e termina prima del Gate 1.

1. **Estrazione dei claim dalla bozza corrente.** Rileggete il testo ed estraete ogni frase che contiene un fatto verificabile (numeri, date, nomi propri, attribuzioni, relazioni causali, citazioni), copiandola alla lettera con il suo contesto (paragrafo, sezione) prima di invocare il provider RAG e `verify-facts`. Le opinioni dichiarate, le previsioni e i giudizi dell'autore non sono claim: vanno in `excluded` con il motivo, perché il Direttore veda cosa è stato escluso.
2. **Un fatto per claim.** Una frase con due fatti verificabili si riscrive in due frasi: due voci con lo stesso `text` sono `BLOCK`.
3. **Una domanda per claim.** Interrogate il corpus con una domanda precisa per ciascun claim, includendo il contesto estratto; al massimo `[providers.rag].max_claims_per_turn` interrogazioni per messaggio dell'agente, le restanti nel messaggio successivo. Chiedete il passaggio testuale, non un giudizio.
4. **Lettura del passaggio.** Confrontate voi il passaggio con il claim: numero, unità di misura, periodo, popolazione, luogo, edizione della fonte. Un modello RAG può fraintendere la fonte.
5. **Esito e locator.** Assegnate l'esito del §2 e scrivete il locator del §3.
6. **Correzione della bozza.** `unsupported` → togliete o riformulate la frase; `contradicted` → correggetela; registrate l'errore in `pre_publication_errors`. Aggiornate `text` nel claim con la frase nuova. Le frasi riscritte ripassano dalle voci 1–7 e 10 di `humanizer_checklist.md` (aggiornate `draft-review.json`).
7. **Copertura della bozza (obbligatoria, manuale).** Con il digest finale:
   - per ogni frase della bozza con numeri, date, nomi propri o virgolette verificate che esista un claim o una voce in `excluded` (la CLI non lo controlla);
   - scrivete in `draft_digest` di `factcheck.json` e di `draft-review.json` il digest corrente letto da `validate-draft --json`.
8. **Verifica CLI.**
   ```bash
   editorial-pipeline verify-facts content/posts/post_07_titolo.md --json
   ```
   ```json
   {
     "findings": [
       {"code": "rag.claim", "message": "claim_id=C1: recorded evidence and locator present", "state": "OK"},
       {"code": "rag.claim", "message": "claim_id=C2: recorded evidence and locator present", "state": "OK"},
       {"code": "rag.claim", "message": "claim_id=C3: secondary evidence requires review", "state": "WARN"}
     ],
     "post": "content/posts/post_07_titolo.md"
   }
   ```
   Codici possibili: `rag.claim` (esito di ciascun claim), `rag.source` (fonte non primaria, circolare o con copia locale non valida), `rag.schema` (file mancanti, JSON non valido, `post_id` o identificativi duplicati), `rag.stale_factcheck`, `rag.claim_not_in_draft` (`WARN`), `humanizer.review` e `humanizer.stale_review` (revisione F2b mancante, incompleta o su un altro digest). Exit `1` se c'è almeno un `BLOCK`. Prima del Gate 1 non devono restare né `BLOCK` né `rag.claim_not_in_draft`.
9. **Consegna al Gate 1.** Con `validate-draft` e `verify-facts` senza `BLOCK` sullo stesso digest, `draft-review.json` e `factcheck.json` riallineati, si compone il pacchetto Gate 1 (`gates_and_evidence.md` §2). Le correzioni fatte in F3 avvengono **prima** del gate: non c'è alcuna approvazione da rifare, ma le frasi cambiate si mostrano al Direttore con il prima/dopo.

Se dopo il Gate 1 la bozza o `factcheck.json` cambiano, Gate 1 e Gate 2 diventano `stale` (`gates_and_evidence.md` §6): si rifà F3 sulle parti toccate e si chiede un nuovo Gate 1.

## 7. Errori e limiti di verifica

- Un errore intercettato in F3 si registra in `pre_publication_errors` **prima** di chiedere il Gate 1.
- Un dato trovato solo su fonte secondaria è un **limite di verifica**, non un errore fattuale: si registra con categoria `source_provenance` e non si descrive come allucinazione.
- Un errore scoperto dopo la pubblicazione diventa una voce `COR-<unità>-<n>` della sezione B di `/correzioni/` (F6), con data, prima/dopo, fonte e locator.

## 8. Errori comuni

- Parafrasare il claim in `text`: la CLI segnala `rag.claim_not_in_draft`; si copia la frase della bozza, non la si riassume.
- Dimenticare frasi fattuali della bozza: la CLI non le vede, la copertura è a carico dell'agente.
- Aggiornare la bozza senza aggiornare `draft_digest` di `factcheck.json` e `draft-review.json`: `BLOCK` `rag.stale_factcheck` e `humanizer.stale_review`. Ricalcolare il digest senza rifare il controllo è comunque un errore.
- Usare `grounded_primary` con una fonte `"primary": false`: `BLOCK`.
- Presentare il Gate 1 prima di F3.
- Usare come `source_key` una fonte assente da `sources.json`.
- Locator generici («nel rapporto», «cap. 3»).
- Promuovere un dato `grounded_secondary` perché «tanto è nel testo».
- Considerare `verify-facts` senza `BLOCK` come approvazione: è solo coerenza delle evidenze.
