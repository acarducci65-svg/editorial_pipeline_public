# Changelog

Tutte le modifiche rilevanti di Editorial Pipeline sono documentate qui.
Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e le versioni seguono [Semantic Versioning](https://semver.org/lang/it/).

## [1.2.5] - 2026-11-16

### Added

- Export `publish --target static_site`: se la bozza non ha già un titolo
  `## Fonti` o `### Fonti`, la copia esportata riceve una sezione `## Fonti`
  generata da `[paths].evidence/<post_id>/sources.json`, con un punto
  `- [Titolo](link) — Autori/Istituzione (Anno)` per fonte. Il link è il primo
  URL `http(s)` fra `url`, `pdf` e `open_access_url`, altrimenti
  `https://doi.org/<doi>`. Campi interni come `local_copy`, `consulted_sha256` e
  `notes` non vengono mai pubblicati, e la bozza in `content/` resta intatta (T-097).
- `PlaywrightVisualBuilder` prova in ordine Chromium di Playwright, Google Chrome
  di sistema (`channel="chrome"`) e Microsoft Edge di sistema (`channel="msedge"`)
  prima di ripiegare sul solo HTML, così PNG e PDF del carosello si generano anche
  senza `playwright install chromium` (T-099).

### Changed

- Regole `--focus` dell'audio NotebookLM più strette: definizioni rispettate
  anche nel riepilogo finale, nessuna estensione del risultato di una coorte a
  tutta la forza lavoro, nessuna correlazione presentata come causa, unità e
  scale dei numeri pronunciate con esattezza.

### Documentation

- Skill F5: i finding della revisione audio si classificano per materialità.
  Sono P1 bloccanti numeri, date o scale inventati o alterati, fatti contraddetti
  da claim o fonti, inversioni concettuali gravi e tono enfatico; le frasi di
  raccordo del dialogo naturale senza `claim_id` restano al più note P3 (T-093).
- Skill F5: dopo un `--new` autorizzato, gli episodi superati vanno rimossi dallo
  Studio (a mano o con `nlm studio delete` dopo conferma esplicita) finché resta
  un solo artefatto audio attivo (T-094).
- Skill: `editorial-pipeline view <post_id> --no-browser` obbligatorio dopo il
  Gate 2 e dopo l'ultimo `publish`, per mostrare in console il badge Gate 2 e lo
  stato pubblicato (T-095).
- Skill F4: testi social e slide del carosello sono puliti, senza `claim_id`,
  tag interni o note redazionali; il tracciamento va in
  `evidence/<post_id>/social-review.md`. Struttura per canale e URL reale
  dell'articolo obbligatori (T-096).
- Skill: sezione `## Fonti` automatica dell'export `static_site` documentata, con
  le istruzioni per l'agente e l'avviso sui titoli `## Sources` in inglese (T-098).
- Skill F4: un carosello è completo solo con tutti i `slide_NN.png` e il
  `<post_id>_carousel.pdf` su disco e `artifact_type = "carousel"` nel manifest.
  Documentati l'ordine di fallback dei browser e la procedura per slide HTML
  modificate a mano (T-100).
- README e manuale utente allineati alla versione 1.2.5.

## [1.2.0] - 2026-11-16

### Added

- Flag `--new` per `editorial build-audio --provider notebooklm`: salta la
  ricognizione dello Studio e avvia una nuova Audio Overview anche se nel
  taccuino esiste già un artefatto `completed`, `in_progress` o `queued`.
  Con un provider diverso da `notebooklm` la CLI rifiuta il flag (T-088).
- Layout `static_site_layout = "hugo_bundle"` (`<post_id>/index.md` con i media
  accanto), export degli asset audio approvati con l'azione `static_site` o
  `publish_audio` e ripubblicazione con `[publishing].allow_overwrite = true`.
- Interruzione immediata di `verify-facts` con `provider = "notebooklm"` quando
  NotebookLM segnala un limite di utilizzo o di frequenza
  (`NotebookLM RAG: usage limit reached …`), senza ulteriori interrogazioni (T-086).
- Applicazione di `[providers.rag].max_claims_per_turn` (default `8`) anche nella
  CLI: oltre il tetto `verify-facts` non lancia interrogazioni remote.
- Opzioni `--length {short,default,long}` e
  `--overview-format {deep_dive,brief,critique,debate}` per `editorial build-audio`
  e chiavi `[audio].length` / `[audio].overview_format` (precedenza: CLI >
  `[audio]` > default), passate a `nlm audio create` come `--length` e `--format` (T-091).

### Changed

- `build-audio` con NotebookLM genera per default puntate brevi (`length = "short"`,
  `overview_format = "deep_dive"`) e apre il `--focus` con regole editoriali
  vincolanti per i conduttori: registro sobrio, niente enfasi, frasi fatte,
  metafore o esempi numerici inventati, rispetto di definizioni e orizzonti
  temporali, perimetro chiuso sui claim verificati, più le voci di
  `[register].extra_forbidden` (T-091).

- Polling dell'audio NotebookLM esteso a 10 minuti (120 controlli ogni 5 s) e
  riuso degli artefatti audio già presenti nello Studio, completati o in corso,
  senza generazioni duplicate (T-082).
- `nlm query notebook` viene invocato con `--new-conversation` per citazioni
  deterministiche e indipendenti dalle interrogazioni precedenti (T-006).

### Fixed

- L'export `static_site` esclude gli artefatti `.html` e `.css` (slide HTML,
  console web), che Hugo tratterebbe come pagine da renderizzare (T-080).
- Il loader di `editorial.toml` tollera il BOM UTF-8 aggiunto da alcuni editor
  su Windows (T-085).
- La console `editorial view` trova le bozze anche in sottocartelle annidate di
  `content/`: `web_hub.discover_post_ids` cerca i post in modo ricorsivo.
- Import circolare nell'adapter audio NotebookLM.

### Documentation

- Skill `editorial-pipeline`: architettura NotebookLM a due livelli. Il
  **Taccuino Maestro** (archivio di fonti storiche e articoli pubblicati) serve
  la ricerca trasversale in F0/F1 e si aggiorna in F6; il **Micro-Taccuino
  d'Articolo** `<slug>-<post_id>`, creato in automatico a fine F1 dopo la
  conferma delle fonti (`notebook_create`, `nlm alias set`, `source_add` delle
  sole fonti di `sources.json`, `EDITORIAL_RAG_ID`/`EDITORIAL_AUDIO_ID`), è lo
  standard per il fact-checking F3 e l'audio F5. Documentato l'uso di `--new` (T-089).
- Divieto di rilanci ripetuti di `verify-facts` dopo errori remoti di NotebookLM:
  una sola esecuzione remota per turno (T-087).
- Divieto di ripiego autonomo su `script_only` dopo l'avvio di una generazione
  NotebookLM e obbligo di verificare il file audio su disco prima della
  console (T-083).
- Guida allo scaffolding del sito Hugo che riceve `publish` (T-081) e al deploy
  con Docker/Coolify, con regola UTF-8 senza BOM e date localizzate (T-084).
- Linee guida contro l'iper-frammentazione dei claim in F3.
- Skill: `editorial view` obbligatorio prima del pacchetto Gate 1, per mostrare
  al Direttore bozza, fonti e claim nella console (T-090).
- Skill: `--length short`, `--overview-format` e regole anti-enfasi del `--focus`
  documentati in F5; il controllo pre-Gate 2 dell'audio include la checklist
  anti-cliché e la ricerca di estrapolazioni, esempi inventati e confusioni
  concettuali, da riferire come finding P1; `--new` solo su autorizzazione del
  Direttore (T-092).
- README e manuale utente allineati alla versione 1.2.0.

## [1.1.0] - 2026-11-15

### Added

- Comando `editorial view` con console offline a 6 schede per articolo,
  indice newsroom `index.html` e server loopback `--serve` con whitelist
  di sicurezza.
- Adapter `author_website` per la pubblicazione di pagine long-form standalone
  per blog o sito personale dell'autore (`dist/author_site/<post_id>/index.html`),
  con player podcast e carosello integrati.
- Configurazione `[theme]` con palette accessibili WCAG AA (`cobalt_tech`,
  `emerald`, `nordic_minimal`, `custom`), colori esadecimali e `font_family`.

### Changed

- Slide del carosello allineate al tema Cobalt Tech con dati post-Gate 2.
- Skill `editorial-pipeline` aggiornata con intervista preliminare su testata,
  autore e tema, e supporto a `view` e `author_website`.

## [0.2.0] - 2026-11-14

### Changed — Breaking / Architectural

- NotebookLM Studio diventa il motore esclusivo per i podcast editoriali F5
  a due voci: usare `editorial build-audio --provider notebooklm`.
  I workflow che producevano podcast con TTS locale devono migrare a NotebookLM;
  `script_only` rimane disponibile per preparare il copione senza generare audio.

### Deprecated

- Il provider TTS locale mono-voce è deprecato per qualità inadeguata allo
  standard giornalistico del progetto. È ancora selezionabile per compatibilità,
  ma emette un `DeprecationWarning` e un avviso nella CLI; non è ammesso nel
  pacchetto podcast editoriale e non viene usato come fallback automatico.

### Added

- Supporto dei formati audio `.m4a` (AAC nativo di NotebookLM, predefinito) e
  `.mp3` tramite `--format`, con selezione della lingua tramite `--language`.
  La selezione `.mp3` imposta il nome di destinazione: l'adapter non esegue
  transcodifica e il contenitore effettivo dipende dall'output di `nlm`.
- Motore di pubblicazione `editorial publish` per Hugo/Jekyll, Ghost, Medium
  e Substack, con export per blog/newsletter e manifesto del bundle.
  La pubblicazione resta subordinata al Gate 2 umano vincolante.
- Comando `install-skill` con mapping automatico della skill e risorse incluse
  nel pacchetto distribuibile.

### Fixed

- Resilienza delle citazioni RAG in `NotebookLMAdapter` per `nlm >= 0.15`,
  con risoluzione del dizionario delle note verso gli ID delle fonti.

### Documentation

- Revisione integrale di `skills/editorial-pipeline/SKILL.md`,
  `skills/editorial-pipeline/references/publishing-and-audio.md` e
  `docs/audio_production.md` per lo standard audio NotebookLM, i comandi
  aggiornati e le procedure di verifica umana.
- Manuale utente `docs/manuale_configurazione_e_uso.md` aggiornato alla versione
  1.3.0, con riferimento al software 0.2.0.

## [0.1.0] - 2026-11-14

### Added

- Release iniziale del framework editoriale a sei fasi, con libreria Python,
  CLI e skill per agenti AI.
- Doppio gate umano vincolante per approvazione della bozza e pubblicazione.
- Revisione de-aizing, fact-checking grounded su fonti tramite RAG,
  caroselli visivi e report bundle per la verifica dei contenuti.
