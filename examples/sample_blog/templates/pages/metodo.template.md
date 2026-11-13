---
title: "Il metodo"
description: "Come lavora {{PROJECT_NAME}}: chi fa cosa tra persone e modelli AI, come verifichiamo i fatti, quali limiti dichiariamo."
canonical_path: "/metodo/"
page_kind: "transparency"
template_version: 1
# Fonti dei dati: editorial_manifest.yaml (ruoli, principi, limiti),
# registro attivo in templates/registers/ (checklist), editorial.toml (fasi, gate).
# Le righe che iniziano con <!-- auto: ... --> sono blocchi generati dal renderer.
---

# Il metodo

{{PROJECT_NAME}} è una **redazione aumentata**: una direzione umana che si avvale di modelli di intelligenza artificiale e tiene per sé le decisioni. Questa pagina descrive come nasce ogni {{CONTENT_UNIT}}, chi fa cosa e dove il processo può sbagliare.

Ultimo aggiornamento: {{METHOD_UPDATED_AT}}.

## Chi fa cosa

<!-- auto: manifest.roles -> tabella (Chi | Ruolo | Fasi) -->

| Chi | Ruolo | Fasi |
|---|---|---|
| {{AUTHOR_NAME}} ({{DIRECTOR_ROLE}}) | Sceglie tema, domanda e fonti; dà le indicazioni di stesura; riscrive; approva in esclusiva la bozza e la pubblicazione; risponde di ogni riga. | Ideazione, stesura, Gate 1, Gate 2 |
| {{LLM_DRAFTING_AGENT}} | Prima stesura sulle fonti selezionate, elenco dei claim da verificare, bozze dei testi promozionali. | Stesura, promozione |
| Umanizzatore ({{HUMANIZER_AGENT}}) | Revisione di stile con la checklist pubblica riportata sotto, in un passaggio separato dalla stesura. | Revisione |
| {{RAG_SYSTEM_NAME}} | Verifica dei claim sulle fonti del corpus, con citazione e pagina. | Verifica |
| {{INTEGRATOR_AGENT}} | Coordinamento dei task e verifica formale delle consegne. | Trasversale |

La prima persona degli {{CONTENT_UNIT_PLURAL}} è quella di {{AUTHOR_NAME}}: esperienze, ricordi e opinioni sono suoi. Le parole spesso nascono da un modello, e lo diciamo.

<!-- auto: manifest.independence_disclosures (se presenti) -->

## Il percorso di un {{CONTENT_UNIT}}

<!-- auto: editorial.toml [phases] -> elenco fasi abilitate -->

1. **Scelta e fonti.** {{AUTHOR_NAME}} sceglie il tema e le fonti primarie. Ogni fonte è archiviata con un identificativo e, quando possibile, un'impronta del file.
2. **Prima stesura.** {{LLM_DRAFTING_AGENT}} scrive una bozza sulle fonti e sulle indicazioni ricevute.
3. **Revisione di stile.** L'Umanizzatore applica la checklist pubblica. La revisione viene registrata voce per voce.
4. **Verifica dei fatti.** Ogni affermazione fattuale viene isolata e verificata su {{RAG_SYSTEM_NAME}}. Gli errori intercettati in questa fase finiscono nella sezione A del registro [correzioni](/correzioni/).
5. **Gate 1: approvazione della bozza.** {{AUTHOR_NAME}} legge la bozza, la checklist e l'esito della verifica, e approva o chiede correzioni. Nessun modello può approvare al suo posto.
6. **Promozione.** Solo dopo il Gate 1 si preparano i materiali promozionali{{OPTIONAL_PROMO_ASSETS}}.
7. **Controlli finali.** Test automatici e confronto dei file da pubblicare.
8. **Gate 2: approvazione della pubblicazione.** {{AUTHOR_NAME}} approva testo, data e azioni consentite.

Se una bozza cambia dopo la revisione o la verifica, quei passaggi si rifanno: un'approvazione vale solo per la versione approvata.

## La revisione di stile

<!-- auto: registro attivo -> checklist_mapping (voci 1-9) -->

L'Umanizzatore non serve a rendere il testo "non rilevabile" come testo generato: serve a renderlo leggibile, preciso e onesto. Questa è la checklist che applica, per intero:

1. {{CHECKLIST_ITEM_1}}
2. {{CHECKLIST_ITEM_2}}
3. {{CHECKLIST_ITEM_3}}
4. {{CHECKLIST_ITEM_4}}
5. {{CHECKLIST_ITEM_5}}
6. {{CHECKLIST_ITEM_6}}
7. {{CHECKLIST_ITEM_7}}
8. {{CHECKLIST_ITEM_8}}
9. {{CHECKLIST_ITEM_9}}

Ogni voce si chiude con uno di quattro esiti: *ok*, *corretto*, *giustificato* (con motivo) o *non superato*. Una voce non superata blocca il passaggio alla verifica.

## Come verifichiamo i fatti

Ogni claim riceve uno di questi esiti:

- **Verificato sulla fonte primaria**: la frase corrisponde a quanto scritto nel documento originale (articolo, rapporto, atto), con pagina o sezione.
- **Verificato su fonte esterna**: la fonte primaria è consultabile online; registriamo l'indirizzo e la data di consultazione.
- **Riscontrato solo su fonte secondaria**: la frase corrisponde a una sintesi, non al documento originale. Lo ammettiamo nel corpo del testo, mai nei materiali promozionali.

Un claim **non supportato** o **contraddetto** dalle fonti blocca la bozza: la frase si corregge o si toglie, e si rifanno revisione e verifica.

Numeri e dati usati nei materiali promozionali devono essere verificati sulla fonte primaria o su fonte esterna, con un riferimento preciso.

## Guardrail

> {{GUARDRAIL_STATEMENT}}

È una regola di processo, non una promessa di risultato: ogni affermazione fattuale esce con una fonte controllabile; se la fonte non si trova, la frase si toglie; se un errore sfugge, si corregge in chiaro e con data su [/correzioni/](/correzioni/).

## Limiti dichiarati

<!-- auto: manifest.declared_limits -->

- {{DECLARED_LIMIT_1}}
- {{DECLARED_LIMIT_2}}
- {{DECLARED_LIMIT_3}}

## Strumenti

Il processo è gestito con [Editorial Pipeline](https://github.com/{{FRAMEWORK_REPO}}), un framework open source che verifica le evidenze di ogni fase e si ferma ai due gate umani. Il framework controlla che le prove siano coerenti; non decide se un testo è buono.

Domande sul metodo: {{CONTACT_EMAIL}}.
