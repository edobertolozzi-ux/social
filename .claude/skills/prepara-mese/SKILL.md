---
name: prepara-mese
description: Prepara il piano editoriale completo di un mese per uno o più clienti — strategia, caption, grafiche, video, revisione — e lo lascia pronto per l'approvazione di Edoardo. Usala per "prepara novembre per il bistrot", "prepara il mese prossimo per tutti", o dalla routine del 20 del mese.
---

# Prepara il mese

**Input**: uno o più slug di clienti (oppure "tutti" = clienti con `attivo: true` in `config.yaml`) e il mese `AAAA-MM`. Se il mese non è indicato, è il mese prossimo.

**Risultato**: `clienti/<slug>/piani/AAAA-MM.yaml` con tutti i post in stato `pronto` (o `da_correggere` con note chiare), contenuti finiti su Drive, pagina calendario aggiornata, tutto salvato.

## 0. Controlli iniziali

```bash
python3 scripts/verifica_setup.py --rapido
python3 scripts/piano.py stato-mese --mese AAAA-MM          # quali clienti hanno già un piano e a che punto
```
- Se il piano esiste già ed è oltre `bozza`, non rifarlo: completa solo i post rimasti indietro. In una sessione con Edoardo chiedi prima di sovrascrivere.
- In modalità routine prepara al massimo il numero di clienti indicato dal prompt (per non esaurire i limiti dell'abbonamento), scegliendo quelli senza piano in ordine alfabetico.

## 1. Materiali

```bash
python3 scripts/media.py elenca --cliente <slug> --nuovi
```
Se ci sono file nuovi, delega all'agente `analista-media` la catalogazione prima di pianificare.

## 2. Strategia e scheletro → agente `stratega`

Passa: slug, mese, eventuali indicazioni di Edoardo. Attendi il piano con i post in `bozza`.

## 3. Testi → agente `copywriter`

Passa: slug, percorso del piano, "tutti i post in bozza".

## 4. Contenuti → agente `creativo`

Passa: slug, percorso del piano, mese. Un solo creativo per piano alla volta (modificano lo stesso file). Più clienti possono andare in parallelo, ognuno col suo creativo.

## 5. Revisione → agente `revisore`

Se ci sono post `da_correggere`, rimanda le note al `copywriter` o al `creativo` indicati, poi di nuovo al revisore. **Massimo 2 giri**: quello che resta irrisolto rimane `da_correggere` con la nota per Edoardo.

## 6. Chiusura

```bash
python3 scripts/piano.py imposta clienti/<slug>/piani/AAAA-MM.yaml --piano stato_piano=pronto
python3 scripts/valida_piano.py clienti/<slug>/piani/AAAA-MM.yaml
python3 scripts/calendario.py --cliente <slug>
bash scripts/salva.sh "Piano AAAA-MM pronto: <slug>"
```

## 7. Avviso a Edoardo

- In una sessione con lui: una riga per cliente (post pronti, post da correggere, materiali da chiedere al cliente), più il link `CALENDARIO_URL`.
- In una routine: email con il connettore Gmail a `EMAIL_EDOARDO` (variabile d'ambiente), oggetto "VOLTA · bozze di <mese> pronte", con la stessa sintesi e il link. Se Gmail non è disponibile, scrivi la sintesi in `site/ultimo-avviso.md` e salva.

Mai programmare nulla in questa skill: la programmazione richiede l'approvazione di Edoardo (`/approva-e-programma`).
