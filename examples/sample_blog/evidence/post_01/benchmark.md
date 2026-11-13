# Log di misura simulato (sandbox)

Dati inventati a scopo didattico.

- Interprete: Python 3.12 (portatile di prova, 4 core, SSD)
- Comando: `python -X importtime -c "import mio_script"`
- Ripetizioni: 5, cache del sistema operativo calda

| Ripetizione | Avvio totale (ms) | Libreria grafici, cumulativo (ms) |
|---|---|---|
| 1 | 412 | 270 |
| 2 | 398 | 262 |
| 3 | 405 | 268 |
| 4 | 401 | 266 |
| 5 | 409 | 271 |

Mediana: 405 ms totali, 268 ms per la libreria di grafici (66%).
