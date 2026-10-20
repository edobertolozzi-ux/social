---
name: approva-e-programma
description: Applica le decisioni di Edoardo su un piano (approva, scarta, modifica, sposta) e programma i post approvati sullo scheduler. Usala per "approva tutto tranne il 3 e il 7", "sposta il 12 a giovedì", "rifai la caption del 5", "ok programma novembre".
---

# Approva e programma

I post si indicano col **numero** che compare sulla pagina calendario (ordine cronologico nel mese, da 1). Per vedere la corrispondenza numero → id:

```bash
python3 scripts/piano.py elenco clienti/<slug>/piani/AAAA-MM.yaml
```

**Attenzione:** spostare o aggiungere un post cambia la numerazione. Se Edoardo dà più comandi insieme ("sposta il 2 a venerdì e approva il 3"), prima traduci **tutti** i numeri in id con `piano.py elenco`, poi esegui i comandi usando gli id (tutti i comandi accettano anche l'id al posto del numero).

## Interpretare i comandi

| Edoardo dice | Cosa fai |
|---|---|
| "approva tutto" / "ok" riferito al piano | `piano.py approva <piano> --tutti` (solo i post `pronto`) |
| "approva tutto tranne 3 e 7" | `piano.py approva <piano> --tutti --tranne 3 7` |
| "approva 1, 2, 5" | `piano.py approva <piano> 1 2 5` |
| "togli il 9" | `piano.py scarta <piano> 9` |
| "sposta il 12 a giovedì alle 19" | `piano.py sposta <piano> 12 --data AAAA-MM-GG --ora 19:00` (calcola tu la data) |
| "rifai la caption del 5 più ironica" | scrivi la richiesta in `note_edoardo` del post 5, stato `bozza`, delega al `copywriter`, poi al `revisore`; mostra il nuovo testo e chiedi ok |
| "cambia la foto del 4 con una dello staff" | come sopra, ma `stratega` sceglie la foto dal catalogo e `creativo` rifà il file |

Se un comando è ambiguo (quale cliente? quale mese?), chiedi in una riga. Se Edoardo ha già un'opinione chiara, non ridiscuterla.

Quando un post viene modificato su richiesta, dopo la revisione non è approvato automaticamente: mostra la nuova versione (caption e link al file) e chiedi conferma.

## Programmare

Solo dopo l'ok esplicito di Edoardo in questa conversazione.

```bash
python3 scripts/scheduler.py programma clienti/<slug>/piani/AAAA-MM.yaml --prova    # mostra cosa verrebbe programmato
python3 scripts/scheduler.py programma clienti/<slug>/piani/AAAA-MM.yaml            # programma davvero
```

Lo script programma solo i post `approvato` con data futura, scarica i file da Drive, li invia allo scheduler e scrive `job_id` e stato `programmato` nel piano. Un post con data già passata viene saltato e segnalato: proponi a Edoardo una nuova data.

### Modifiche a post già programmati

- Testo o orario: `python3 scripts/scheduler.py aggiorna <piano> <numero> [--caption-dal-piano] [--data ... --ora ...]`
- Cambiare il file o annullare: `python3 scripts/scheduler.py annulla <piano> <numero>` (solo post programmati e non ancora usciti; torna `approvato`), poi riprogramma.
- Post in `errore`: `python3 scripts/scheduler.py riprova <piano> <numero> [--subito]` rimanda il post solo sui canali dove non è uscito.

Un post che contiene ancora `[DA VERIFICARE]` non si può approvare né programmare: prima va completato il dato mancante.

## Chiusura

```bash
python3 scripts/calendario.py --cliente <slug>
bash scripts/salva.sh "Approvati e programmati post di AAAA-MM: <slug>"
```

Rispondi in una riga: quanti programmati, primo e ultimo, eventuali saltati e perché.
