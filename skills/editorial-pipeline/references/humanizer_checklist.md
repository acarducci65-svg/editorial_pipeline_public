# Checklist anti-cliché (de-aizing)

Vademecum operativo per la revisione di stile in **F2b** (bozza), per le frasi riscritte in **F3** e per i testi di **F4/F5** (promozione e copioni audio). La revisione rende il testo leggibile, preciso e coerente con il registro. **Non** serve a nascondere l'origine della prima stesura, che si dichiara su `/metodo/` (principio TP4).

Tutti gli esempi sono inventati per questa guida: nomi, enti, numeri e titoli non si riferiscono a persone o fatti reali. In un testo vero ogni riferimento passa dal fact-check.

---

## 1. Come si usa

1. **Passaggio separato.** La revisione non si fa mentre si scrive. Di preferenza la esegue un agente diverso dall'autore della stesura; altrimenti lo stesso agente in un passaggio distinto, dichiarato nella prova (`reviewer_is_author: true`).
2. **Linter prima, lettura poi.** Eseguite `editorial-pipeline validate-draft <post> --json`: il linter segnala espressioni e pattern vietati dal registro attivo. Poi rileggete il testo voce per voce: il linter non coglie tutto, a volte segnala falsi positivi, e non legge le famiglie emergenti del §3 se non sono state aggiunte al registro o a `[register].extra_forbidden`.
3. **Un esito per voce.** Ogni voce si chiude con uno di quattro esiti:

| Esito | Quando | Valore JSON della chiave collegata |
|---|---|---|
| `ok` | Nessuna occorrenza | `pass` |
| `corretto` | Occorrenze trovate e riscritte | `pass` |
| `giustificato: <motivo>` | Occorrenza mantenuta per una ragione documentata (es. contrasto presente nella fonte) | `pass` |
| `failed` | Occorrenza non risolta | `fail` |

   Un `fail` impedisce di presentare il Gate 1: `verify-facts` e `check-gate` leggono `draft-review.json` e segnalano `BLOCK` (`humanizer.review`) se una voce di `[humanizer].required_items` non vale `pass` o se il `draft_digest` della revisione non coincide con la bozza corrente.
4. **Registrate** la revisione (vedi §6).
5. **Frasi riscritte in F3.** Ogni frase corretta durante il fact-check torna dalle voci 1–7 e 10 prima del Gate 1; la prova di revisione si aggiorna.

Regola generale di riscrittura: la frase corretta deve suonare come il resto del paragrafo e come l'autore, non come un modulo compilato.

## 2. Precedenza tra checklist e registri di stile

> **Regola.** Il registro attivo può *allargare le forme* e *stringere le soglie*. Non può mai allentare i vincoli sulle fonti, la voce 5 per i fatti, né i principi TP1–TP6. In caso di conflitto vale la regola più restrittiva per i **fatti** e quella del registro per la **forma**.

Le **etichette** delle voci variano da registro a registro (`checklist_mapping` nel file YAML del registro: «Tic da newsletter», «Testimonianze non documentate»…); le **chiavi CLI** no. La soglia applicabile è sempre quella del registro attivo.

### Matrice di precedenza

| Voce | `academic_essay` | `tech_blog` | `investigative` | `cultural_newsletter` | Chi prevale |
|---|---|---|---|---|---|
| 1 Enfasi vuota | Checklist | Checklist | Checklist | Checklist; nessun superlativo di maniera | Checklist |
| 2 Tic da chatbot + famiglie §3 | Checklist + lista del registro | Checklist + lista del registro | Checklist + lista del registro | Checklist + lista del registro | Unione delle liste (la più lunga) |
| 3 Strutture binarie | Soglia del registro | Soglia del registro | Soglia **0,5** ogni 1.000 parole | Soglia del registro | Registro (stringe) |
| 4 Righe isolate | Checklist | Checklist | Ammesse solo in apertura di scena datata | Ammesse con misura, mai come chiusa | Registro per la forma |
| 5 Prima persona | Solo `verified_facts` | **Plurale del tutorial ammesso** («installiamo», «vediamo»); singolare solo `verified_facts` | Singolare solo per fatti documentati dal cronista nelle evidenze | **Singolare ammessa per opinioni dichiarate**; mai per ricordi o fatti non in `verified_facts` | Registro per la forma; checklist per i fatti |
| 6 Grassetto | Checklist | `codice` per comandi, file, variabili | Checklist | Checklist | Registro per la forma |
| 7 Attribuzioni | Autore e anno in ogni attribuzione | Versione e link alla documentazione | Due conferme indipendenti; fonti riservate con formula del registro | Citazioni testuali verificate | Il più restrittivo |
| 8 Rigore del registro | Limiti dei modelli citati | Versioni, comandi riproducibili, benchmark con ambiente | Date complete, tutela delle fonti, **diritto di replica prima del Gate 2**, fatti separati dalle valutazioni | Citazioni verificate | Registro |
| 9 Voce dell'autore | Checklist | Checklist | Checklist | Checklist | Checklist |
| 10 Cautela a cascata | Checklist; cautela metodologica ammessa se attribuita al limite di uno studio | Checklist | **Condizionale di cronaca obbligatorio** per fatti non accertati giudizialmente | Checklist | Registro (eccezione deontologica) |
| Placeholder `[verificare]`, `[fonte]`, `TODO` | Vietati | Vietati | Vietati | Vietati | Vietati ovunque |

## 3. Famiglie di cliché emergenti

Pattern frequenti nei modelli generativi recenti. Le espressioni regolari usano la sintassi Python `re` con `IGNORECASE`, sul testo visibile normalizzato (come il linter). Sono spie: un riscontro si valuta in lettura, non si corregge alla cieca. Per farle segnalare alla CLI aggiungetele a `[register].extra_forbidden` o al file del registro.

### 3.1 Aperture d'epoca (voce 2)

Prima frase generica e non datata: il lettore non riceve nessun fatto.

```regex
\bin un(?:'| )(?:mondo|epoca|era) (?:sempre più|in cui|dove|come questo)\b
\bnell'(?:era|epoca) (?:del|della|dell'|dei|delle|digitale)\b
\b(?:al giorno d'oggi|oggi più che mai|ora più che mai)\b
\bnegli ultimi anni\b.{0,40}\b(?:rivoluzionato|trasformato|cambiato radicalmente)\b
```

| Prima | Dopo |
|---|---|
| «Nell'era dell'intelligenza artificiale, anche le biblioteche cambiano.» | «Da marzo la biblioteca civica presta lettori di e-book: 140 prestiti nel primo mese.» |

**Riscrittura:** partite da un fatto datato e localizzato; indicate l'anno, non l'epoca.

### 3.2 Chiuse trionfali o sospese (voce 2)

Chiusa che giudica al posto del lettore o promette senza dati.

```regex
\b(?:una cosa è certa|solo il tempo (?:potrà dirlo|lo dirà)|il futuro è (?:luminoso|roseo|promettente))\b
\b(?:rappresenta|segna|costituisce) un passo (?:importante|decisivo|fondamentale) verso\b
\bla strada è ancora lunga\b
\bil viaggio è (?:appena|solo) (?:iniziato|cominciato)\b
\buna sfida e (?:insieme )?un'opportunità\b
```

| Prima | Dopo |
|---|---|
| «Il nuovo orto rappresenta un passo importante verso un quartiere più verde. Il viaggio è appena iniziato.» | «Il comitato chiederà altri due lotti a settembre; la delibera è attesa entro fine anno.» |

**Riscrittura:** chiudete con un fatto, con il passo successivo datato o con una domanda aperta attribuita a qualcuno.

### 3.3 Residui da assistente (voce 2, errore di produzione)

Residuo della chat finito nel testo. Non è una questione di stile: va tolto sempre, in ogni registro.

```regex
\b(?:certo!|ottima domanda|ecco (?:una|la) versione (?:rivista|aggiornata))
\bspero che (?:questo|questa guida|l'articolo) ti sia stat[oa] utile\b
\bfammi sapere se\b
\bcome modello (?:linguistico|di intelligenza artificiale)\b
```

**Riscrittura:** togliere. Un residuo in un testo presentato al Gate 1 si registra tra gli errori intercettati.

### 3.4 Gerundi di coda interpretativi (voce 7)

Un'interpretazione non attribuita attaccata a un fatto: è un claim nascosto che sfugge all'estrazione in F3.

```regex
,\s(?:sottolineando|evidenziando|dimostrando|riflettendo|contribuendo a|testimoniando)\b
```

| Prima | Dopo |
|---|---|
| «Gli iscritti al corso serale sono raddoppiati, riflettendo una crescente fame di competenze digitali.» | «Gli iscritti al corso serale sono passati da 20 a 41 (registro iscrizioni, foglio 2025).» |

**Riscrittura:** attribuite l'interpretazione a una fonte con locator, oppure togliete il gerundio.

### 3.5 Domanda retorica con risposta immediata (voce 4)

Variante della riga isolata e della struttura binaria.

```regex
\b\w+(?:\s\w+){0,3}\?\s+(?:semplice|sorprendente|nessuno|tutto|niente|eccolo|ecco)[.!]
\bil (?:motivo|risultato|segreto|problema)\?\s
```

| Prima | Dopo |
|---|---|
| «Il risultato? Sorprendente.» | «Il tempo di compilazione è sceso da 4 minuti a 50 secondi.» |

**Riscrittura:** dite il fatto nella frase dichiarativa.

### 3.6 Lessico calcato dall'inglese (voce 2)

Lessico astratto che sostituisce il nome della cosa.

```regex
\bnavigare (?:la|le) (?:complessità|sfide|incertezz[ae])\b
\bgioca(?:re|no|)? un ruolo (?:chiave|cruciale|fondamentale)\b
\b(?:è|sono) (?:una )?testimonianza d(?:i|el|ella)\b
\btassello fondamentale\b
\b(?:andiamo|andremo) ad? (?:analizzare|vedere|scoprire|esplorare)\b
\b(?:panorama|ecosistema) (?:digitale|attuale|tecnologico)\b
```

| Prima | Dopo |
|---|---|
| «La cooperativa gioca un ruolo chiave nell'ecosistema locale.» | «La cooperativa gestisce tre delle cinque mense scolastiche del comune.» |

**Riscrittura:** nominate chi fa che cosa; «andiamo ad analizzare» → entrate nel contenuto senza annunciarlo.

### 3.7 Triadi a effetto (voce 3)

Tre aggettivi o sostantivi in serie, ritmati, senza informazione aggiuntiva. Il rilevamento è euristico (`WARN`): decide chi rivede.

```regex
\b(\w+), (\w+) e (\w+)[.!]\s*$
\b(?:più|meno) \w+, (?:più|meno) \w+, (?:più|meno) \w+\b
```

| Prima | Dopo |
|---|---|
| «Un'app veloce, semplice, sicura.» | «L'app si apre in meno di un secondo e cifra i dati sul telefono.» |

**Riscrittura:** tenete gli elementi che hanno un fatto a sostegno e ditelo.

### 3.8 Maiuscole all'inglese nei titoli (voce 6)

Title case estraneo all'italiano, frequente nei titoli generati e nelle slide. Unica eccezione alla regola generale: questo pattern va applicato **senza** `IGNORECASE` e con `MULTILINE`, altrimenti segnala ogni titolo.

```regex
^#{1,6}\s+(?:[A-ZÀ-Ý]\w*\s+){3,}[A-ZÀ-Ý]\w*\s*$
```

| Prima | Dopo |
|---|---|
| «Come Funziona La Lievitazione Lenta» | «Come funziona la lievitazione lenta» |

**Riscrittura:** maiuscola solo all'inizio e sui nomi propri.

### 3.9 Cautela a cascata (voce 10)

Spia sintattica della voce 10 (sotto):

```regex
\b(?:potrebbe|sembrerebbe|parrebbe)\b.{0,40}\b(?:potenzialmente|in un certo senso|in qualche misura|forse)\b
\b(?:si potrebbe sostenere che|non è da escludere che|sembrerebbe suggerire)\b
```

**Riscrittura:** dite il fatto con il suo limite esplicito, oppure togliete la frase.

---

## 4. Le 10 voci

| # | Voce | Chiave CLI |
|---|---|---|
| 1 | Enfasi vuota e autorità presa in prestito | `empty_emphasis` |
| 2 | Tic da chatbot e da blogger (con §3.1–3.3, 3.6) | `empty_emphasis` |
| 3 | Strutture binarie forzate (con §3.7) | `negative_parallelism` |
| 4 | Righe isolate a effetto (con §3.5) | `isolated_lines` |
| 5 | Ricordi inventati | `invented_autobiography` |
| 6 | Grassetto e tipografia sobri (con §3.8) | `decorative_bold` |
| 7 | Attribuzioni puntuali (con §3.4) | `vague_attribution` |
| 8 | Rigore specifico del registro | prova testuale |
| 9 | Voce dell'autore | prova testuale |
| 10 | Cautela a cascata (con §3.9) | `hedge_stacking` (proposta; finché la CLI non la espone, prova testuale) |

Le chiavi 1–7 compaiono in `draft-review.json` / `social-review.json`; una chiave è `pass` solo se tutte le voci collegate sono `ok`, `corretto` o `giustificato`. Le voci 8, 9 e 10 si documentano nella prova testuale e in `items_detail`.

Nota sulle chiavi: i registri chiamano la regola dei tic `chatbot_tics`; la CLI la riporta come `style.empty_emphasis.*` con il messaggio `[registro/chatbot_tics]`. È la stessa voce.

---

### Voce 1 — Enfasi vuota e autorità presa in prestito

**Spia:** aggettivi che chiedono fiducia invece di dare un motivo: *straordinario, cruciale, fondamentale, prestigioso, rivoluzionario, imprescindibile, autorevole*.

| Prima | Dopo |
|---|---|
| «Un'indagine dell'autorevolissimo Osservatorio Ciclabile Padano conferma…» | «Un'indagine dell'Osservatorio Ciclabile Padano (rapporto 2024, p. 9) stima…» |
| «Questa libreria straordinaria semplifica radicalmente il parsing.» | «Questa libreria legge i file CSV con intestazioni irregolari senza configurazione aggiuntiva.» |
| «Un passaggio cruciale per il futuro del quartiere.» | «Il parcheggio diventa un orto condiviso da 40 lotti.» |

**Test:** se l'aggettivo si toglie senza perdere informazione, si toglie. Se serve a dire perché una cosa conta, si dice con un fatto.

### Voce 2 — Tic da chatbot e da blogger

**Spia:** preamboli, annunci e chiuse che riempiono: *è interessante notare che, vale la pena sottolineare, immergiamoci, in conclusione possiamo dire, ecco perché è importante, scopriamolo insieme*; più le famiglie §3.1 (aperture d'epoca), §3.2 (chiuse trionfali), §3.3 (residui da assistente), §3.6 (lessico calcato).

| Prima | Dopo |
|---|---|
| «Vale la pena sottolineare che le iscrizioni sono cresciute.» | «Le iscrizioni sono passate da 120 a 310 in due anni.» |
| «In un mondo sempre più connesso, la posta cartacea resiste.» | «Il circolo spedisce ancora 800 lettere al mese, quasi tutte a soci sopra i settant'anni.» |
| «Scopriamo insieme come funziona una lievitazione lenta.» | «Una lievitazione lenta dura dalle 18 alle 24 ore in frigorifero.» |
| «In conclusione, il progetto si è rivelato un successo.» | «Dopo un anno, i tempi di attesa allo sportello sono scesi da 25 a 9 minuti.» |

### Voce 3 — Strutture binarie forzate

**Spia:** «non X, ma Y», «non si tratta di X, si tratta di Y», «non è solo X, è Y», «più che X, Y». Anche triadi a effetto (§3.7) e domande retoriche in serie.

Il pattern **non è vietato in sé**: è vietato quando il contrasto lo crea la frase e non la fonte. Oltre la soglia del registro attivo (di norma un'occorrenza ogni 1.000 parole; 0,5 in `investigative`) ogni occorrenza va motivata.

| Caso | Testo | Esito |
|---|---|---|
| Retorico | «Non è solo un mercato, è una comunità.» | `corretto` → «Il sabato i banchi restano aperti fino alle 14 e metà dei clienti arriva a piedi.» |
| Retorico | «Il problema non è il software, sono le abitudini.» | `corretto` → «Il gestionale funzionava; due reparti su cinque continuavano a usare i fogli di calcolo (verbale interno, punto 4).» |
| Dalla fonte | «Il calo non dipende dai prezzi ma dagli orari ridotti, come mostra la tabella 2 del rapporto.» | `giustificato: contrasto riportato dalla fonte, tabella 2` |

### Voce 4 — Righe isolate a effetto

**Spia:** chiuse di una o due parole su riga propria, a capo drammatici, domande retoriche con risposta immediata (§3.5).

| Prima | Dopo |
|---|---|
| «…e il forno chiuse dopo sessant'anni.<br><br>Così.» | «…e il forno chiuse dopo sessant'anni, il 31 marzo.» |
| «Il test è passato.<br><br>Al primo colpo.» | «Il test è passato al primo tentativo su tutte e tre le versioni di Python supportate.» |

Ammesse le frasi brevi di ambientazione in apertura («Lunedì, ore 6. Il mercato ittico apre.»). Il linter non distingue i due casi: decide chi rivede.

### Voce 5 — Ricordi inventati

**Regola:** un modello non inventa ricordi, dialoghi, aneddoti o esperienze dell'autore. Le scene quotidiane si scrivono come esperimenti mentali (seconda persona plurale o forma impersonale). La prima persona singolare per **fatti** è ammessa solo per quelli elencati in `author_profile.yaml` (`first_person.verified_facts`) o registrati nelle evidenze. Le forme ammesse in più dal registro (opinioni dichiarate, plurale del tutorial) sono nella matrice del §2.

| Prima | Esito | Dopo |
|---|---|---|
| «Stamattina, in fila dal fornaio, osservo i prezzi e penso al grano.» | `failed` | «Provate a confrontare il prezzo di un chilo di pane con quello di cinque anni fa.» |
| «Quando ho aperto il mio primo repository, nessuno scriveva test.» | `failed` se non è un fatto dichiarato | «Nei progetti open source dei primi anni Duemila i test automatici erano rari (indagine X, anno, p. N).» |
| «Nel mio manuale del 2015 proponevo…» | `ok` se il lavoro è dichiarato come fonte personale e il fact-check ha il locator | — |

**Spia nei testi promozionali:** verbi in prima persona singolare al presente in scene comuni (*entro, guardo, scelgo, apro, conto*). Ogni registro ne elenca altri.

### Voce 6 — Grassetto e tipografia sobri

- Ammesso sulla prima definizione di un concetto e, al massimo, su un dato centrale per sezione.
- Mai su frasi intere (oltre 8 parole) né come decorazione.
- Spia: più di un grassetto ogni 80 parole.
- Nei registri tecnici comandi, file e variabili vanno in `codice`, non in grassetto.
- Sui social che non rendono il Markdown i marcatori `**` sono un errore: toglieteli.
- Nei testi pubblici di F4 (file di canale e slide) niente `claim_id`, tag `[C1]` o tabelle: il tracciamento sta in `social-review.md` (§6).
- Titoli e slide senza maiuscole all'inglese (§3.8).

| Prima | Dopo |
|---|---|
| «**Il compostaggio domestico riduce in modo significativo i rifiuti organici di ogni famiglia.**» | «Il **compostaggio domestico** riduce i rifiuti organici di circa un terzo (fonte, p. N).» |

### Voce 7 — Attribuzioni puntuali

**Spia:** *gli esperti dicono, studi dimostrano, è noto che, secondo molti, la scienza concorda, si dice che*; gerundi di coda interpretativi (§3.4).

| Prima | Dopo |
|---|---|
| «Gli esperti concordano che la settimana corta aumenta la produttività.» | «Due sperimentazioni aziendali (Autore A, anno; Autore B, anno) arrivano a risultati opposti.» |
| «Studi dimostrano che il verde urbano abbassa la temperatura.» | «Una rassegna di 30 misure (Autore, anno, figura 3) stima un calo medio di 1–2 °C nelle ore più calde.» |
| «Secondo fonti vicine all'azienda…» | «Secondo due dipendenti che hanno chiesto di non essere nominati…» (solo se il registro lo ammette e la fonte è registrata) |

**Test:** se non si riesce a dire chi, dove e con quale locator, la frase si toglie.

### Voce 8 — Rigore specifico del registro

Ogni registro aggiunge regole proprie (`register_specific` nel file YAML del registro). Il riepilogo è nella riga 8 della matrice del §2. In `investigative` la tutela delle fonti (due conferme indipendenti, formula per le fonti riservate) e il **diritto di replica** (richiesta prima del Gate 2, data ed esito nel testo) sono controlli con rischio legale: si documentano voce per voce.

Si verificano a mano e si annotano nella prova testuale.

### Voce 9 — Voce dell'autore

Il testo rivisto deve suonare come l'autore, non come un modello che ha tolto i propri tic. In caso di dubbio, confrontatelo con un testo scritto interamente dall'autore sullo stesso tema. Non si aggiungono ironia, colore o espressioni dialettali che l'autore non usa. Le parti riscritte dal Direttore non si «normalizzano».

### Voce 10 — Cautela a cascata

**Spia:** due o più formule di cautela nella stessa frase o claim (*potrebbe, sembrerebbe, in un certo senso, si potrebbe sostenere, non è da escludere, potenzialmente, in qualche misura*). Pattern in §3.9. È il contrario dell'enfasi vuota, ed è altrettanto un tic: diluisce i claim fino a renderli non verificabili, e il fact-check non trova cosa controllare.

| Prima | Dopo |
|---|---|
| «Questo potrebbe potenzialmente suggerire un certo impatto sulla mobilità.» | «Nel 2024 gli spostamenti in bici sono cresciuti del 18% (rapporto, p. 14); il rapporto non stima l'effetto della nuova pista.» |

**Test:** la frase dice una cosa che il fact-check può controllare? Se no, o si dice il fatto con il suo limite («il rapporto non stima…»), o la frase si toglie.

**Eccezione di registro:** in `investigative` il condizionale di cronaca per fatti non accertati giudizialmente («avrebbe versato», «secondo l'accusa») è un obbligo deontologico, non un tic: esito `giustificato: condizionale di cronaca, stato del procedimento in <regola del registro>`. In `academic_essay` la cautela che riporta il limite dichiarato di uno studio è ammessa se attribuita (autore, anno, locator).

---

## 5. Formule vietate in ogni testo pubblico

Valgono in bozze, copy, copioni e pagine di trasparenza. Sono le `deprecated_phrases` del manifesto. Il linter (`validate-draft`) le legge da `[manifesto].file` e le segnala come `BLOCK`.

| Non scrivete | Perché | Al suo posto |
|---|---|---|
| «zero allucinazioni», «verificato al 100%» | Promessa non verificabile | Descrivete il controllo e rimandate a `/metodo/` e `/correzioni/` |
| «scritto da una persona» | Falso se la prima stesura è di un modello | «prima stesura di [modello], rivista e approvata da [ruolo]» |
| «non rilevabile», «sembra umano» | Travisa lo scopo della revisione | «revisione di stile con checklist pubblica» |

Un dato riscontrato solo su fonte secondaria non si descrive come «verificato» e non entra nei materiali promozionali.

## 6. Registrazione della revisione

La revisione produce due file in `evidence/<post_id>/`:

- `draft-review.json` (F2b, aggiornato dopo F3) o `social-review.json` (F4/F5);
- una prova testuale (`draft-review.md` / `social-review.md`) con l'esito di ogni voce, le correzioni fatte e le giustificazioni.

```json
{
  "schema_version": 1,
  "post_id": "post_07",
  "phase": "F2b",
  "register_id": "tech_blog",
  "draft_digest": "v1:<digest completo dell'unità dopo la revisione>",
  "reviewer": "<etichetta dell'agente>",
  "reviewer_is_author": false,
  "reviewed_at": "2026-11-13T10:00:00+01:00",
  "items": {
    "empty_emphasis": "pass",
    "negative_parallelism": "pass",
    "isolated_lines": "pass",
    "vague_attribution": "pass",
    "decorative_bold": "pass",
    "invented_autobiography": "pass"
  },
  "items_detail": {
    "1": "corretto", "2": "ok", "3": "giustificato: contrasto in fonte, tabella 2",
    "4": "ok", "5": "ok", "6": "ok", "7": "ok", "8": "ok", "9": "ok", "10": "corretto"
  },
  "evidence_path": "evidence/post_07/draft-review.md",
  "evidence_sha256": "<sha256 della prova>"
}
```

Struttura minima della prova testuale:

```markdown
# Revisione di stile — post_07 (registro tech_blog)

Revisore: <agente>, passaggio separato dalla stesura.

| # | Voce | Esito | Note |
|---|---|---|---|
| 1 | Enfasi vuota | corretto | §2: «rivoluzionario» → descrizione della funzione |
| 2 | Tic da chatbot | ok | nessuna apertura d'epoca né residuo da assistente |
| 3 | Strutture binarie | giustificato: contrasto in fonte, tabella 2 | §4 |
| … | … | … | … |
| 9 | Voce dell'autore | ok | confronto con il paragrafo riscritto dal Direttore |
| 10 | Cautela a cascata | corretto | §3: «potrebbe potenzialmente» → dato con limite dichiarato |

## Frasi riscritte in F3
| Prima | Dopo | Voci ricontrollate |
|---|---|---|
```

`social-review.md` ha in più una riga per ogni unità di testo promozionale (slide, post, primo commento, didascalia, story, abstract, copione), con esito e, per ogni numero, il `claim_id` che lo copre.

**Separazione netta fra testo pubblico e tracciamento (F4).** Il `claim_id` vive solo qui, in `social-review.md` (o in una sezione redazionale separata di `copy.md`). I file di canale (`linkedin.md`, `twitter.md`, `instagram.md`, `newsletter.md`) e le slide HTML/PNG del carosello contengono solo testo pubblico pulito: nessun tag `[C1]`/`[C7]`, nessun `claim_id`, nessun locator interno, nessuna nota di stesura, intestazione redazionale o tabella. Sulle slide la fonte si scrive per il lettore (`Fonte: Commissione europea, Ageing Report 2024, p. 5`); nei file di canale il testo è pronto al copia-incolla, in prosa scorrevole, e chiude con l'URL dell'articolo (`[project].base_url` + slug). Un tag interno trovato nel testo pubblico è un errore da correggere prima della consegna, non una voce da giustificare.

```markdown
## Tracciamento dati del kit social
| Unità | Testo pubblico (estratto) | claim_id | Locator | Esito |
|---|---|---|---|---|
| linkedin.md §2 | «…la spesa salirebbe di N punti di PIL…» | C7 | Ageing Report 2024, p. 5 | ok |
| slide 3 | «Fonte: Commissione europea, Ageing Report 2024, p. 5» | C1 | p. 5, tab. 1 | ok |
```

La CLI legge `post_id`, `draft_digest` e `items` (le chiavi di `[humanizer].required_items` devono valere `pass`); gli altri campi sono documentali. `social-review.json` non è letto dalla CLI.

Se il testo cambia dopo la revisione, si rivedono le parti cambiate e si aggiorna la prova; poi `draft_digest`. Ricalcolare solo il digest è un errore: il report torna coerente ma la revisione non copre il testo nuovo.

## 7. Limiti

La checklist intercetta le forme più riconoscibili, non tutte. Le espressioni regolari del §3 producono falsi positivi e falsi negativi: sono spie per chi rivede, non un verdetto. La checklist non giudica se un argomento regge o se un testo è interessante. Non sostituisce il Gate 1: è materiale che il Direttore legge prima di decidere.
