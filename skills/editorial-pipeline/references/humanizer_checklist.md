# Checklist anti-cliché (de-aizing)

Vademecum operativo per la revisione di stile in **F2** (bozza) e **F4** (testi promozionali). La revisione rende il testo leggibile, preciso e coerente con il registro. **Non** serve a nascondere l'origine della prima stesura, che si dichiara su `/metodo/` (principio TP4).

Tutti gli esempi sono inventati per questa guida: nomi, enti, numeri e titoli non si riferiscono a persone o fatti reali. In un testo vero ogni riferimento passa dal fact-check.

---

## 1. Come si usa

1. **Passaggio separato.** La revisione non si fa mentre si scrive. Di preferenza la esegue un agente diverso dall'autore della stesura; altrimenti lo stesso agente in un passaggio distinto, dichiarato nella prova.
2. **Linter prima, lettura poi.** Eseguite `editorial-pipeline validate-draft <post> --json`: il linter segnala espressioni e pattern vietati dal registro attivo. Poi rileggete il testo voce per voce: il linter non coglie tutto e a volte segnala falsi positivi.
3. **Un esito per voce.** Ogni voce si chiude con uno di quattro esiti:

| Esito | Quando |
|---|---|
| `ok` | Nessuna occorrenza |
| `corretto` | Occorrenze trovate e riscritte |
| `giustificato: <motivo>` | Occorrenza mantenuta per una ragione documentata (es. contrasto presente nella fonte) |
| `failed` | Occorrenza non risolta: blocca il gate |

4. **Registrate** la revisione (vedi §4).

Regola generale di riscrittura: la frase corretta deve suonare come il resto del paragrafo e come l'autore, non come un modulo compilato.

## 2. Le 9 voci

| # | Voce | Chiave CLI |
|---|---|---|
| 1 | Enfasi vuota e autorità presa in prestito | `empty_emphasis` |
| 2 | Tic da chatbot e da blogger | `empty_emphasis` |
| 3 | Strutture binarie forzate | `negative_parallelism` |
| 4 | Righe isolate a effetto | `isolated_lines` |
| 5 | Ricordi inventati | `invented_autobiography` |
| 6 | Grassetto sobrio | `decorative_bold` |
| 7 | Attribuzioni puntuali | `vague_attribution` |
| 8 | Rigore specifico del registro | prova testuale |
| 9 | Voce dell'autore | prova testuale |

Le chiavi 1–7 compaiono in `draft-review.json` / `social-review.json`; una chiave è `pass` solo se tutte le voci collegate sono `ok`, `corretto` o `giustificato`. Le voci 8 e 9 si documentano nella prova testuale.

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

**Spia:** preamboli, annunci e chiuse che riempiono: *è interessante notare che, vale la pena sottolineare, immergiamoci, in un mondo in cui, in conclusione possiamo dire, ecco perché è importante, scopriamolo insieme*.

| Prima | Dopo |
|---|---|
| «Vale la pena sottolineare che le iscrizioni sono cresciute.» | «Le iscrizioni sono passate da 120 a 310 in due anni.» |
| «In un mondo sempre più connesso, la posta cartacea resiste.» | «Il circolo spedisce ancora 800 lettere al mese, quasi tutte a soci sopra i settant'anni.» |
| «Scopriamo insieme come funziona una lievitazione lenta.» | «Una lievitazione lenta dura dalle 18 alle 24 ore in frigorifero.» |
| «In conclusione, il progetto si è rivelato un successo.» | «Dopo un anno, i tempi di attesa allo sportello sono scesi da 25 a 9 minuti.» |

### Voce 3 — Strutture binarie forzate

**Spia:** «non X, ma Y», «non si tratta di X, si tratta di Y», «non è solo X, è Y», «più che X, Y». Anche triadi a effetto («veloce, economico, inaffidabile») e domande retoriche in serie.

Il pattern **non è vietato in sé**: è vietato quando il contrasto lo crea la frase e non la fonte. Oltre la soglia del registro (di norma un'occorrenza ogni 1.000 parole) ogni occorrenza va motivata.

| Caso | Testo | Esito |
|---|---|---|
| Retorico | «Non è solo un mercato, è una comunità.» | `corretto` → «Il sabato i banchi restano aperti fino alle 14 e metà dei clienti arriva a piedi.» |
| Retorico | «Il problema non è il software, sono le abitudini.» | `corretto` → «Il gestionale funzionava; due reparti su cinque continuavano a usare i fogli di calcolo (verbale interno, punto 4).» |
| Dalla fonte | «Il calo non dipende dai prezzi ma dagli orari ridotti, come mostra la tabella 2 del rapporto.» | `giustificato: contrasto riportato dalla fonte, tabella 2` |

### Voce 4 — Righe isolate a effetto

**Spia:** chiuse di una o due parole su riga propria, a capo drammatici.

| Prima | Dopo |
|---|---|
| «…e il forno chiuse dopo sessant'anni.<br><br>Così.» | «…e il forno chiuse dopo sessant'anni, il 31 marzo.» |
| «Il test è passato.<br><br>Al primo colpo.» | «Il test è passato al primo tentativo su tutte e tre le versioni di Python supportate.» |

Ammesse le frasi brevi di ambientazione in apertura («Lunedì, ore 6. Il mercato ittico apre.»). Il linter non distingue i due casi: decide chi rivede.

### Voce 5 — Ricordi inventati

**Regola:** un modello non inventa ricordi, dialoghi, aneddoti o esperienze dell'autore. Le scene quotidiane si scrivono come esperimenti mentali (seconda persona plurale o forma impersonale). La prima persona singolare è ammessa solo per i fatti elencati in `author_profile.yaml` (`first_person.verified_facts`) o registrati nelle evidenze.

| Prima | Esito | Dopo |
|---|---|---|
| «Stamattina, in fila dal fornaio, osservo i prezzi e penso al grano.» | `failed` | «Provate a confrontare il prezzo di un chilo di pane con quello di cinque anni fa.» |
| «Quando ho aperto il mio primo repository, nessuno scriveva test.» | `failed` se non è un fatto dichiarato | «Nei progetti open source dei primi anni Duemila i test automatici erano rari (indagine X, anno, p. N).» |
| «Nel mio manuale del 2015 proponevo…» | `ok` se il lavoro è dichiarato come fonte personale e il fact-check ha il locator | — |

**Spia nei testi promozionali:** verbi in prima persona singolare al presente in scene comuni (*entro, guardo, scelgo, apro, conto*). Ogni registro ne elenca altri.

### Voce 6 — Grassetto sobrio

- Ammesso sulla prima definizione di un concetto e, al massimo, su un dato centrale per sezione.
- Mai su frasi intere (oltre 8 parole) né come decorazione.
- Spia: più di un grassetto ogni 80 parole.
- Nei registri tecnici comandi, file e variabili vanno in `codice`, non in grassetto.
- Sui social che non rendono il Markdown i marcatori `**` sono un errore: toglieteli.

| Prima | Dopo |
|---|---|
| «**Il compostaggio domestico riduce in modo significativo i rifiuti organici di ogni famiglia.**» | «Il **compostaggio domestico** riduce i rifiuti organici di circa un terzo (fonte, p. N).» |

### Voce 7 — Attribuzioni puntuali

**Spia:** *gli esperti dicono, studi dimostrano, è noto che, secondo molti, la scienza concorda, si dice che*.

| Prima | Dopo |
|---|---|
| «Gli esperti concordano che la settimana corta aumenta la produttività.» | «Due sperimentazioni aziendali (Autore A, anno; Autore B, anno) arrivano a risultati opposti.» |
| «Studi dimostrano che il verde urbano abbassa la temperatura.» | «Una rassegna di 30 misure (Autore, anno, figura 3) stima un calo medio di 1–2 °C nelle ore più calde.» |
| «Secondo fonti vicine all'azienda…» | «Secondo due dipendenti che hanno chiesto di non essere nominati…» (solo se il registro lo ammette e la fonte è registrata) |

**Test:** se non si riesce a dire chi, dove e con quale locator, la frase si toglie.

### Voce 8 — Rigore specifico del registro

Ogni registro aggiunge regole proprie (`register_specific` nel file YAML del registro). Esempi:

| Registro | Controllo tipico |
|---|---|
| `academic_essay` | Condizioni e limiti dei modelli citati; autore e anno in ogni attribuzione |
| `tech_blog` | Versioni dichiarate, comandi riproducibili, benchmark con ambiente e numero di ripetizioni |
| `investigative` | Date complete, tutela delle fonti, diritto di replica, fatti separati dalle valutazioni |
| `cultural_newsletter` | Citazioni testuali verificate, nessun superlativo di maniera |

Si verificano a mano e si annotano nella prova testuale.

### Voce 9 — Voce dell'autore

Il testo rivisto deve suonare come l'autore, non come un modello che ha tolto i propri tic. In caso di dubbio, confrontatelo con un testo scritto interamente dall'autore sullo stesso tema. Non si aggiungono ironia, colore o espressioni dialettali che l'autore non usa. Le parti riscritte dal Direttore in F2 non si «normalizzano».

---

## 3. Formule vietate in ogni testo pubblico

Oltre al registro, il linter cerca le `deprecated_phrases` del manifesto. Valgono in bozze, copy e pagine di trasparenza:

| Non scrivete | Perché | Al suo posto |
|---|---|---|
| «zero allucinazioni», «verificato al 100%» | Promessa non verificabile | Descrivete il controllo e rimandate a `/metodo/` e `/correzioni/` |
| «scritto da una persona» | Falso se la prima stesura è di un modello | «prima stesura di [modello], rivista e approvata da [ruolo]» |
| «non rilevabile», «sembra umano» | Travisa lo scopo della revisione | «revisione di stile con checklist pubblica» |

Un dato riscontrato solo su fonte secondaria non si descrive come «verificato» e non entra nei materiali promozionali.

## 4. Registrazione della revisione

La revisione produce due file in `evidence/<post_id>/`:

- `draft-review.json` (F2) o `social-review.json` (F4);
- una prova testuale (`draft-review.md` / `social-review.md`) con l'esito di ogni voce, le correzioni fatte e le giustificazioni.

```json
{
  "reviewer": "humanizer (passaggio separato dalla stesura)",
  "register_id": "tech_blog",
  "digest": "<digest dell'unità dopo la revisione>",
  "items": {
    "empty_emphasis": "pass",
    "negative_parallelism": "pass",
    "isolated_lines": "pass",
    "vague_attribution": "pass",
    "decorative_bold": "pass",
    "invented_autobiography": "pass"
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
| 2 | Tic da chatbot | ok | — |
| 3 | Strutture binarie | giustificato: contrasto in fonte, tabella 2 | §4 |
| … | … | … | … |
| 9 | Voce dell'autore | ok | confronto con il paragrafo riscritto dal Direttore |
```

`social-review.md` ha in più una riga per ogni unità di testo promozionale (slide, post, primo commento, didascalia, story, abstract), con esito e, per ogni numero, il `claim_id` che lo copre.

Se il testo cambia dopo la revisione, si rivedono le parti cambiate e si aggiorna la prova; poi il digest. Ricalcolare solo il digest è un errore: il report torna coerente ma la revisione non copre il testo nuovo.

## 5. Limiti

La checklist intercetta le forme più riconoscibili, non tutte. Non giudica se un argomento regge o se un testo è interessante. Non sostituisce il Gate 1: è materiale che il Direttore legge prima di decidere.
