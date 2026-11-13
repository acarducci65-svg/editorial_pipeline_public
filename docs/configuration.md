# Configurazione di editorial.toml

`editorial.example.toml` ? il modello completo; `examples/sample_blog/editorial.toml` ? una configurazione didattica compilata. `editorial-pipeline init progetto` copia modello e template nel nuovo progetto. Tutti i campi elencati sono obbligatori salvo `gates.gate1.allowed_actions` e `gates.gate2.allowed_actions` (default lista vuota). Le liste possono essere vuote; lo schema non impone in generale vincoli semantici ulteriori ai tipi indicati.

## Riferimento dei campi

| Sezione | Campi e significato |
| --- | --- |
| Radice | `schema_version`: intero, deve essere `1`. |
| `project` | Stringhe `name`, `slug`, `language`, `timezone`, `content_unit`, `content_unit_plural`, `base_url`: identit? e convenzioni del progetto. |
| `paths` | Percorsi relativi `content`, `evidence`, `dist`, `templates`, `pages`, `corrections`, `sources`, `reports`. `content` contiene i post; `evidence` le directory per post; `dist` gli output. |
| `author` | `profile`: percorso relativo del profilo YAML. |
| `manifesto` | `file`: percorso relativo del manifesto YAML. |
| `register` | `active`: identificativo del registro; `directory`: directory relativa dei registri; `extra_forbidden`: lista di espressioni vietate aggiuntive. |
| `phases` | `core`: lista di nomi delle fasi. |
| `phases.optional` | Booleani `F0`, `F1`, `F4_visual`, `F4_video`, `F5`. |
| `phases.disabled_behavior` | `status`: `skipped`, `warning` o `blocked`; `report_in_summary`: booleano. |
| `gates` | `approver_role`: stringa; `receipts_dir`: percorso relativo; `forbidden_excerpts`: lista di stringhe. |
| `gates.gate1`, `gates.gate2` | `name`, `after`, `approval_phrase`, `question`: stringhe; `required` deve essere `true`; `allowed_actions`: lista di stringhe, opzionale. |
| `providers.drafting` | Stringhe `adapter`, `model_label`. |
| `providers.humanizer` | `adapter`: stringa; `separate_pass_required`: booleano. |
| `providers.rag` | `adapter`, `corpus_id_env`: stringhe; `max_claims_per_turn`: intero. |
| `providers.audio`, `providers.visual` | `adapter`: stringa per ciascuna sezione. |
| `factcheck` | Liste di stringhe `allowed_outcomes`, `blocking_outcomes`, `promotion_outcomes`, `circular_source_tags`; booleano `require_locator_for_promotion`. |
| `humanizer` | `required_items`: lista di stringhe; `reviewer_must_differ_from_author`: booleano. |
| `transparency` | Stringhe `method_page`, `corrections_page`, `press_page`; booleani `trailing_slash`, `require_separate_approval`. Sono rotte web, non percorsi filesystem. |
| `transparency.templates` | Percorsi relativi `method`, `corrections`, `press`. |
| `corrections` | Stringhe `pre_publication_id`, `post_publication_id`, `contact_email`; liste `categories_pre`, `categories_post`, `statuses`; booleano `show_reporter_name`. |
| `privacy` | `report_paths` deve essere `relative`; `reject_absolute_paths` deve essere `true`; `deny_patterns` ? una lista di stringhe. |

Le sezioni `[editorial]`, `[de_aizing]`, `[rag]`, `[visual]` e `[channels]` non sono accettate dallo schema attuale: usare rispettivamente le sezioni esistenti per progetto, registro e humanizer, `providers.rag` e `providers.visual`. Non esiste una sezione canali. Le impostazioni dichiarative non implicano che ogni fase o regola sia gi? eseguita dalla CLI: per esempio `verify-facts` usa il provider locale e `build-visual` usa Playwright indipendentemente dai valori `adapter`.

## Percorsi e validazione

`load_config` legge TOML e costruisce `EditorialConfig`: Pydantic v2 rifiuta campi extra e modelli modificabili. I campi percorso non possono essere vuoti, assoluti, dotati di drive o contenere `..`. La CLI usa la cartella del file di configurazione come radice e chiama `resolve_paths`: i percorsi sono normalizzati e i collegamenti simbolici che escono dalla radice sono rifiutati. Il metodo restituisce anche il valore risolto di `register.active`, ma lo style checker usa `register.active` come identificativo e costruisce `directory/<active>.yaml`; usare quindi un nome semplice come `tech_blog`.

La CLI chiama anche `validate_operative`, che cerca ricorsivamente stringhe `{{...}}` nella configurazione e le rifiuta. Non verifica l'esistenza o il contenuto dei file YAML di autore e manifesto, n? garantisce che un valore privo di segnaposto sia realmente pronto alla pubblicazione. I segnaposto a graffa singola usati nelle frasi operative non sono intercettati.

Il modello iniziale contiene segnaposto da compilare prima dell'uso operativo. La sandbox di esempio usa dati fittizi gi? compilati: non esiste un interruttore Pydantic separato per una modalit? sandbox. Le sue evidenze simulate non dimostrano fatti reali.

## Registri e template

I modelli `templates/author_profile.yaml` e `templates/editorial_manifest.yaml` si associano tramite `author.profile` e `manifesto.file`; vanno compilati e revisionati dall'operatore. I registri disponibili in `templates/registers/` sono `academic_essay`, `tech_blog`, `investigative` e `cultural_newsletter`. Copiare il registro nella directory configurata e impostarne l'identificativo in `register.active`; `load_register` richiede che `register.id` coincida con il nome del file senza estensione. `StyleChecker` applica i pattern supportati e `extra_forbidden`; indicazioni descrittive e controlli editoriali non automatizzati restano affidati alla revisione umana. I template delle pagine si collegano tramite `transparency.templates`.
