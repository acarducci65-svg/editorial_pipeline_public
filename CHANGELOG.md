# Changelog

Tutte le modifiche rilevanti di Editorial Pipeline sono documentate qui.
Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e le versioni seguono [Semantic Versioning](https://semver.org/lang/it/).

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
