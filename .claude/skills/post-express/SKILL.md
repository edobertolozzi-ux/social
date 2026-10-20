---
name: post-express
description: Crea e pubblica in pochi minuti un post o una story dell'ultimo minuto partendo da una foto o un video mandati dal telefono. Usala per "post express per il bistrot con questa foto, piatto del giorno", "story veloce: stasera musica dal vivo".
---

# Post express

Edoardo è al telefono e ha fretta: niente domande inutili, una sola conferma prima di pubblicare.

## 1. Il materiale

In ordine di preferenza:
1. Il file allegato alla conversazione, se è disponibile come file nella sessione
2. L'ultimo file nella cartella `express/` del cliente su Drive:
   ```bash
   python3 scripts/media.py elenca --cliente <slug> --cartella express --ultimi 3
   python3 scripts/media.py scarica --cliente <slug> express/<file>
   ```
Se non trovi niente, chiedi a Edoardo di condividere la foto nella cartella `express` del cliente su Drive (dall'app Drive: Condividi → Drive → cartella del cliente → express).

Guarda il file con Read per capire cosa mostra.

## 2. Il contenuto

- Formato: quello che dice Edoardo; se non lo dice, `story` per le cose del giorno, `foto` per il resto.
- Testo: scrivi tu la caption (o i testi della story) seguendo `brand.md`, solo con fatti detti da Edoardo o presenti in `info.md`. Breve.
- File: ritaglio o grafica con `scripts/grafica.py` (story → template `story-annuncio`, formato 9:16).
- Carica il file: `python3 scripts/media.py carica --cliente <slug> --mese AAAA-MM <file>`.

## 3. Conferma

Mostra a Edoardo in un messaggio breve: la caption (o i testi), il link Drive al file (`python3 scripts/media.py link --cliente <slug> <percorso>`), quando uscirebbe. Domanda: "Pubblico adesso o a che ora?"

## 4. Pubblicazione (dopo il suo ok)

Aggiungi il post al piano del mese corrente con stato `approvato` (lo crea se non esiste):
```bash
python3 scripts/piano.py aggiungi clienti/<slug>/piani/AAAA-MM.yaml --da-json '<json del post>'
python3 scripts/scheduler.py programma clienti/<slug>/piani/AAAA-MM.yaml --solo <id> [--subito]
python3 scripts/calendario.py --cliente <slug>
bash scripts/salva.sh "Post express <id>: <slug>"
```
`--subito` pubblica immediatamente; senza, usa data e ora del post.

Rispondi: "Fatto, esce alle HH:MM" (o "Pubblicato" con il link se disponibile).
