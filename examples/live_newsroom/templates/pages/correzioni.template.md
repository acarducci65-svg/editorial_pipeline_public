---
title: "Correzioni"
description: "Registro pubblico degli errori di {{PROJECT_NAME}}: quelli intercettati prima della pubblicazione e le rettifiche successive."
canonical_path: "/correzioni/"
page_kind: "transparency"
template_version: 1
# Dati: file indicato in editorial.toml [paths].corrections (corrections.json).
# Le due sezioni vengono sempre mostrate, anche se vuote, in quest'ordine: A, B.
---

# Correzioni

Su {{PROJECT_NAME}} ogni fatto ha una fonte e ogni errore ha una data. Questa pagina raccoglie entrambi i tipi di errore: quelli che il processo ha intercettato prima della pubblicazione e quelli sfuggiti, corretti dopo.

Le voci non si cancellano. Se una voce pubblicata viene modificata, la modifica è indicata con una nota datata.

## Errore fattuale o limite di verifica?

Non tutto ciò che registriamo è un errore dimostrato.

- Un **errore fattuale** è un'affermazione smentita dalla fonte: un numero sbagliato, un autore o un anno errati, una conclusione più forte di quella del documento.
- Un **limite di verifica** è un'affermazione che abbiamo potuto riscontrare solo su una fonte secondaria. Non sappiamo che sia falsa; sappiamo che non l'abbiamo verificata sull'originale. Lo registriamo come tale.

## Come funziona una rettifica

1. Riceviamo una segnalazione o troviamo l'errore durante una rilettura.
2. Ricontrolliamo la frase sulla fonte primaria.
3. Se l'errore è confermato, correggiamo il testo e aggiungiamo una voce alla sezione B con il testo prima e dopo, la data e la spiegazione.
4. L'{{CONTENT_UNIT}} corretto rimanda alla voce del registro.

Il nome di chi segnala compare solo con il suo consenso esplicito.

## Segnalare un errore

Scrivete a {{CORRECTIONS_CONTACT_EMAIL}} indicando l'indirizzo della pagina, la frase e, se possibile, la fonte. {{RESPONSE_POLICY}}

---

## A — Prima della pubblicazione

Errori intercettati durante la revisione e la verifica dei fatti, corretti prima che l'{{CONTENT_UNIT}} uscisse. Li pubblichiamo perché mostrano dove il processo ha lavorato e dove i modelli sbagliano. Una voce compare solo dopo l'uscita dell'{{CONTENT_UNIT}} a cui si riferisce.

<!-- auto: corrections.pre_publication, ordinate per detected_at decrescente -->
<!-- se vuota: "Nessun errore intercettato finora." -->

<!-- Formato di ciascuna voce (generato dal renderer):

### ERR-{{UNIT_ID}}-{{SEQ}} {#ERR-{{UNIT_ID}}-{{SEQ}}}

- **{{CONTENT_UNIT}}**: [{{UNIT_TITLE}}]({{UNIT_URL}})
- **Rilevato**: {{DETECTED_AT}} durante {{DETECTED_IN_LABEL}}
- **Categoria**: {{CATEGORY_LABEL}}
- **Prima**: «{{BEFORE}}»
- **Dopo**: «{{AFTER}}»  (oppure: frase rimossa)
- **Spiegazione**: {{EXPLANATION}}
- **Fonte**: {{SOURCE_LABEL}}, {{LOCATOR}}
-->

Categorie della sezione A:

| Categoria | Significato |
|---|---|
| Dato senza fonte | Un'affermazione plausibile che nessuna fonte del corpus sostiene. |
| Verifica solo di seconda mano | Riscontro trovato solo su una sintesi, non sull'originale (limite di verifica). |
| Affermazione più forte della fonte | Il testo generalizza o conclude più di quanto dica il documento. |
| Errore numerico | Aritmetica sbagliata o esempio numerico incoerente. |
| Attribuzione | Autore, anno, rivista o istituzione errati. |
| Audio | Frase errata nella versione audio, con minutaggio. |

## B — Dopo la pubblicazione

Rettifiche di errori sfuggiti al processo e segnalati o scoperti dopo l'uscita.

<!-- auto: corrections.post_publication, ordinate per corrected_at decrescente -->
<!-- se vuota: "Nessuna rettifica registrata." -->

<!-- Formato di ciascuna voce (generato dal renderer):

### COR-{{UNIT_ID}}-{{SEQ}} {#COR-{{UNIT_ID}}-{{SEQ}}}

- **{{CONTENT_UNIT}}**: [{{UNIT_TITLE}}]({{UNIT_URL}})
- **Rilevato**: {{DETECTED_AT}} · **Corretto**: {{CORRECTED_AT}}
- **Categoria**: {{CATEGORY_LABEL}} · **Esito**: {{STATUS_LABEL}}
- **Prima**: «{{BEFORE}}»
- **Dopo**: «{{AFTER}}»
- **Spiegazione**: {{EXPLANATION}}
- **Segnalato da**: {{REPORTER_NAME}}  (solo con consenso)
-->

Categorie della sezione B: errore fattuale, errore di calcolo, attribuzione errata, chiarimento su un'ambiguità. Esiti: corretto, chiarito, ritirato.
