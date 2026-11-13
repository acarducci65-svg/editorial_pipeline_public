# Guida per il Direttore

Questa guida è per la persona che dirige una redazione aumentata con Editorial Pipeline: chi sceglie i temi, approva le bozze e decide cosa si pubblica. Non serve saper programmare; serve sapere cosa il sistema fa, cosa non fa e cosa vi chiederà.

Nella guida "Direttore" indica un ruolo, non un titolo: può essere un editor, una ricercatrice, il titolare di una newsletter.

## 1. Il patto in breve

Editorial Pipeline coordina agenti AI che scrivono, rivedono e verificano. Tre regole non cambiano mai, qualunque configurazione usiate:

1. **Le decisioni sono vostre.** Tema, fonti, riscrittura, approvazione. Gli agenti propongono.
2. **Due gate umani.** Il Gate 1 (bozza) e il Gate 2 (pubblicazione) si attraversano solo con un vostro messaggio esplicito in chat. Nessun agente può approvare, nemmeno il proprio lavoro, nemmeno "per conto vostro".
3. **Si dichiara chi ha fatto cosa.** Le pagine pubbliche dicono che la prima stesura è di un modello e che voi l'avete rivista e approvata.

Un report della CLI con stato `ready` significa "le evidenze sono coerenti", non "il testo è approvato". Approvare resta compito vostro.

## 2. Primo avvio

### 2.1 Configurazione

1. Copiate `editorial.example.toml` in `editorial.toml` nella radice del vostro progetto.
2. Compilate `[project]`: nome, lingua, fuso orario, come chiamate un'unità di contenuto (articolo, puntata, numero).
3. Scegliete il registro di stile in `[register].active` (vedi §4).
4. Dichiarate i provider in `[providers.*]`: quali modelli e servizi usate davvero. Se un passaggio lo fa una persona o un agente fuori dalla CLI, lasciate `adapter = "manual"`.

Tutti i percorsi sono relativi alla cartella del progetto. Non scrivete identificativi di servizi cloud, token o chiavi nel file: vanno in variabili d'ambiente (es. `EDITORIAL_RAG_ID`).

### 2.2 Profilo autore

Compilate `templates/author_profile.yaml`. È la sola fonte da cui gli agenti possono prendere dati su di voi.

- Scrivete le credenziali **una volta**, nella forma esatta che volete vedere pubblicata (`credentials.display`).
- Elencate in `credentials.forbidden_claims` le formule sbagliate che temete: un titolo di studio che non avete, un incarico che non ricoprite. Il linter le bloccherà.
- Se citerete un vostro lavoro precedente (tesi, rapporto, libro), attivate `personal_source`. Verrà trattato come una fonte qualsiasi, con locator obbligatorio e senza elogi (`anti_flattery_policy`).
- In `first_person.verified_facts` mettete i fatti biografici che gli agenti possono usare in prima persona. Tutto il resto, per un agente, è un ricordo inventato.

Il profilo compilato contiene dati personali: tenetelo nel vostro progetto e decidete voi cosa rendere pubblico.

### 2.3 Manifesto

`templates/editorial_manifest.yaml` descrive la redazione: ruoli, principi, limiti, formule vietate. Compilate i nomi degli strumenti che usate davvero, con il fornitore. Se lo stesso fornitore produce e verifica, o lo stesso modello scrive e rivede, ditelo in `independence_disclosures`.

I principi TP1-TP6 si possono riformulare, non indebolire.

## 3. Il ciclo di un'unità di contenuto

```
F0  Ricerca fonti (opzionale)
F1  Inventario fonti (consigliato)
F2a Prima stesura           ← voi date indicazioni e riscrivete
F2b Revisione di stile
F3  Verifica dei fatti
    ── Gate 1: approvate la bozza ──
F4  Promozione  ‖  F5 Audio (opzionale)
F6  Controlli finali
    ── Gate 2: approvate la pubblicazione ──
```

L'ordine F2a → F2b → F3 → Gate 1 è obbligato. Se il testo cambia dopo F2b o F3, quei passaggi si rifanno: la CLI segna come `stale` tutto ciò che dipendeva dalla versione precedente, compresa un'eventuale approvazione.

### Cosa fate voi, fase per fase

| Fase | Il vostro ruolo |
|---|---|
| F0-F1 | Scegliete tema, domanda e fonti primarie. Controllate che le fonti siano gli originali, non sintesi. |
| F2a | Date indicazioni, leggete la prima stesura, riscrivete quello che non è vostro. |
| F2b | Potete leggere la revisione; non dovete firmarla. |
| F3 | Leggete l'elenco dei claim e il loro esito. |
| Gate 1 | Decidete. |
| F4-F5 | Rivedete i testi promozionali: sono testi nuovi e spesso è lì che compaiono errori. |
| Gate 2 | Decidete testo, data e azioni. |

## 4. Scegliere il registro

Il registro definisce lunghezze, formattazione ammessa e soprattutto l'elenco delle espressioni vietate.

| Registro | Per | Caratteristiche |
|---|---|---|
| `academic_essay` | Saggistica, divulgazione | Niente codice né formule inline; attribuzioni con autore e anno; rigore sulle condizioni dei modelli. |
| `tech_blog` | Post tecnici, tutorial | Codice ammesso (con linguaggio dichiarato); versioni e benchmark riproducibili; niente marketing. |
| `investigative` | Inchiesta | Date complete, tutela delle fonti, diritto di replica, separazione fatti/valutazioni. |
| `cultural_newsletter` | Newsletter di cultura | Prima persona ammessa per opinioni; citazioni testuali verificate; niente superlativi di maniera. |

Potete aggiungere espressioni vietate del vostro progetto in `[register].extra_forbidden` o creare un registro nuovo copiandone uno. La guida all'umanizzazione (`docs/humanizer_guide.md`) spiega il formato.

## 5. I due gate

### 5.1 Cosa vi viene mostrato

**Gate 1** — prima di chiedervi l'approvazione, l'agente deve mostrarvi:

- titolo, sommario e prime righe;
- numero di parole e tempo di lettura;
- esito dei controlli automatici (zero error; i warning con motivazione);
- la checklist di stile con l'esito di ogni voce;
- la tabella dei claim: testo, esito, fonte, pagina, con evidenza di quelli riscontrati solo su fonte secondaria (che non potranno essere usati in promozione);
- gli errori intercettati, con prima e dopo;
- il digest abbreviato della bozza.

**Gate 2** — prima di chiedervi l'approvazione:

- anteprime dei materiali promozionali e i loro testi completi;
- per ogni dato usato in promozione: esito della verifica, fonte, locator;
- data e ora di pubblicazione nel vostro fuso, con l'equivalente UTC;
- esito dei controlli finali;
- elenco dei file che verranno pubblicati o sincronizzati;
- le azioni che state autorizzando (pubblicare, programmare, sincronizzare).

Se manca qualcosa, chiedetelo prima di rispondere.

### 5.2 Come si approva

Scrivete in chat la frase indicata nella domanda, per esempio:

> Approvo Gate 1 #12

oppure indicate le correzioni. La frase rende riconoscibile la ricevuta che l'agente registra subito dopo (`approvals/gate1.json`, con il digest approvato, l'ora e il vostro messaggio parola per parola).

Non valgono come approvazione: notifiche dell'IDE, messaggi di hook, revisioni di un altro agente, un "ok" detto in una sessione precedente su una versione diversa. Se un agente vi dice che qualcosa è "già approvato", chiedete la ricevuta e controllate il digest.

La ricevuta rende verificabile *cosa* avete approvato. Non autentica *chi* l'ha scritto: se altre persone hanno accesso alla vostra chat, tenetelo presente.

### 5.3 Se chiedete correzioni

L'agente torna alla fase indicata. Il digest cambia, quindi tutto ciò che dipendeva dalla versione precedente va rifatto, a partire dalla prima evidenza invalidata.

## 6. Pagine di trasparenza

Tre pagine permanenti accompagnano la pubblicazione:

- **/metodo/** — chi fa cosa, il percorso di un'unità, la checklist di stile, come si verificano i fatti, i limiti;
- **/correzioni/** — registro pubblico, sezione A (errori intercettati prima della pubblicazione) e sezione B (rettifiche);
- **/per-chi-scrive/** — scheda per giornalisti e ricercatori: progetto, autore, come citare, riuso, contatti.

I template sono in `templates/pages/`; come integrarli nel vostro sito è spiegato in `docs/transparency_pages.md`.

Queste pagine non sono contenuti con gate propri: ogni modifica richiede una vostra approvazione esplicita sul testo e sul diff, distinta dai gate delle singole unità.

## 7. Errori e correzioni

- Un errore intercettato in revisione o verifica si registra **prima** di chiedervi il Gate 1, nel file di fact-check. Diventerà una voce della sezione A dopo l'uscita.
- Un errore emerso dopo il Gate 1 (un dato sbagliato in un copy, una frase errata nell'audio) si registra nelle evidenze della fase, non nel fact-check già approvato.
- Un errore scoperto dopo la pubblicazione diventa una voce della sezione B, con data e spiegazione; il testo corretto rimanda alla voce.
- Un limite di verifica (dato riscontrato solo su fonte secondaria) non è un errore fattuale e non va descritto come allucinazione.
- Le voci pubblicate non si cancellano; si modificano solo con una nota datata.

## 8. Formule da non usare

Il manifesto elenca formule che il linter cerca nei testi pubblici. Le più comuni:

| Non scrivete | Perché | Al suo posto |
|---|---|---|
| "zero allucinazioni", "verificato al 100%" | Promessa non verificabile | Descrivete il controllo e rimandate a /metodo/ e /correzioni/ |
| "scritto da una persona" | Falso se la prima stesura è di un modello | "prima stesura di [modello], rivista e approvata da [voi]" |
| "non rilevabile", "sembra umano" | Travisa lo scopo della revisione di stile | "revisione di stile con checklist pubblica" |

## 9. Domande frequenti

**Posso disattivare un gate per andare più veloce?**
No. `required = false` è un errore di validazione. Potete disattivare fasi opzionali (ricerca, audio, video), non i gate.

**Posso usare lo stesso modello per scrivere e rivedere?**
Sì, in passaggi separati e dichiarati. Potete imporre un revisore diverso con `reviewer_must_differ_from_author = true`.

**Il fact-check può essere sbagliato?**
Sì. Il verificatore controlla solo le fonti del corpus e può fraintenderle. Per questo leggete la tabella dei claim al Gate 1 ed esiste il registro correzioni.

**Gli agenti possono pubblicare da soli?**
No. Pubblicazione, programmazione, commit e push richiedono il Gate 2 o una vostra istruzione esplicita.

**Cosa succede se un agente esaurisce la quota a metà?**
Deve chiudere i controlli in corso, scrivere un handover parziale con il punto di ripresa e fermarsi. Nessun lavoro nuovo, nessuna approvazione presunta.
