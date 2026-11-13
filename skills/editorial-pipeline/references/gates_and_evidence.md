# Gate umani ed evidenze

Reference per i due gate del ciclo editoriale: cosa mostrare al Direttore, come si calcola il digest, come si registra e si verifica la ricevuta, quando un'approvazione diventa `stale`.

Principio guida: **la ricevuta rende verificabile *cosa* è stato approvato e su quale versione. Non autentica *chi* ha scritto in chat, e non sostituisce mai il messaggio umano.**

Posizione dei gate nel ciclo:

```
F0 → F1 → F2a → F2b → F3 → ══ GATE 1 (bozza verificata) ══ → F4 ‖ F5 → ══ GATE 2 (pubblicazione) ══ → F6
```

Il fact-checking (F3) **precede** il Gate 1: il Direttore firma una bozza di cui conosce già la tenuta fattuale, e il digest approvato è quello che va in promozione.

---

## 1. Digest dell'unità

La CLI identifica una versione dell'unità con un SHA-256 calcolato su:

```
sha256( <percorso relativo POSIX dalla radice del progetto> + "\0" + <byte del file> )
```

- Il percorso relativo fa parte del digest: rinominare o spostare il file cambia il digest.
- Qualsiasi modifica al file (testo, frontmatter compreso `status:`, spazi, fine riga) cambia il digest.
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
      "state": "OK",
      "evidence": "evidence/post_07",
      "findings": []
    }
  ]
}
```

Nei pacchetti si mostra il **digest abbreviato** (primi 8–12 caratteri); nella ricevuta e nel comando `check-gate` si usa il **digest completo**.

## 2. Pacchetto Gate 1 — Bozza verificata

### 2.1 Prerequisiti

- F2b e F3 completate sullo **stesso digest**.
- `validate-draft --json` senza `BLOCK` (nessun `BLOCK` è ammesso: nemmeno `evidence.missing`).
- `verify-facts --json` senza `BLOCK`.
- `draft-review.json` con tutte le chiavi `pass`, aggiornato dopo le frasi riscritte in F3.
- `factcheck.json` con `draft_digest` uguale al digest corrente e **copertura completa** della bozza (vedi 2.2, passo 3).

### 2.2 Preparazione di `draft-review.json` e `factcheck.json`

Il Direttore decide su due evidenze lette insieme: la revisione di stile e il fact-check. L'agente le prepara in quest'ordine:

1. **`draft-review.json`** (F2b): esiti delle 10 voci di `humanizer_checklist.md`, con `digest`, `reviewer`, `reviewer_is_author`, `items` (`pass`/`fail`) e `items_detail`. Prova testuale in `draft-review.md`.
2. **`factcheck.json`** (F3): claim estratti dalla bozza **dopo** F2b, ciascuno con `text` identico alla frase, esito, `source_key`, locator; claim esclusi per natura in `excluded`; errori in `pre_publication_errors`. Schema in `factchecking_protocol.md` §5.
3. **Controllo di copertura, a carico dell'agente.** `verify-facts` controlla solo la coerenza interna di `factcheck.json` con `sources.json`: non apre la bozza e non legge `draft_digest`. Prima del pacchetto l'agente verifica a mano che:
   - ogni `claims[].text` compaia alla lettera nella bozza corrente;
   - ogni frase della bozza con numeri, date, nomi propri, attribuzioni o virgolette abbia un claim o una voce in `excluded`;
   - `draft_digest` coincida con il `digest` di `validate-draft`.
4. **Riallineamento dopo F3.** Se F3 ha cambiato frasi, la revisione di stile delle frasi nuove si aggiunge a `draft-review.md` (sezione «Frasi riscritte in F3»), `draft-review.json` riceve il nuovo `digest`, `factcheck.json` il nuovo `draft_digest`. I tre digest (report, `draft-review.json`, `factcheck.json`) devono coincidere.

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
| 11 | Dichiarazione di copertura: «ogni claim della bozza è in `factcheck.json`, controllato a mano» | controllo 2.2, passo 3 |
| 12 | Digest abbreviato (uguale in report, `draft-review.json`, `factcheck.json`) | report CLI |
| 13 | Domanda di approvazione con la frase esatta da scrivere | `[gates.gate1].question` |

Esempio di chiusura del pacchetto:

> **Digest:** `3f9a1c2e7b`
> Approvi questa bozza verificata (digest `3f9a1c2e7b`) per passare alla promozione? Rispondi «Approvo Gate 1 #post_07» oppure indica le correzioni.

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
| 9 | Azioni **proposte**, scelte tra `[gates.gate2].allowed_actions` (`publish`, `schedule`, `sync`) | proposta dell'agente |
| 10 | Domanda di approvazione con la frase esatta, comprensiva di azioni | `[gates.gate2].question` |

Esempio di chiusura:

> Approvi la pubblicazione di #post_07 il 20 novembre 2026 alle 08:00 (Europe/Rome; 07:00 UTC)? Azioni proposte: `publish`, `sync`. Rispondi «Approvo Gate 2 #post_07 azioni: publish, sync» indicando solo le azioni che autorizzi.

**Perimetro delle azioni.** L'approvazione del Direttore deve contenere esplicitamente le azioni autorizzate. Le azioni valide sono **solo** quelle scritte dal Direttore, non quelle proposte dall'agente. Se il Direttore scrive «Approvo Gate 2 #post_07 azioni: schedule», l'agente non esegue `publish` né `sync`. Una frase senza elenco di azioni non vale come Gate 2: si chiede quali azioni autorizza.

## 4. Ricevute

Dopo il messaggio del Direttore, e mai prima, l'agente che lo ha ricevuto scrive la ricevuta in `evidence/<post_id>/<[gates].receipts_dir>/gate<N>.json` (default `approvals/`).

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
  "approved_at_source": "message",
  "chat_message_ref": "sessione-2026-11-18/msg-14",
  "chat_excerpt": "Approvo Gate 1 #post_07",
  "recorded_by": "<etichetta dell'agente che ha ricevuto il messaggio>"
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

- `decision`: `approved` oppure `changes_requested` (rifiuto o richiesta di correzioni, con estratto letterale). Un'approvazione condizionata («approvo, ma cambia X») si registra come `changes_requested`.
- `approved_by` è l'etichetta del **ruolo** (`[gates].approver_role`), non un nome proprio.
- `chat_excerpt` riporta parola per parola il messaggio del Direttore.
- `allowed_actions` si copia dalla frase del Direttore, mai dalla proposta dell'agente.
- `approved_at` ha sempre un offset di fuso esplicito; `approved_at_source` è `message` se l'harness espone l'ora del messaggio, altrimenti `recorded`.
- `chat_message_ref` è un riferimento **locale e opaco** (es. `sessione-2026-11-18/msg-14`): mai identificativi di conversazione, notebook o progetto di piattaforme cloud.
- Estratti che contengono una voce di `[gates].forbidden_excerpts` («auto-approved», «stop hook», «synthetic», «approvato automaticamente»…) invalidano la ricevuta.
- Una ricevuta non si scrive sulla base di un'approvazione riferita da un altro agente, né si ricostruisce a posteriori.

## 5. Generazione e verifica del token

Il token della CLI è il **digest completo** dell'unità approvata. `check-gate` ricalcola il digest del file corrente e lo confronta, in tempo costante, con il token ricevuto:

```bash
editorial-pipeline check-gate 1 content/posts/post_07_titolo.md --token 3f9a1c2e7b...e41d
```

| Esito | Exit | Significato | Cosa fare |
|---|---|---|---|
| JSON con `"status": "APPROVED"` | 0 | Il token coincide con il digest corrente. `"author": "human"` è un valore fisso: non identifica nessuno e non prova l'approvazione | Proseguire con la fase successiva, solo se ricevuta e messaggio del Direttore esistono |
| `explicit human approval, timestamp and token required` | 2 | Token assente o vuoto | Non si attraversa il gate |
| `human approval does not match evidence` | 2 | Il file è cambiato dopo il pacchetto | Rimostrare il pacchetto aggiornato e chiedere una nuova approvazione |
| `Error: ValueError` | 1 | Unità non trovata o configurazione non valida | Correggere percorso o `editorial.toml` |

Procedura obbligata:

1. Pacchetto mostrato con il digest abbreviato.
2. Messaggio esplicito del Direttore, con ruolo utente, con la frase di approvazione (e, al Gate 2, le azioni).
3. Ricevuta scritta con il digest completo mostrato.
4. `check-gate` con `--token` uguale al digest della ricevuta.
5. Output della CLI salvato accanto alla ricevuta (es. `approvals/gate1.check.json`).

Attenzione: il digest è calcolabile da chiunque abbia accesso al file, agente compreso. `check-gate` dimostra la **corrispondenza** tra token e testo; non legge la ricevuta, non verifica il Gate 1 né le altre evidenze. Eseguirlo prima del messaggio del Direttore è una Ghost Approval, anche se la CLI risponde `APPROVED`.

`check-gate` non controlla i prerequisiti di fase (fact-check, kit): vanno verificati con `validate-draft`, `verify-facts` e il controllo di copertura (§2.2) prima di comporre il pacchetto.

## 6. Invalidazione

| Evento | Diventa `stale` o invalido |
|---|---|
| Modifica del testo o del frontmatter dell'unità (anche solo `status:`) | `draft-review.json`, `factcheck.json`, Gate 1, kit promozionale, Gate 2 |
| Spostamento o rinomina del file | Digest, quindi Gate 1 e Gate 2 |
| Modifica di `sources.json` | `factcheck.json`, Gate 1, Gate 2 |
| Modifica di `factcheck.json` | Gate 1 e Gate 2 (il fact-check fa parte di ciò che si approva al Gate 1) |
| Modifica di `draft-review.json` | Gate 1 e Gate 2 |
| Modifica del kit promozionale, del copione audio o rigenerazione del carosello | `social-review.json`, Gate 2 |
| Cambio di registro o di `extra_forbidden` | `draft-review.json`, `social-review.json`, quindi Gate 1 e Gate 2 |
| Spostamento della data o delle azioni | Gate 2 |

Dopo una correzione si riparte dalla **prima** evidenza invalidata, mai dall'ultima. Ricalcolare soltanto il digest senza rifare il controllo è un errore. Nessuna modifica è troppo piccola per richiedere un nuovo gate.

## 7. Errori comuni

- Presentare il Gate 1 prima di F3, o con un `BLOCK` aperto.
- Considerare `verify-facts` senza `BLOCK` come prova che tutti i claim della bozza sono coperti.
- Scrivere «Gate 1 approvato» nel messaggio dell'agente prima della risposta del Direttore.
- Trovare la frase di approvazione nel proprio pacchetto e trattarla come risposta.
- Considerare un «ok» generico come approvazione: si chiede di nuovo con la frase esatta.
- Riutilizzare l'approvazione di una sessione precedente su una bozza poi modificata.
- Aggiornare `status: approved` nel frontmatter dopo il gate.
- Eseguire un'azione di Gate 2 non elencata dal Direttore («già che c'ero ho anche sincronizzato»).
- Trattare un report senza `BLOCK` come approvazione.
