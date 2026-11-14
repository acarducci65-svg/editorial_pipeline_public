# Verifica dei fatti con NotebookLM: strumenti MCP e CLI

Reference per **F1** (inventario delle fonti) e **F3** (fact-checking della bozza) quando la redazione usa Google NotebookLM. Integra `factchecking_protocol.md`, che resta la norma per fonti, esiti, locator e schemi JSON: NotebookLM cambia il modo di **trovare** i passaggi, non le regole con cui si **registrano**.

Posizione nel ciclo: `F0 → F1 → F2a → F2b → F3 → Gate 1 → F4 ‖ F5 → Gate 2 → F6`. NotebookLM interviene in F1 e F3, sempre prima del Gate 1.

---

## 1. Due livelli, due responsabilità

| Livello | Strumento | Chi lo aziona | Che cosa produce |
|---|---|---|---|
| **Agente (MCP)** | Server `notebooklm-mcp` collegato all'harness | Voi, durante F1 e F3 | Passaggi da leggere e localizzare; le evidenze le scrivete voi in `sources.json` e `factcheck.json` |
| **CLI** | `editorial-pipeline verify-facts` con `[rag] provider = "notebooklm"`, che invoca `nlm query notebook` | La CLI, a fine F3 | Un finding `rag.claim` remoto per claim (`OK`/`WARN`/`BLOCK`), in aggiunta ai finding locali |

Sono indipendenti: potete usare gli strumenti MCP con `provider = "local"`, oppure la verifica CLI senza strumenti MCP nell'harness.

**Come capire se gli strumenti MCP ci sono.** Cercate nell'elenco degli strumenti dell'harness nomi come `notebook_list`, `notebook_query`, `source_add` (in Claude Code compaiono con prefisso `mcp__notebooklm-mcp__`). Se mancano, non simulate le risposte: lavorate sulle copie locali in `[paths].sources` e lo dite al Direttore.

## 2. Livello agente: F1 — inventario delle fonti

1. **Individuate il taccuino.** `notebook_list`, poi `notebook_get` o `notebook_describe` sul taccuino indicato dal Direttore. Se il Direttore non ve l'ha indicato, chiedetelo: non scegliete voi fra taccuini diversi.
2. **Caricate solo fonti già scelte.** `source_add` (`source_type` = `url`, `text`, `file` o `drive`) per le fonti primarie individuate secondo `factchecking_protocol.md` §1. Il taccuino non è un motore di scoperta: una fonte proposta da NotebookLM (per esempio da `research_start`) entra solo dopo che l'avete aperta e classificata come primaria o secondaria.
3. **Controllate ogni fonte.** `source_describe` e `source_get_content` per verificare titolo, edizione, data e completezza dell'indicizzazione prima di scriverla in `sources.json`.
4. **Registrate in `sources.json`** con `key`, `type`, `title`, `url` o `local_copy`, `accessed`, `primary` (schema in `factchecking_protocol.md` §4). Gli identificativi delle fonti in NotebookLM **non** vanno in `sources.json`.
5. **Sottoponete l'elenco al Direttore**, che decide quali fonti entrano.

## 3. Livello agente: F3 — fact-checking della bozza

Per ogni claim estratto dalla bozza (procedura in `factchecking_protocol.md` §6, passi 1–2):

1. **Una domanda per claim** con `notebook_query`, al massimo `[providers.rag].max_claims_per_turn` per messaggio. Chiedete il passaggio, non un giudizio:

   > Riporta alla lettera il passaggio delle fonti che riguarda questa affermazione e indica fonte, pagina o sezione: «<testo del claim>». Se le fonti non lo trattano o lo contraddicono, dillo.

2. **Leggete il passaggio nella fonte**, non solo nella risposta. Usate le citazioni restituite per aprire il punto esatto (`source_get_content` o la copia locale) e confrontate numero, unità, periodo, popolazione, luogo, edizione.
3. **Assegnate l'esito** secondo `factchecking_protocol.md` §2. Una risposta senza citazione, o con una citazione che non sostiene il claim, è `unsupported`. Se la fonte citata è secondaria, l'esito massimo è `grounded_secondary`.
4. **Scrivete il locator** dalla fonte (`p. 14, tabella 2`, `§4.2`), mai «secondo NotebookLM» o il numero di citazione della risposta.
5. **Registrate in `factcheck.json`** come previsto dal §5 del protocollo. Potete indicare `"rag_provider": "notebooklm"`; non inserite identificativi di taccuino, conversazione o fonte.

Strumenti che modificano o espongono dati (`source_delete`, `notebook_delete`, `notebook_share_public`, `notebook_share_invite`, `notebook_share_batch`) richiedono la conferma esplicita del Direttore in chat, anche quando lo strumento prevede un parametro `confirm`.

## 4. Livello CLI: `verify-facts` con NotebookLM

Configurazione (la prepara la persona che gestisce il progetto; voi la controllate, non la inventate):

```toml
[rag]
provider = "notebooklm"
corpus_id_env = "EDITORIAL_RAG_ID"   # nome della variabile, non l'identificativo
timeout_seconds = 60
```

Prerequisiti sull'host: `nlm` nel `PATH` (`uv tool install notebooklm-mcp-cli`), sessione aperta con `nlm login`, variabile `EDITORIAL_RAG_ID` con l'identificativo o un alias `nlm` del taccuino.

```bash
editorial-pipeline verify-facts content/posts/post_07_titolo.md --json
```

Comportamento:

- la verifica locale gira sempre per prima: senza `factcheck.json` coerente il report resta `BLOCK`;
- poi un'interrogazione `nlm` per claim, con un finding `rag.claim` identificato dalla posizione (`Claim 3: not supported by notebook sources`);
- `BLOCK` se mancano citazioni o la risposta smentisce il claim, `WARN` se è incerta, `OK` altrimenti;
- `Error: RagUnavailableError` ed exit `1`, senza report, se il corpus non è configurato, `nlm` manca, la sessione è scaduta, scade il timeout o la risposta non è JSON valido.

Come leggere i finding remoti:

| Finding remoto | Che cosa fate |
|---|---|
| `Claim N: not supported by notebook sources` (`BLOCK`) | Riaprite la fonte del claim N. Se il passaggio non c'è, correggete o togliete la frase (`unsupported`). Se c'è ma la fonte non è nel taccuino, aggiungetela (F1) o dichiaratelo nel pacchetto Gate 1 |
| `Claim N: requires review of notebook evidence` (`WARN`) | Rileggete il passaggio; motivate il `WARN` nel pacchetto Gate 1 o riformulate la frase |
| `Claim N: supported by notebook sources` (`OK`) | Nessuna azione oltre al controllo che avete già fatto: la classificazione è lessicale, non sostituisce la vostra lettura |
| `Error: RagUnavailableError` | Non è un esito sui claim. Riferite al Direttore (sessione `nlm` scaduta, variabile vuota, timeout). **Non** ripiegate da soli su `provider = "local"` per far passare il controllo: cambiare la configurazione è una decisione del Direttore |

Il testo dei claim viene inviato a Google. Se la bozza è riservata, chiedete al Direttore prima di usare `provider = "notebooklm"`.

## 5. Zero-leak

- Identificativi di taccuino, fonte e conversazione restano nella sessione o nella variabile d'ambiente. Mai in `editorial.toml`, evidenze, ricevute, pacchetti di gate, commit o messaggi pubblici.
- Non incollate nei file di evidenza le risposte integrali di NotebookLM: registrate il locator e, se utile, una citazione breve del passaggio della **fonte**.
- Non eseguite `nlm login` né gestite credenziali Google per conto del Direttore in una sessione non presidiata: l'accesso lo fa la persona titolare dell'account.

## 6. Gate umani

NotebookLM, da MCP o da CLI, produce indizi e finding automatici. Non cambia nulla dei gate:

- Gate 1 e Gate 2 restano vincolanti e umani: si chiudono solo con la frase di approvazione scritta dal Direttore in chat (`gates_and_evidence.md`).
- Un report `verify-facts` senza `BLOCK`, anche con tutti i claim `OK` su NotebookLM, significa «evidenze coerenti», mai «testo approvato».
- Non scrivete ricevute in `approvals/` sulla base di un esito di NotebookLM, e non presentate un `OK` remoto come conferma del Direttore: sarebbe una Ghost Approval.
- `check-gate` riesegue solo i controlli locali e valida ricevute umane; non interroga NotebookLM.

## 7. Errori comuni

- Copiare in `locator` il numero di citazione della risposta di NotebookLM invece del punto nella fonte.
- Usare come `grounded_primary` un claim confermato solo dalla sintesi del modello, senza aver letto il passaggio.
- Aggiungere al taccuino fonti non sottoposte al Direttore e citarle in bozza.
- Scrivere l'identificativo del taccuino in `editorial.toml` (`corpus_id`) per «comodità».
- Trattare `Error: RagUnavailableError` come un `BLOCK` sui claim e riscrivere la bozza: è un problema di configurazione o di sessione.
- Interrogare il taccuino con domande che contengono più fatti: una domanda, un claim.
