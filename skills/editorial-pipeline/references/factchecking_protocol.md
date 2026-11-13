# Protocollo di fact-checking su fonti primarie

Reference per **F1** (acquisizione fonti) e **F3** (verifica dei claim). Definisce cosa conta come fonte primaria, come si scrive un locator, gli esiti ammessi e la struttura di `sources.json` e `factcheck.json` letti dalla CLI.

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

## 2. Esiti ammessi

| Esito | Significato | Stato CLI | Nel testo | In promozione |
|---|---|---|---|---|
| `grounded_primary` | Riscontrato sulla fonte primaria del corpus, con locator | `OK` | Sì | Sì |
| `verified_external` | Riscontrato su una fonte primaria esterna al corpus, con URL, data di verifica e locator | `OK` | Sì | Sì |
| `grounded_secondary` | Riscontrato solo su fonte secondaria | `WARN` | Sì, dichiarato come tale | **No** |
| `unsupported` | Nessun riscontro | `BLOCK` | No: si toglie o si riformula | No |
| `contradicted` | La fonte dice il contrario | `BLOCK` | No: si corregge | No |

Per la CLI un claim è `OK` solo se: esito tra `grounded_primary`, `verified_external` (o il legacy `verified`), `source_key` presente in `sources.json`, `locator` non vuoto. Qualsiasi altra combinazione, compresi claim duplicati o assenti da `factcheck.json`, è `BLOCK`.

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
  "draft_digest": "<digest dell'unità verificata>",
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
  "summary": {"total": 3, "blocking": 0, "promotable": 2}
}
```

| Campo | Obbligatorio | Note |
|---|---|---|
| `post_id` | Sì | Deve coincidere con `sources.json` e con l'unità, altrimenti la CLI rifiuta |
| `claims` | Sì | Lista non vuota |
| `claims[].text` | Sì | Frase della bozza **alla lettera**: la CLI confronta per uguaglianza esatta |
| `claims[].outcome` | Sì | Uno degli esiti del §2 |
| `claims[].source_key` | Per esiti `OK` | Deve esistere in `sources.json` |
| `claims[].locator` | Per esiti `OK` | Non vuoto, specifico (§3) |
| `claims[].verified_at` | Per `verified_external` | Data e ora con offset di fuso |
| `claims[].promotable` | Consigliato | `true` solo per `grounded_primary` / `verified_external` con locator |
| `draft_digest` | Consigliato | Digest dell'unità al momento della verifica: se cambia, il fact-check è `stale` |
| `pre_publication_errors` | Se presenti | Diventano voci della sezione A di `/correzioni/` dopo l'uscita |

## 6. Procedura di F3

1. **Estrazione dei claim.** Copiate dalla bozza ogni frase che contiene un fatto verificabile: numeri, date, nomi, attribuzioni, relazioni causali, citazioni. Le opinioni dichiarate come tali non sono claim.
2. **Una domanda per claim.** Interrogate il corpus con una domanda precisa per ciascun claim, al massimo `[providers.rag].max_claims_per_turn` per turno. Chiedete il passaggio testuale, non un giudizio.
3. **Lettura del passaggio.** Confrontate voi il passaggio con il claim: numero, unità di misura, periodo, popolazione, luogo. Un modello RAG può fraintendere la fonte.
4. **Esito e locator.** Assegnate l'esito del §2 e scrivete il locator del §3.
5. **Correzione della bozza.** `unsupported` → togliete o riformulate la frase; `contradicted` → correggetela; registrate l'errore in `pre_publication_errors`. Aggiornate `text` nel claim con la frase nuova.
6. **Verifica CLI.**
   ```bash
   editorial-pipeline verify-facts content/posts/post_07_titolo.md --json
   ```
   ```json
   {
     "findings": [
       {"code": "rag.claim", "message": "Claim evidence: OK", "state": "OK"},
       {"code": "rag.claim", "message": "Claim evidence: OK", "state": "OK"},
       {"code": "rag.claim", "message": "Claim evidence: WARN", "state": "WARN"}
     ],
     "post": "content/posts/post_07_titolo.md"
   }
   ```
   I finding sono nell'ordine dei claim. Exit `1` se c'è almeno un `BLOCK`.
7. **Gate 1 stale.** Se la bozza è cambiata, il Gate 1 va richiesto di nuovo mostrando il diff delle frasi modificate (vedi `gates_and_evidence.md` §6).

## 7. Errori e limiti di verifica

- Un errore intercettato in F3 si registra in `pre_publication_errors` **prima** di chiedere il gate successivo.
- Un dato trovato solo su fonte secondaria è un **limite di verifica**, non un errore fattuale: si registra con categoria `source_provenance` e non si descrive come allucinazione.
- Un errore scoperto dopo la pubblicazione diventa una voce `COR-<unità>-<n>` della sezione B di `/correzioni/` (F5), con data, prima/dopo, fonte e locator.

## 8. Errori comuni

- Parafrasare il claim in `text`: la CLI non lo trova e restituisce `BLOCK`.
- Usare come `source_key` una fonte assente da `sources.json`.
- Locator generici («nel rapporto», «cap. 3»).
- Promuovere un dato `grounded_secondary` perché «tanto è nel testo».
- Considerare `verify-facts` senza `BLOCK` come approvazione: è solo coerenza delle evidenze.
