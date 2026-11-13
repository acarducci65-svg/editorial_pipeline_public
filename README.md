# Editorial Pipeline

## English

Editorial Pipeline is an early-stage framework for human-governed editorial workflows.
This repository currently contains only a scaffold: editorial processing, fact checking,
and publication are not implemented.

The intended workflow requires two binding human decisions: **Gate 1**, approval of the
draft, and **Gate 2**, approval for publication. Agents cannot grant either approval.

Install Python 3.10 or newer, then run:

```sh
python -m pip install -e ".[dev]"
python -m editorial_pipeline
pytest
```

Optional dependencies can be installed with `.[social]`, `.[audio]`, or `.[all]`.
Playwright browser binaries and external media tools may require separate installation.
See CONTRIBUTING.md and SECURITY.md for project policies. Licensed under Apache 2.0.

## Italiano

Editorial Pipeline ? un framework in fase iniziale per flussi editoriali governati da
persone. Il repository contiene solo lo scheletro: elaborazione editoriale, verifica
dei fatti e pubblicazione non sono ancora implementate.

Il flusso previsto richiede due decisioni umane vincolanti: **Gate 1**, approvazione
della bozza, e **Gate 2**, approvazione della pubblicazione. Gli agenti non possono
rilasciare tali approvazioni.

Con Python 3.10 o successivo, eseguire:

```sh
python -m pip install -e ".[dev]"
python -m editorial_pipeline
pytest
```

Le dipendenze opzionali si installano con `.[social]`, `.[audio]` o `.[all]`.
I browser Playwright e gli strumenti multimediali esterni possono richiedere
un'installazione separata. Vedere CONTRIBUTING.md e SECURITY.md. Licenza Apache 2.0.
