---
id: "post_01"
title: "Misurare il tempo di import di uno script Python"
author: "Ada Esempio"
register: "tech_blog"
status: "draft"
date: "2026-11-10"
evidence: "evidence/post_01"
sandbox: true
---

# Misurare il tempo di import di uno script Python

Uno script da riga di comando che impiega un secondo ad avviarsi è spesso lento prima ancora di eseguire la prima istruzione utile: il tempo se ne va negli import. Python offre un'opzione dell'interprete per vedere dove, modulo per modulo.

## Il comando

Dalla versione 3.7 l'interprete accetta l'opzione `-X importtime` [1]. Il resoconto esce su standard error, quindi conviene redirigerlo su un file:

```bash
python -X importtime -c "import mio_script" 2> import.log
```

Ogni riga del file riporta tre colonne: il tempo speso nel modulo stesso, il tempo cumulativo che include i suoi import, il nome del modulo. I tempi sono in microsecondi.

## Leggere il resoconto

Il modo più rapido per trovare i colpevoli è ordinare per tempo cumulativo:

```bash
sort -t "|" -k 2 -n import.log | tail -n 15
```

Nella sandbox di questo blog abbiamo misurato uno script di prova su un portatile con Python 3.12: la libreria di grafici importata in testa al file pesava da sola circa due terzi dell'avvio. I numeri esatti, l'hardware e le cinque ripetizioni sono nelle evidenze del post.

## Spostare gli import pesanti

Una libreria usata da un solo sottocomando non ha bisogno di essere caricata a ogni avvio. Si può importarla dentro la funzione che la usa:

```python
def esporta_grafico(dati):
    import matplotlib.pyplot as plt

    plt.plot(dati)
    plt.savefig("grafico.png")
```

Il costo si paga solo quando quel sottocomando viene eseguito. Lo svantaggio è che un errore di import emerge più tardi, al primo uso: un test che esercita ogni sottocomando lo intercetta prima del rilascio.

## Cosa resta da verificare

Il guadagno dipende dal disco, dalla cache del sistema operativo e dalla versione dell'interprete. Prima di cambiare il codice conviene ripetere la misura almeno tre volte e confrontare le mediane, non il singolo valore migliore.

## Fonti

1. Documentazione di Python, «Command line and environment», voce `-X importtime` (consultata il 2026-11-10).
