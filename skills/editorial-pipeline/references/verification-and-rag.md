# Verifica dei fatti con NotebookLM: strumenti MCP e CLI

Reference per **F1** (inventario delle fonti e creazione del Micro-Taccuino d'Articolo) e **F3** (fact-checking della bozza) quando la redazione usa Google NotebookLM, con il modello a due livelli Taccuino Maestro / Micro-Taccuino (§0). Integra `factchecking_protocol.md`, che resta la norma per fonti, esiti, locator e schemi JSON: NotebookLM cambia il modo di **trovare** i passaggi, non le regole con cui si **registrano**.

Posizione nel ciclo: `F0 → F1 → F2a → F2b → F3 → Gate 1 → F4 ‖ F5 → Gate 2 → F6`. NotebookLM interviene in F0/F1 (ricerca e inventario), in F3 (fact-checking, prima del Gate 1), in F5 (audio) e in F6 (aggiornamento dell'archivio).

---

## 0. Architettura dei taccuini: Taccuino Maestro e Micro-Taccuino d'Articolo

La redazione lavora con **due livelli di taccuino**, con compiti distinti:

| Taccuino | Contenuto | Fasi | Variabile |
|---|---|---|---|
| **Taccuino Maestro** (archivio di redazione; opzionale ma raccomandato) | Tutte le fonti primarie storiche della testata e gli articoli già pubblicati | **F0 / F1**: ricerca trasversale, continuità editoriale, controllo delle ripetizioni. **F6**: si arricchisce a pubblicazione avvenuta | Nessuna variabile della CLI: lo indica il Direttore (alias `nlm`) |
| **Micro-Taccuino d'Articolo** (`<slug>-<post_id>`) | **Solo** le 4–7 fonti primarie approvate in `evidence/<post_id>/sources.json` | **F3** (`verify-facts`, `notebook_query`) e **F5** (`build-audio`) | `EDITORIAL_RAG_ID` ed `EDITORIAL_AUDIO_ID` = `<slug>-<post_id>` |

Perché due livelli:

- **F3 senza fonti circolari.** Nel Maestro ci sono anche gli articoli già pubblicati e più edizioni dello stesso rapporto: una query di verifica rischia di «confermare» un claim citando un nostro vecchio post, o l'edizione sbagliata di un dataset. Nel Micro-Taccuino ci sono solo le fonti approvate per questa unità, quindi ogni citazione rimanda a una voce di `sources.json`.
- **F5 focalizzato.** I conduttori di NotebookLM Studio parlano di ciò che trovano nel taccuino: con il Micro-Taccuino il podcast resta al 100% sull'articolo, senza divagazioni su post precedenti.
- **Continuità nel Maestro.** Ricerca dell'angolo, collegamenti con articoli passati e controllo delle ripetizioni richiedono la vista d'insieme, che solo il Maestro offre.

`<slug>` è lo slug breve dell'articolo concordato in F0 (minuscole, trattini, senza spazi né accenti); `<post_id>` è l'identificativo dell'unità. Esempio: `lavoro-remoto-post_07`.

**Compatibilità con un solo taccuino.** Se il Direttore usa un unico taccuino per tutto (nessun Maestro, oppure nessun Micro-Taccuino), le procedure di §2–§4 restano valide su quel taccuino: `EDITORIAL_RAG_ID` ed `EDITORIAL_AUDIO_ID` puntano al suo alias. In questo caso dichiarate nel pacchetto Gate 1 che le verifiche F3 sono state fatte su un taccuino condiviso e controllate con più attenzione che le citazioni rimandino a fonti di `sources.json`, non ad articoli già pubblicati. Il Micro-Taccuino non si crea se il Direttore non lo vuole.

## 1. Agente (MCP) e CLI: due responsabilità

| Livello | Strumento | Chi lo aziona | Che cosa produce |
|---|---|---|---|
| **Agente (MCP)** | Server `notebooklm-mcp` collegato all'harness | Voi, durante F1 e F3 | Passaggi da leggere e localizzare; le evidenze le scrivete voi in `sources.json` e `factcheck.json` |
| **CLI** | `editorial-pipeline verify-facts` con `[rag] provider = "notebooklm"`, che invoca `nlm query notebook` | La CLI, a fine F3 | Un finding `rag.claim` remoto per claim (`OK`/`WARN`/`BLOCK`), in aggiunta ai finding locali |

Sono indipendenti: potete usare gli strumenti MCP con `provider = "local"`, oppure la verifica CLI senza strumenti MCP nell'harness.

**Come capire se gli strumenti MCP ci sono.** Cercate nell'elenco degli strumenti dell'harness nomi come `notebook_list`, `notebook_query`, `source_add` (in Claude Code compaiono con prefisso `mcp__notebooklm-mcp__`). Se mancano, non simulate le risposte: lavorate sulle copie locali in `[paths].sources` e lo dite al Direttore.

## 2. Livello agente: F0/F1 — ricerca nel Maestro e inventario delle fonti

1. **Individuate il Taccuino Maestro.** `notebook_list`, poi `notebook_get` o `notebook_describe` sul taccuino indicato dal Direttore. Se il Direttore non ve l'ha indicato, chiedetelo: non scegliete voi fra taccuini diversi.
2. **Interrogate il Maestro per la ricerca trasversale (F0/F1).** Con `notebook_query` cercate articoli già pubblicati sullo stesso tema (per evitare ripetizioni e collegare i pezzi), fonti primarie già acquisite dalla redazione e l'edizione più recente dei rapporti ricorrenti. Le risposte del Maestro orientano la scelta delle fonti; non sono evidenze per F3.
3. **Caricate solo fonti già scelte.** `source_add` (`source_type` = `url`, `text`, `file` o `drive`) per le fonti primarie individuate secondo `factchecking_protocol.md` §1. Il taccuino non è un motore di scoperta: una fonte proposta da NotebookLM (per esempio da `research_start`) entra solo dopo che l'avete aperta e classificata come primaria o secondaria.
4. **Controllate ogni fonte.** `source_describe` e `source_get_content` per verificare titolo, edizione, data e completezza dell'indicizzazione prima di scriverla in `sources.json`.
5. **Registrate in `sources.json`** con `key`, `type`, `title`, `url` o `local_copy`, `accessed`, `primary` (schema in `factchecking_protocol.md` §4). Gli identificativi delle fonti in NotebookLM **non** vanno in `sources.json`.
6. **Sottoponete l'elenco al Direttore**, che decide quali fonti entrano. Nello stesso messaggio proponete lo slug del Micro-Taccuino (`<slug>-<post_id>`).
7. **Dopo la conferma delle fonti, create il Micro-Taccuino** (§2.1).

### 2.1 Creazione automatica del Micro-Taccuino d'Articolo (fine F1)

Si esegue **solo dopo** che il Direttore ha approvato in chat l'elenco di `sources.json`, e solo se usa il modello a due livelli (§0). Non serve un'ulteriore conferma per creare il taccuino: la conferma delle fonti la include. Le operazioni distruttive o di condivisione restano soggette a conferma esplicita (§3, ultimo paragrafo).

1. **Create il taccuino** con titolo `"<slug>-<post_id>"`:
   - MCP: `notebook_create` con `title = "<slug>-<post_id>"`;
   - CLI: `nlm notebook create "<slug>-<post_id>" --json`.
   Se un taccuino con quel titolo esiste già (`notebook_list`), non createne un secondo: riferite al Direttore e chiedete se riusarlo.
2. **Registrate l'alias locale**, così nessun UUID finisce nei file versionati:
   ```bash
   nlm alias set <slug>-<post_id> <notebook_id>     # MCP: alias con action="set"
   ```
   L'identificativo restituito da `notebook_create` serve solo in questo comando; da qui in avanti si usa l'alias.
3. **Caricate le sole fonti di `sources.json`** (di norma 4–7 fonti primarie), una per voce, con attesa dell'indicizzazione:
   - MCP: `source_add` con `notebook_id = "<slug>-<post_id>"`, `source_type` coerente (`url`, `file` per `local_copy`, `drive`, `text`) e `wait = true`;
   - CLI: `nlm source add <slug>-<post_id> --url <url> --wait`.
   Nessuna fonte del Maestro, nessun articolo già pubblicato, nessuna fonte esclusa dal Direttore. Al termine controllate con `notebook_get` che il numero di fonti coincida con `sources.json` e che ognuna sia indicizzata (`source_describe`).
4. **Impostate le variabili d'ambiente della sessione** sull'alias:
   ```bash
   export EDITORIAL_RAG_ID=<slug>-<post_id>
   export EDITORIAL_AUDIO_ID=<slug>-<post_id>
   ```
   ```powershell
   $env:EDITORIAL_RAG_ID = "<slug>-<post_id>"
   $env:EDITORIAL_AUDIO_ID = "<slug>-<post_id>"
   ```
   Valgono solo per la sessione: non si scrivono in `editorial.toml`, in `.env` versionati, negli script del progetto né nei pacchetti di gate.
5. **Riferite al Direttore**: alias creato, numero di fonti caricate e indicizzate, eventuali fonti non caricabili (paywall, file troppo grande) con il motivo. Una fonte che non entra nel Micro-Taccuino non si può verificare in F3 con NotebookLM: va verificata sulla copia locale e dichiarata nel pacchetto Gate 1.

Se gli strumenti MCP mancano e `nlm` non è disponibile, non simulate la creazione: dite al Direttore che il Micro-Taccuino non è stato creato e proseguite con le copie locali.

Se in F3 una fonte nuova entra in `sources.json` (con l'assenso del Direttore), aggiungetela anche al Micro-Taccuino con lo stesso passo 3, prima di rieseguire le verifiche.

## 3. Livello agente: F3 — fact-checking della bozza

**Taccuino da interrogare: il Micro-Taccuino d'Articolo** (`<slug>-<post_id>`, §2.1), non il Maestro. Le citazioni devono rimandare a fonti di `sources.json`; una citazione che rimanda a un articolo già pubblicato della testata non è una fonte del claim (`unsupported` se non c'è altro riscontro). Con un solo taccuino condiviso vale la nota di compatibilità di §0.

Per ogni claim estratto dalla bozza (perimetro e procedura in `factchecking_protocol.md` §6.1–6.3, passi 1–2):

> **Tetto per turno: `[providers.rag].max_claims_per_turn` (default `8`).** Ogni `notebook_query` consuma quota dell'account Google del Direttore, e una raffica di interrogazioni può far scattare il rate-limiting e bloccare la sessione per tutti. Quindi:
>
> - **mai più di `max_claims_per_turn` interrogazioni per messaggio dell'agente**; le restanti nel messaggio successivo, dopo aver letto i passaggi già ricevuti;
> - le interrogazioni remote vanno ai **nodi fattuali critici**: prima i dati destinati alla promozione, poi cifre, percentuali, date e citazioni normative; le frasi fuori perimetro (`factchecking_protocol.md` §6.1) non si interrogano mai;
> - se l'elenco dei claim supera di molto 8–15 per un articolo di lunghezza ordinaria, è iper-frammentazione (`factchecking_protocol.md` §6.2): rifate la selezione invece di distribuire le query su più turni;
> - un errore di quota o di sessione scaduta non si aggira ritentando a raffica: fermatevi e riferite al Direttore.

1. **Una domanda per claim** con `notebook_query`, nel rispetto del tetto per turno. Chiedete il passaggio, non un giudizio:

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

[providers.rag]
max_claims_per_turn = 8              # tetto di interrogazioni remote per esecuzione
```

Il tetto vale anche per la CLI: con `provider = "notebooklm"`, se `factcheck.json` contiene più claim di `max_claims_per_turn`, `verify-facts` non lancia alcuna interrogazione e termina con exit `1` e il messaggio `Error: RAG claims count (N) exceeds maximum allowed per turn (8). …` (un `RagUnavailableError`); tra un'interrogazione e l'altra applica una breve pausa. La prima risposta è ridurre `claims` ai fatti materiali (`factchecking_protocol.md` §6.1–6.2). Alzare `max_claims_per_turn` è una decisione del Direttore, non un modo per far passare il controllo.

Prerequisiti sull'host: `nlm` nel `PATH` (`uv tool install notebooklm-mcp-cli`), sessione aperta con `nlm login`, variabile `EDITORIAL_RAG_ID` con l'alias `nlm` del taccuino. Nel modello a due livelli è l'alias del **Micro-Taccuino** `<slug>-<post_id>` creato in F1 (§2.1); mai l'alias del Maestro, che contiene articoli già pubblicati ed edizioni diverse degli stessi rapporti. Prima di lanciare `verify-facts` controllate che la variabile punti all'unità giusta (`echo $EDITORIAL_RAG_ID`; PowerShell: `$env:EDITORIAL_RAG_ID`): dopo il lavoro su un'altra unità può essere rimasta impostata sul taccuino precedente.

```bash
editorial-pipeline verify-facts content/posts/post_07_titolo.md --json
```

Comportamento:

- la verifica locale gira sempre per prima: senza `factcheck.json` coerente il report resta `BLOCK`;
- poi un'interrogazione `nlm` per claim, con un finding `rag.claim` identificato dalla posizione (`Claim 3: not supported by notebook sources`);
- `BLOCK` se mancano citazioni o la risposta smentisce il claim, `WARN` se è incerta, `OK` altrimenti;
- un errore `RagUnavailableError` (riga `Error: …` su stderr) ed exit `1`, senza report, se i claim superano `max_claims_per_turn`, il corpus non è configurato, `nlm` manca, la sessione è scaduta, scade il timeout o la risposta non è JSON valido.

Come leggere i finding remoti:

| Finding remoto | Che cosa fate |
|---|---|
| `Claim N: not supported by notebook sources` (`BLOCK`) | Riaprite la fonte del claim N. Se il passaggio non c'è, correggete o togliete la frase (`unsupported`). Se c'è ma la fonte non è nel taccuino, aggiungetela (F1) o dichiaratelo nel pacchetto Gate 1 |
| `Claim N: requires review of notebook evidence` (`WARN`) | Rileggete il passaggio; motivate il `WARN` nel pacchetto Gate 1 o riformulate la frase |
| `Claim N: supported by notebook sources` (`OK`) | Nessuna azione oltre al controllo che avete già fatto: la classificazione è lessicale, non sostituisce la vostra lettura |
| `Error: RAG claims count (N) exceeds maximum allowed per turn (M)` | Troppi claim: rifate la selezione secondo `factchecking_protocol.md` §6.1–6.2 e rieseguite. Se l'elenco è già limitato ai fatti materiali (per esempio 12 claim legittimi in un articolo di 1.400 parole), riferite al Direttore, che decide se alzare il tetto per il progetto. Non spezzate `factcheck.json` per aggirare il tetto e non alzate `max_claims_per_turn` da soli |
| Altri `RagUnavailableError` (`Error: …` su corpus, `nlm`, sessione, timeout) | Non è un esito sui claim. Riferite al Direttore (sessione `nlm` scaduta, variabile vuota, timeout). **Non** ripiegate da soli su `provider = "local"` per far passare il controllo: cambiare la configurazione è una decisione del Direttore |

Il testo dei claim viene inviato a Google. Se la bozza è riservata, chiedete al Direttore prima di usare `provider = "notebooklm"`.

### 4.1 Una sola esecuzione remota per turno: divieto di rilanci ripetuti

> **Regola vincolante.** Con `provider = "notebooklm"`, `editorial-pipeline verify-facts` si esegue **al massimo una volta per turno dell'agente** (un turno = un vostro messaggio, fino alla risposta del Direttore). Ogni esecuzione lancia fino a `max_claims_per_turn` interrogazioni sull'account Google del Direttore: cinque rilanci consecutivi più una serie di controprove manuali bastano a saturare la quota e a bloccare NotebookLM per tutta la redazione.

Dopo l'esecuzione, se il report contiene `BLOCK` remoti che non sapete spiegare dalla lettura della fonte, oppure la CLI termina con un errore remoto (`NotebookLM RAG: usage limit reached …`, `query failed`, timeout, risposta non JSON):

1. **Non rilanciate `verify-facts`** nello stesso turno, né subito dopo, sperando in un exit `0` casuale: le risposte di NotebookLM non sono deterministiche e un rilancio non è una verifica.
2. **Non sparate interrogazioni di controprova** con `nlm query notebook` da terminale, né in serie né in parallelo, e non ripiegate su `notebook_query` MCP oltre il tetto di §3: è la stessa quota.
3. **Fermatevi subito.** Registrate il finding nell'handover o nel resoconto (severità `P1` per `usage limit` o un'anomalia che si ripete; indicate comando, esito e numero di claim interrogati, senza identificativi di taccuino o conversazione).
4. **Riferite al Direttore** e attendete. Un nuovo `verify-facts` si lancia solo nel turno successivo e solo dopo che il Direttore l'ha autorizzato (in caso di `usage limit`, dopo il cooldown che indica lui): **un** rilancio, non una serie.

Il messaggio della CLI `Wait before retrying or use --provider manual` è rivolto al Direttore: non autorizza l'agente a ritentare né a cambiare provider (§4, ultima riga della tabella). Un `BLOCK` remoto spiegabile (il passaggio manca davvero nella fonte) si tratta invece come da tabella: correggete la bozza o `factcheck.json`, e la riverifica avviene al turno successivo, con una sola esecuzione.

## 4-bis. F6 — Aggiornamento del Taccuino Maestro

A pubblicazione avvenuta (dopo il Gate 2 e `publish`), il Maestro si arricchisce perché le unità successive possano trovarlo in F0/F1:

1. **Su indicazione del Direttore**, aggiungete al Maestro con `source_add` (`wait = true`) l'articolo pubblicato (URL definitivo o Markdown della versione approvata) e le fonti primarie del Micro-Taccuino che il Maestro non contiene ancora. Controllate con `notebook_get` che non creiate doppioni della stessa fonte o della stessa edizione.
2. **Il Micro-Taccuino resta com'è**: serve per eventuali correzioni F6 (riverifica di un claim contestato) e per rigenerare l'audio dopo una correzione approvata. Eliminarlo (`notebook_delete`) è una decisione del Direttore, con conferma esplicita in chat.
3. Le correzioni pubblicate (`COR-<unità>-<n>`) si riflettono anche nel Maestro: sostituite la versione dell'articolo con quella corretta, su istruzione del Direttore, così le unità future non riprendono il dato errato.

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
- Trattare un `RagUnavailableError` come un `BLOCK` sui claim e riscrivere la bozza: è un problema di configurazione o di sessione.
- Interrogare il taccuino con domande che contengono più fatti: una domanda, un claim.
- Verificare in F3 sul Taccuino Maestro invece che sul Micro-Taccuino: la risposta può citare un articolo già pubblicato o l'edizione sbagliata di un rapporto (§0, §3).
- Caricare nel Micro-Taccuino fonti che non sono in `sources.json`, o creare il Micro-Taccuino prima che il Direttore abbia confermato le fonti (§2.1).
- Lasciare `EDITORIAL_RAG_ID`/`EDITORIAL_AUDIO_ID` impostate sull'alias di un'unità precedente.
- Superare `max_claims_per_turn` interrogazioni in un messaggio, o interrogare frasi di raccordo, premesse e definizioni generali: satura la quota dell'account e blocca la sessione (§3).
- Rilanciare `verify-facts` più volte di seguito, o lanciare raffiche di `nlm query notebook`, dopo un `BLOCK` inspiegabile o un `usage limit`: una sola esecuzione per turno, poi stop, finding e Direttore (§4.1).
