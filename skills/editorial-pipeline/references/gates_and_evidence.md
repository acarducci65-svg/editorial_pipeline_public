# Gate umani ed evidenze

Reference per i due gate del ciclo editoriale: cosa mostrare al Direttore, come si calcola il digest, come si registra e si verifica la ricevuta, quando un'approvazione diventa `stale`.

Principio guida: **la ricevuta rende verificabile *cosa* è stato approvato e su quale versione. Non autentica *chi* ha scritto in chat, e non sostituisce mai il messaggio umano.**

---

## 1. Digest dell'unità

La CLI identifica una versione dell'unità con un SHA-256 calcolato su:

```
sha256( <percorso relativo POSIX dalla radice del progetto> + "\0" + <byte del file> )
```

- Il percorso relativo fa parte del digest: rinominare o spostare il file cambia il digest.
- Qualsiasi modifica al file (testo, frontmatter, spazi, fine riga) cambia il digest.
- Il digest corrente si legge dal campo `digest` del report:

```bash
editorial-pipeline validate-draft content/posts/post_07_titolo.md --json
```

```json
{
  "posts": [
    {
      "rel_path": "content/posts/post_07_titolo.md",
      "digest": "3f9a1c2e7b...e41d",
      "state": "BLOCK",
      "evidence": "evidence/post_07",
      "findings": [
        {"code": "evidence.missing", "message": "Missing evidence: factcheck.json", "state": "BLOCK"}
      ]
    }
  ]
}
```

Nei pacchetti si mostra il **digest abbreviato** (primi 8–12 caratteri); nella ricevuta e nel comando `check-gate` si usa il **digest completo**.

## 2. Pacchetto Gate 1 — Bozza

Prerequisiti: F2 completata, revisione di stile registrata, linter senza `BLOCK` di stile.

Il pacchetto, presentato in chat in un unico messaggio, contiene:

| # | Voce | Fonte del dato |
|---|---|---|
| 1 | Titolo, sommario e prime righe della bozza | file dell'unità |
| 2 | Numero di parole e tempo di lettura stimato | calcolo sull'unità |
| 3 | Registro di stile attivo | `editorial.toml [register].active` |
| 4 | Esito di `validate-draft`: elenco dei `BLOCK` (atteso al più `evidence.missing` per `factcheck.json`) e dei `WARN` con motivazione | report CLI |
| 5 | Checklist anti-cliché: esito di ciascuna delle 9 voci | `draft-review.json` + prova |
| 6 | Claim preliminari: testo, fonte prevista (`key`), tipo di fonte | elenco claim di F2 + `sources.json` |
| 7 | Errori intercettati durante stesura e revisione, con prima/dopo | note di revisione |
| 8 | Digest abbreviato | report CLI |
| 9 | Domanda di approvazione con la frase esatta da scrivere | `[gates.gate1].question` |

Esempio di chiusura del pacchetto:

> **Digest:** `3f9a1c2e7b`
> Approvi questa bozza (digest `3f9a1c2e7b`) per passare al fact-check e alla promozione? Rispondi «Approvo Gate 1 #post_07» oppure indica le correzioni.

Dopo la domanda l'agente **termina il turno**.

## 3. Pacchetto Gate 2 — Pubblicazione

Prerequisiti: Gate 1 valido sul digest corrente, `verify-facts` senza `BLOCK`, kit promozionale rivisto.

| # | Voce | Fonte del dato |
|---|---|---|
| 1 | Conferma che il digest corrente coincide con quello approvato al Gate 1 (o nuovo Gate 1 ottenuto) | report CLI + `approvals/gate1.json` |
| 2 | Esito di `verify-facts`: totale claim, `OK`, `WARN` (`grounded_secondary` dichiarati) | report CLI |
| 3 | Anteprime del carosello (prima e ultima slide almeno) e percorso del manifest | `build-visual` |
| 4 | Testi integrali di ogni copy promozionale, per canale | kit F4 |
| 5 | Tabella dati promozionali: dato, `claim_id`, esito, fonte, locator | `factcheck.json` |
| 6 | Esito della revisione anti-cliché del kit | `social-review.json` + prova |
| 7 | Data e ora di uscita nel fuso del progetto, con equivalente UTC | `[project].timezone` |
| 8 | Elenco dei file che verranno pubblicati o sincronizzati | dry-run del deploy |
| 9 | Azioni richieste, scelte tra `[gates.gate2].allowed_actions` (`publish`, `schedule`, `sync`) | proposta dell'agente |
| 10 | Domanda di approvazione con la frase esatta | `[gates.gate2].question` |

Esempio di chiusura:

> Approvi la pubblicazione di #post_07 il 20 novembre 2026 alle 08:00 (Europe/Rome; 07:00 UTC) con le azioni `publish` e `sync`? Rispondi «Approvo Gate 2 #post_07».

Nessuna azione è implicita: se il Direttore approva solo `schedule`, l'agente non esegue `sync`.

## 4. Ricevute

Dopo il messaggio di approvazione, e mai prima, l'agente che lo ha ricevuto scrive la ricevuta in `evidence/<post_id>/<[gates].receipts_dir>/gate<N>.json` (default `approvals/`).

`approvals/gate1.json`:

```json
{
  "schema_version": 1,
  "gate": 1,
  "post_id": "post_07",
  "decision": "approved",
  "digest": "3f9a1c2e7b...e41d",
  "approved_by": "Direttore",
  "approved_at": "2026-11-18T10:42:00+01:00",
  "chat_message_ref": "<identificativo della sessione e posizione del messaggio>",
  "chat_excerpt": "Approvo Gate 1 #post_07",
  "recorded_by": "<nome dell'agente che ha ricevuto il messaggio>"
}
```

`approvals/gate2.json`: come sopra con `"gate": 2` e in più:

```json
{
  "publish_at_local": "2026-11-20T08:00:00+01:00",
  "publish_at_utc": "2026-11-20T07:00:00Z",
  "allowed_actions": ["publish", "sync"],
  "files": ["content/posts/post_07_titolo.md", "dist/social/post_07/manifest.json"]
}
```

Regole:

- `approved_by` è l'etichetta del **ruolo** (`[gates].approver_role`), non un nome proprio.
- `chat_excerpt` riporta parola per parola il messaggio del Direttore.
- `approved_at` ha sempre un offset di fuso esplicito.
- Estratti che contengono una voce di `[gates].forbidden_excerpts` («auto-approved», «stop hook», «synthetic», «approvato automaticamente»…) invalidano la ricevuta.
- Una ricevuta non si scrive sulla base di un'approvazione riferita da un altro agente, né si ricostruisce a posteriori.

## 5. Generazione e verifica del token

Il token della CLI è il **digest completo** dell'unità approvata. `check-gate` ricalcola il digest del file corrente e lo confronta, in tempo costante, con il token ricevuto:

```bash
editorial-pipeline check-gate 1 content/posts/post_07_titolo.md --token 3f9a1c2e7b...e41d
```

| Esito | Exit | Significato | Cosa fare |
|---|---|---|---|
| JSON con `"status": "APPROVED"` | 0 | Il token coincide con il digest corrente: la ricevuta è legata al testo mostrato | Proseguire con la fase successiva |
| `explicit human approval, timestamp and token required` | 2 | Token assente o vuoto | Non si attraversa il gate |
| `human approval does not match evidence` | 2 | Il file è cambiato dopo il pacchetto | Rimostrare il pacchetto aggiornato e chiedere una nuova approvazione |
| `Error: ValueError` | 1 | Unità non trovata nella cartella dei contenuti | Correggere il percorso |

Procedura obbligata:

1. Pacchetto mostrato con il digest abbreviato.
2. Messaggio esplicito del Direttore con la frase di approvazione.
3. Ricevuta scritta con il digest completo mostrato.
4. `check-gate` con `--token` uguale al digest della ricevuta.
5. Output della CLI salvato accanto alla ricevuta (es. `approvals/gate1.check.json`).

Attenzione: il digest è calcolabile da chiunque abbia accesso al file, agente compreso. `check-gate` dimostra la **corrispondenza** tra ricevuta e testo, non l'esistenza dell'approvazione. Eseguirlo prima del messaggio del Direttore è una Ghost Approval, anche se la CLI risponde `APPROVED`.

`check-gate` non controlla i prerequisiti di fase (fact-check, kit): vanno verificati con `validate-draft` e `verify-facts` prima di comporre il pacchetto.

## 6. Invalidazione

| Evento | Diventa `stale` o invalido |
|---|---|
| Modifica del testo o del frontmatter dell'unità | `draft-review.json`, `factcheck.json`, Gate 1, kit promozionale, Gate 2 |
| Spostamento o rinomina del file | Digest, quindi Gate 1 e Gate 2 |
| Modifica di `sources.json` | `factcheck.json`, Gate 1, Gate 2 |
| Modifica di `factcheck.json` | Gate 2; il Gate 1 se cambia un claim mostrato nel pacchetto |
| Modifica del kit promozionale o rigenerazione del carosello | `social-review.json`, Gate 2 |
| Cambio di registro o di `extra_forbidden` | `draft-review.json`, `social-review.json` |
| Spostamento della data o delle azioni | Gate 2 |

Dopo una correzione si riparte dalla **prima** evidenza invalidata, mai dall'ultima. Ricalcolare soltanto il digest senza rifare il controllo è un errore.

## 7. Errori comuni

- Scrivere «Gate 1 approvato» nel messaggio dell'agente prima della risposta del Direttore.
- Considerare un «ok» generico come approvazione: si chiede di nuovo con la frase esatta.
- Riutilizzare l'approvazione di una sessione precedente su una bozza poi modificata.
- Eseguire un'azione di Gate 2 non elencata nella ricevuta («già che c'ero ho anche sincronizzato»).
- Trattare un report senza `BLOCK` come approvazione.
