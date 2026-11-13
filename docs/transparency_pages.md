# Pagine di trasparenza: specifiche e integrazione

Questo documento definisce le tre pagine permanenti di una redazione aumentata — `/metodo/`, `/correzioni/`, `/per-chi-scrive/` — e spiega come integrarle nei principali generatori di siti statici (SSG) e CMS.

## 1. Requisiti comuni

| Requisito | Dettaglio |
|---|---|
| Route | `/metodo/`, `/correzioni/`, `/per-chi-scrive/`, con barra finale. Configurabili in `editorial.toml` `[transparency]`; il valore di `canonical_path` nel frontmatter deve coincidere con la route effettiva. |
| Navigazione | Link alle tre pagine nell'header o nel footer di **ogni** pagina del sito, comprese le unità di contenuto. |
| Natura | Pagine vive, non unità di contenuto: niente numerazione, feed RSS, gate di unità. |
| Approvazione | Ogni modifica richiede un'approvazione esplicita del Direttore sul testo e sul diff, distinta dai gate (`require_separate_approval = true`). |
| Fonti dei dati | `editorial_manifest.yaml`, `author_profile.yaml`, registro attivo, `editorial.toml`, `corrections.json`. I testi non si riscrivono a mano quando esiste il dato strutturato. |
| Lingua | Le formule vietate di `deprecated_phrases` valgono anche qui. |
| Accessibilità | Tabelle con intestazioni, ancore leggibili, contrasto adeguato; le sezioni vuote mostrano un testo, non spariscono. |

## 2. Specifiche per pagina

### 2.1 `/metodo/`

Template: `templates/pages/metodo.template.md`.

Sezioni obbligatorie, in quest'ordine:

1. **Introduzione** — definizione di redazione aumentata, data di ultimo aggiornamento.
2. **Chi fa cosa** — tabella da `manifest.roles` (Chi, Ruolo, Fasi), più le eventuali `independence_disclosures`.
3. **Il percorso di un'unità** — fasi abilitate in `editorial.toml [phases]`, con i due gate evidenziati.
4. **La revisione di stile** — le nove voci di `checklist_mapping` del registro attivo, testuali. Se la checklist interna e la pagina divergono, prevale la segnalazione al Direttore, non una variante silenziosa.
5. **Come verifichiamo i fatti** — i tre esiti (`grounded_primary`, `verified_external`, `grounded_secondary`) e la regola sulla promozione.
6. **Guardrail** — `manifest.guardrail.statement`, presentato come regola di processo.
7. **Limiti dichiarati** — `manifest.declared_limits`.

### 2.2 `/correzioni/`

Template: `templates/pages/correzioni.template.md`. Dati: `corrections.json`.

Struttura: testo introduttivo (errore fattuale vs limite di verifica, come funziona una rettifica, come segnalare), poi **due sezioni sempre visibili, in quest'ordine**:

- **A — Prima della pubblicazione** (`pre_publication`): errori intercettati in revisione e verifica, ID `ERR-<unità>-<n>`, ordinati per `detected_at` decrescente.
- **B — Dopo la pubblicazione** (`post_publication`): rettifiche, ID `COR-<unità>-<n>`, ordinate per `corrected_at` decrescente.

Schema di `corrections.json`:

```json
{
  "schema_version": 1,
  "pre_publication": [
    {
      "id": "ERR-12-01",
      "unit_slug": "12-esempio",
      "phase": "pre_publication",
      "detected_in": "F3",
      "category": "missing_source",
      "status": "corrected",
      "detected_at": "2026-01-10T14:20:00+01:00",
      "corrected_at": "2026-01-10T15:05:00+01:00",
      "published_at": null,
      "before": "…",
      "after": "…",
      "explanation": "…",
      "source_keys": ["…"],
      "locator": "p. 12"
    }
  ],
  "post_publication": []
}
```

Regole di validazione (il build fallisce se non rispettate):

- `id` unico in tutto il file;
- `phase` coincide con la sezione che contiene la voce;
- `detected_at` e `corrected_at` con offset di fuso esplicito;
- `category` tra quelle dichiarate in `editorial.toml [corrections]`;
- `reporter_name` presente solo se `show_reporter_name = true` e con consenso registrato;
- nessun campo interno nella proiezione pubblica: `draft_ref`, `claim_ids`, percorsi di file, hash.

Regole di pubblicazione:

- una voce della sezione A si pubblica solo dopo l'uscita dell'unità a cui si riferisce;
- le voci pubblicate non si cancellano: le modifiche hanno una nota datata;
- ogni voce ha un'ancora `#<id>`; l'unità corretta dopo l'uscita rimanda a `/correzioni/#COR-…`;
- un limite di verifica si registra come `source_provenance`, non come errore fattuale;
- non si registrano le correzioni di solo stile.

### 2.3 `/per-chi-scrive/`

Template: `templates/pages/per-chi-scrive.template.md`.

Sezioni: progetto in breve, chi c'è dietro (autore e strumenti AI dichiarati), linea editoriale, indipendenza, come citare, dati e fonti, riuso e licenza, materiali, contatti.

I dati dell'autore si copiano alla lettera da `author_profile.yaml` (`display_name`, `bio_long`, `credentials.display`). Contatti: solo indirizzi redazionali pubblici.

## 3. Rendering

Il rendering consiste in tre passaggi, indipendenti dal sito di destinazione:

1. **Sostituzione dei placeholder** `{{NOME}}` con i valori dei file di configurazione. Un placeholder non risolto è un errore.
2. **Espansione dei blocchi automatici** marcati `<!-- auto: ... -->` (tabella ruoli, checklist, voci del registro correzioni).
3. **Scrittura** del Markdown (o HTML) risultante nella cartella del sito.

Il comando previsto dalla CLI (in sviluppo) è:

```bash
editorial-pipeline render-pages --out content/pages
```

Finché il comando non è disponibile, i template si compilano a mano o con uno script, mantenendo i tre passaggi.

## 4. Integrazione per piattaforma

Gli esempi assumono che le pagine generate stiano in una cartella del progetto del sito e che `corrections.json` sia copiato tra i dati del sito.

### 4.1 Hugo

- Pagine: `content/metodo/_index.md`, `content/correzioni/_index.md`, `content/per-chi-scrive/_index.md` (le cartelle producono route con barra finale).
- Dati: `data/corrections.json`, letti nel template come `.Site.Data.corrections`.
- Navigazione: voci `[[menu.main]]` in `hugo.toml`, oppure `menu: main` nel frontmatter.
- Shortcode suggerito `{{</* corrections section="pre_publication" */>}}` che itera le voci e genera l'ancora `id="{{ .id }}"`.

### 4.2 Jekyll

- Pagine: `metodo.md` ecc. con `permalink: /metodo/` nel frontmatter.
- Dati: `_data/corrections.json` → `site.data.corrections.pre_publication`.
- Navigazione: `_data/navigation.yml` incluso nel layout.
- Ordinamento: `{% assign voci = site.data.corrections.pre_publication | sort: "detected_at" | reverse %}`.

### 4.3 Eleventy (11ty)

- Pagine: `src/metodo.md` con `permalink: /metodo/`.
- Dati: `src/_data/corrections.json` → variabile globale `corrections`.
- Navigazione: plugin `@11ty/eleventy-navigation` o un array in `_data/nav.json`.

### 4.4 Astro

- Pagine: `src/pages/metodo.md` (o `.astro`) e `trailingSlash: "always"` in `astro.config.mjs`.
- Dati: `import corrections from "../data/corrections.json"`, oppure una content collection con schema Zod che rispecchi le regole del §2.2.

### 4.5 MkDocs (Material)

- Pagine: `docs/metodo/index.md` ecc., `use_directory_urls: true`.
- Navigazione: sezione `nav:` in `mkdocs.yml`.
- Registro correzioni: generare il Markdown completo nel passaggio di rendering (MkDocs non legge dati JSON nei template senza plugin, es. `mkdocs-macros-plugin`).

### 4.6 WordPress

- Creare tre **pagine** (non articoli) con slug `metodo`, `correzioni`, `per-chi-scrive`; permalink impostati su "Nome articolo" con barra finale.
- Contenuto: incollare l'HTML generato in un blocco HTML personalizzato, oppure importarlo via WP-CLI:
  ```bash
  wp post update <ID> --post_content="$(cat dist/pages/metodo.html)"
  ```
- Registro correzioni: rigenerare e aggiornare la pagina a ogni nuova voce; evitare plugin che modifichino il testo dopo l'approvazione.
- Navigazione: Aspetto → Menu (o editor del sito), voci nell'header e nel footer.

### 4.7 Ghost

- Creare tre **pagine** con gli slug indicati; contenuto via card HTML o Admin API (`PUT /ghost/api/admin/pages/{id}/`, campo `html` con `?source=html`).
- Navigazione: Settings → Navigation (primaria e secondaria).

### 4.8 Newsletter senza sito (Substack, Buttondown, ecc.)

- Pubblicare le tre pagine come pagine statiche della piattaforma, se previste, o come post fissati.
- Inserire nel piè di pagina di ogni numero i link alle tre pagine.
- Il registro correzioni si aggiorna come pagina; un numero corretto dopo l'invio riporta la correzione nel numero successivo con rimando alla voce.

## 5. Verifica prima della pubblicazione

Prima di chiedere l'approvazione del Direttore su una modifica alle pagine:

- [ ] nessun placeholder `{{…}}` residuo;
- [ ] `canonical_path` coincide con la route servita;
- [ ] link alle tre pagine presenti in header o footer di tutte le pagine;
- [ ] `corrections.json` valido secondo §2.2;
- [ ] nessuna voce relativa a unità non ancora pubblicate;
- [ ] nessuna formula di `deprecated_phrases`;
- [ ] dati dell'autore identici a `author_profile.yaml`;
- [ ] diff mostrato al Direttore e approvazione ricevuta in chat.

Dopo la pubblicazione, confrontare byte per byte (o via SHA-256) i file approvati con quelli effettivamente serviti e riportare l'esito nell'handover.
