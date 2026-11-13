# Guida all'umanizzazione (de-aizing)

Questa guida descrive la revisione di stile delle fasi F2b (bozza) e F4 (testi promozionali): cosa si cerca, come si corregge, come si registra. Vale per agenti e revisori umani.

## 1. Scopo

L'Umanizzatore rende un testo leggibile, preciso e onesto rispetto al registro scelto. **Non** serve a nascondere che la prima stesura è di un modello: quella origine si dichiara sulla pagina /metodo/. La checklist è pubblica proprio per questo.

Una buona revisione toglie tre cose che i modelli tendono a introdurre:

1. **enfasi senza contenuto** — aggettivi e preamboli che promettono importanza invece di mostrarla;
2. **retorica di struttura** — contrasti, triadi e righe a effetto creati dalla frase e non dai fatti;
3. **fatti non sostenuti** — attribuzioni vaghe e ricordi inventati.

## 2. Quando si applica

- **F2b**, dopo la prima stesura e **prima** del fact-check. F3 verifica il testo già rivisto; se la revisione cambia un claim dopo F3, il fact-check diventa `stale`.
- **F4**, su tutti i testi promozionali: post, didascalie, slide, anteprime, card. Sono testi nuovi ed è lì che compaiono più spesso finti ricordi e numeri arrotondati.

Revisore: di preferenza un agente diverso da chi ha scritto; altrimenti lo stesso agente in un passaggio separato, dichiarato nella revisione.

## 3. La checklist

Ogni registro in `templates/registers/` declina le stesse nove voci. Le prime sette hanno una chiave CLI; le ultime due si documentano nella prova testuale (`evidence_path`).

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

Ogni voce si chiude con uno di quattro esiti: `ok`, `corretto`, `giustificato: <motivo>`, `failed`. Una chiave CLI è `pass` solo se tutte le voci collegate sono `ok`, `corretto` o `giustificato`.

## 4. Le voci, con esempi prima/dopo

Gli esempi sono costruiti per questa guida. Le riscritture indicano una direzione: la frase finale deve suonare come il resto del paragrafo, non come un modulo.

### 4.1 Enfasi vuota e autorità presa in prestito

Aggettivi che chiedono al lettore di fidarsi invece di dargli un motivo.

| Prima | Dopo |
|---|---|
| «Uno studio pubblicato sulla prestigiosa rivista *Journal of Urban Studies*…» | «Uno studio pubblicato sul *Journal of Urban Studies* nel 2019…» |
| «Due brillanti ricercatori hanno dimostrato…» | «Marta Rinaldi e Tomás Ortega hanno stimato…» |
| «Questo framework rivoluzionario cambia tutto.» | «Questo framework genera i client dalle specifiche OpenAPI, eliminando il codice scritto a mano per 40 endpoint.» |
| «Un romanzo imperdibile.» | «Un romanzo per chi ha amato la prima parte della trilogia: stessa città, trent'anni dopo.» |

Regola pratica: se l'aggettivo si può togliere senza perdere informazione, si toglie. Se serve a dire perché una cosa conta, lo si dice con un fatto.

### 4.2 Tic da chatbot e da blogger

Preamboli, annunci e chiuse che riempiono senza dire.

| Prima | Dopo |
|---|---|
| «È affascinante notare che la popolazione è raddoppiata.» | «La popolazione è raddoppiata tra il 1961 e il 1991.» |
| «Ecco il paradosso: più biblioteche, meno prestiti.» | «Tra il 2010 e il 2020 le biblioteche sono aumentate del 12%, i prestiti sono calati del 30%.» |
| «Immergiamoci nel mondo dei container.» | «Un container è un processo isolato con il proprio filesystem. Partiamo da qui.» |
| «In conclusione, possiamo affermare che il progetto ha funzionato.» | «Dopo sei mesi il tempo medio di risposta è sceso da 4 a 1,5 giorni.» |

### 4.3 Strutture binarie forzate

Il pattern «non X, ma Y» (e varianti: «non si tratta di X, si tratta di Y», «non è solo X, è Y») è il tic più riconoscibile della scrittura generata. **Non è vietato in sé**: è vietato quando il contrasto lo crea la frase e non le fonti.

| Caso | Testo | Esito |
|---|---|---|
| Retorico | «Non è solo un caffè, è un rituale.» | `corretto` → «Al bancone il caffè si beve in piedi, in meno di un minuto.» |
| Retorico | «Il problema non è la tecnologia, ma le persone.» | `corretto` → «Il sistema funzionava; il 60% degli operatori non aveva ricevuto la formazione prevista (rapporto interno, p. 14).» |
| Dalla fonte | «L'aumento non dipende dai nuovi iscritti ma dal calo degli abbandoni, come mostra la tabella 3 dello studio.» | `giustificato: contrasto riportato dalla fonte` |

Oltre la soglia del registro (di solito una occorrenza ogni 1.000 parole) ogni occorrenza va motivata. Riducete anche le triadi a effetto («rapido, economico, sbagliato») e le domande retoriche in serie.

### 4.4 Righe isolate a effetto

Chiuse di una o due parole su riga propria.

| Prima | Dopo |
|---|---|
| «…e il consiglio comunale votò contro.<br><br>Punto.» | «…e il consiglio comunale votò contro, 14 a 9.» |
| «Funziona.<br><br>Davvero.» | «Funziona: i test passano su tutte e tre le piattaforme.» |

Ammesse le frasi brevi di ambientazione in apertura («Martedì, ore 7. La stazione è vuota.»). Il linter non distingue i due casi: decide la revisione.

### 4.5 Ricordi inventati

Un modello non inventa ricordi, dialoghi o aneddoti dell'autore. Le scene quotidiane si scrivono come esperimenti mentali, in seconda persona plurale o in forma impersonale. La prima persona singolare è ammessa solo per fatti dell'autore elencati in `author_profile.yaml` o registrati nelle evidenze.

| Prima | Esito | Dopo |
|---|---|---|
| «Ieri al mercato guardo i prezzi e penso all'inflazione.» | `failed` | «Immaginate di confrontare i prezzi al mercato con quelli di un anno fa.» |
| «Quando ho iniziato a programmare, nessuno usava i test.» | `failed` (se non è un fatto dichiarato) | «Fino ai primi anni Duemila, in molti team i test automatici erano l'eccezione (indagine X, 2004).» |
| «Nel mio rapporto del 2012 scrivevo che…» | `ok` se `personal_source` è attivo e il fact-check ha il locator | — |

Spia nei testi promozionali: verbi in prima persona singolare al presente in scene comuni (`guardo`, `conto`, `entro`, `scelgo`). Ogni registro ne elenca altri.

### 4.6 Grassetto sobrio

- Ammesso sulla prima definizione di un concetto e, al massimo, su un dato centrale per sezione.
- Mai su frasi intere (oltre 8 parole) né come decorazione.
- Spia: più di un grassetto ogni 80 parole.
- Nei registri tecnici, comandi e variabili vanno in `codice`, non in grassetto.
- Alcune piattaforme social non rendono il grassetto: lì i marcatori `**` sono un errore.

### 4.7 Attribuzioni puntuali

| Prima | Dopo |
|---|---|
| «Gli esperti concordano che il lavoro da remoto aumenta la produttività.» | «Due studi su call center (Autore A, 2015; Autore B, 2023) arrivano a conclusioni opposte.» |
| «Studi dimostrano che…» | «Una meta-analisi di 42 studi (Autore, anno, tabella 2) stima…» |
| «Secondo indiscrezioni, l'assessore…» | «Secondo due funzionari del Comune che hanno chiesto di non essere nominati…» |

Se non si riesce a dire chi, la frase si toglie. (Nomi, riviste e numeri negli esempi di questa guida sono inventati a scopo illustrativo: in un testo reale ogni riferimento passa dal fact-check.)

### 4.8 Rigore specifico del registro

Ogni registro aggiunge regole proprie (`register_specific`): le condizioni di un modello in saggistica, la riproducibilità del codice nel blog tecnico, il diritto di replica nell'inchiesta, le citazioni testuali nella newsletter. Si verificano a mano e si annotano nella prova testuale.

### 4.9 Voce dell'autore

Il testo rivisto deve suonare come l'autore, non come un modello che ha tolto i propri tic. Se c'è dubbio, confrontatelo con un testo scritto interamente dall'autore sullo stesso tema. Non si aggiungono ironia o colore che l'autore non usa.

## 5. Formule vietate dal manifesto

Oltre al registro, il linter cerca le `deprecated_phrases` di `editorial_manifest.yaml`: promesse assolute («zero allucinazioni», «verificato al 100%»), attribuzioni false («scritto da una persona») e descrizioni distorte della revisione («non rilevabile»). Valgono in bozze, copy e pagine pubbliche.

Un dato riscontrato solo su fonte secondaria non si descrive come «verificato» e non entra nei materiali promozionali.

## 6. Come si registra la revisione

La revisione produce due file nelle evidenze dell'unità:

- `draft-review.json` (F2b) o `social-review.json` (F4), con le sei chiavi CLI e il `digest` del testo rivisto;
- una prova testuale (`evidence_path`) con l'esito di ogni voce, le correzioni fatte e le giustificazioni.

Esempio minimo:

```json
{
  "reviewer": "humanizer (passaggio separato)",
  "register_id": "academic_essay",
  "digest": "<sha256 del testo rivisto>",
  "items": {
    "empty_emphasis": "pass",
    "negative_parallelism": "pass",
    "isolated_lines": "pass",
    "vague_attribution": "pass",
    "decorative_bold": "pass",
    "invented_autobiography": "pass"
  },
  "evidence_path": "evidence/draft-review.md",
  "evidence_sha256": "<sha256 della prova>"
}
```

Il digest include l'identificativo del registro e l'hash dell'elenco di espressioni vietate: cambiare registro o elenco invalida la revisione.

Se il testo cambia dopo la revisione, si rifà la revisione delle parti cambiate e si aggiorna la prova. Ricalcolare solo il digest è un errore: la CLI torna `ready` ma la revisione non copre il testo nuovo.

## 7. Creare o estendere un registro

1. Copiate il registro più vicino in `templates/registers/<nuovo_id>.yaml`.
2. Cambiate `register.id` (uguale al nome del file) e la descrizione.
3. Modificate `forbidden_expressions` e `forbidden_patterns`. Le espressioni si confrontano a confini di parola, senza distinguere maiuscole; i pattern sono espressioni regolari Python applicate con `IGNORECASE`. Ogni voce ha una `suggestion` che indica una direzione di riscrittura.
4. Aggiornate `checklist_mapping` se rinominate le voci; le chiavi CLI restano le sette standard più `evidence_path`.
5. Impostate `[register].active` in `editorial.toml`.

Per poche aggiunte basta `[register].extra_forbidden` in `editorial.toml`, senza creare un registro.

Evitate espressioni troppo brevi o comuni (un falso positivo a ogni revisione insegna a ignorare il linter) ed esempi presi da testi reali di terzi.

## 8. Limiti

La checklist intercetta le forme più riconoscibili, non tutte. Non giudica se un'argomentazione regge, se una generalizzazione è fondata o se un testo è interessante. Non sostituisce il Gate 1: è il materiale che il Direttore legge prima di decidere.
