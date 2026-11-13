# Verifica dei fatti con RAG

In F3 la redazione individua le asserzioni verificabili, consulta fonti indipendenti e registra per ciascuna l'esito e un riferimento preciso. Occorre distinguere una fonte primaria da una secondaria, controllare contesto, data e localizzatore, risolvere contraddizioni e non promuovere affermazioni prive di supporto. La revisione umana valuta anche copertura e affidabilit?: il controllo locale non estrae tutti i claim dalla bozza e non legge o interpreta semanticamente le fonti.

## Porta e adapter

`RagProvider` ? una classe astratta con `capabilities() -> set[str]` e `verify(claims: list[str], evidence_path: Path) -> list[Finding]`. `LocalRagProvider` legge `sources.json` e `factcheck.json` dalla directory di evidenza; funziona offline e riproduce le decisioni registrate, non effettua ricerche o inferenza. Entrambi i file devono contenere liste di oggetti e lo stesso `post_id`.

Per ogni testo richiesto, il provider cerca una sola corrispondenza esatta in `claims`: `verified`, `verified_external` o `grounded_primary`, con `source_key` presente nelle fonti e `locator` non vuoto, producono `OK`; `grounded_secondary` produce `WARN`; assenza, duplicati e altri casi producono `BLOCK`. Per `grounded_secondary` il codice non verifica chiave e locator: il revisore deve comunque esaminarli. I campi configurati in `[factcheck]` non modificano questa logica.

`NotebookLMAdapter` accetta un identificativo fornito a runtime oppure tramite il nome di variabile d'ambiente configurato. Controlla configurazione e disponibilit? di `nlm`, ma anche con entrambi presenti solleva `RagUnavailableError`: la verifica remota non ? implementata. La CLI `verify-facts` seleziona sempre il provider locale, indipendentemente da `providers.rag.adapter`.

## Formato delle evidenze

Esempio minimo compatibile con il provider; i campi descrittivi aiutano la revisione e non sono tutti validati dal motore:

```json
{
  "schema_version": 1,
  "post_id": "post_01",
  "sources": [
    {"key": "fonte-1", "title": "Rapporto di esempio", "type": "report", "primary": true, "local_copy": "evidence/sources/rapporto.txt"}
  ]
}
```

```json
{
  "schema_version": 1,
  "post_id": "post_01",
  "claims": [
    {"id": "C1", "text": "Una misura riportata nel rapporto.", "outcome": "grounded_primary", "source_key": "fonte-1", "locator": "pagina 2, tabella 1"}
  ]
}
```

`key` identifica la fonte, `source_key` la collega al claim e `locator` precisa il punto consultato. La sandbox aggiunge campi come `url`, `accessed`, `tags`, `promotable` e `summary`; citazione, testo estratto, spiegazione e punteggio di confidenza possono essere annotati come metadati supplementari, ma non sono campi obbligatori n? valutati dal codice. Non esiste nello schema implementato una classificazione `VERIFIED`/`CONTRADICTED`/`UNVERIFIABLE` o uno score di confidenza: gli esiti effettivi sono le stringhe minuscole sopra descritte e i finding `OK`/`WARN`/`BLOCK`.

## Uso CLI

Dalla radice del repository, usando la sandbox:

```bash
editorial-pipeline verify-facts post_01_valid --config examples/sample_blog/editorial.toml
editorial-pipeline verify-facts post_01_valid --config examples/sample_blog/editorial.toml --json
editorial-pipeline validate-draft post_01_valid --config examples/sample_blog/editorial.toml
```

Il nome ? cercato in `paths.content`; l'identificativo ricavato determina la directory `paths.evidence/post_01/`. Non esistono le opzioni `--draft` e `--sources`: il post ? posizionale e le fonti si trovano tramite configurazione. `verify-facts` legge i testi dal file di fact-check, richiede almeno un claim, stampa JSON anche senza `--json` e restituisce 1 in caso di `BLOCK` o errore, 0 altrimenti. Un `WARN` non produce da solo un errore. `validate-draft` verifica soltanto la presenza dei due file, non il loro contenuto.
