# VOLTA Social

Il social media manager automatico di VOLTA: un gruppo di agenti AI dentro Claude Code che raccoglie i materiali dei clienti, li analizza, prepara il piano editoriale del mese con copy, grafiche e video, li fa revisionare e, dopo l'ok di Edoardo, li programma su Instagram e Facebook. Obiettivo: **al massimo 3 ore al mese per cliente**, tutto gestibile dall'iPhone.

## Come si usa (dal telefono)

App Claude → scheda **Code** → sessione sul repository `social`. Poi si parla normalmente, anche a voce:

| Scrivi o detta | Succede |
|---|---|
| "nuovo cliente: La Bolla Hair Spa, Borgo a Mozzano, beauty, 3 post a settimana" | crea cliente, cartelle Drive, mood board |
| "ci sono foto nuove della Bolla, catalogale" | l'analista tagga e valuta i materiali |
| "prepara dicembre per la Bolla" | strategia, caption, grafiche, reel, revisione: piano pronto da approvare |
| "com'è messo dicembre?" | riepilogo + link alla pagina calendario |
| "approva tutto tranne il 3 e il 7" / "sposta il 12 a giovedì alle 19" | aggiorna il piano |
| "rifai la caption del 5 più ironica" | copywriter → revisore → te la mostra |
| "ok programma dicembre" | i post approvati vanno sullo scheduler |
| "post express per la Bolla con questa foto: oggi promo piega a 25€" | post pronto e programmato in pochi minuti |
| "è uscito tutto ieri?" | controllo pubblicazioni |
| "fai il report di novembre" | report per il cliente + bozza email in Gmail |

Il resto lo fanno le **routine** da sole (bozze del mese il 20-25, controllo serale, catalogo settimanale, report il 2 del mese): vedi `routines/`.

## Cosa c'è dentro

```
CLAUDE.md                 istruzioni del capo redazione (letto da Claude a ogni sessione)
.claude/agents/           i 7 agenti specializzati
.claude/skills/           i comandi (prepara-mese, approva-e-programma, post-express, ...)
clienti/<slug>/           tutto su un cliente: config, mood board, info, storico, catalogo, piani, report
clienti/_modello/         modello per i nuovi clienti
clienti/esempio-bistrot/  cliente inventato per provare (si può cancellare)
templates/grafiche/       template delle grafiche (post, promo, citazione, carosello, story, chiusura reel)
templates/sito/           template della pagina calendario
scripts/                  gli strumenti (Python): media, grafiche, video, AI, scheduler, calendario, report
site/                     pagina calendario generata (pubblicata da Cloudflare Pages)
routines/                 i prompt delle attività programmate
setup/                    script di installazione dell'ambiente cloud
docs/                     configurazione, architettura, formato del piano
```

## Per iniziare

Segui **`docs/setup.md`** (circa un'ora, una volta sola). Poi `routines/README.md`.

## Costi di funzionamento

| Voce | Costo mensile |
|---|---|
| Claude (ragionamento, agenti, routine) | incluso nell'abbonamento Max |
| Upload-Post | 19 € (fino a 5 clienti), poi 50 $, o 33 $ con pagamento annuale (fino a 25) |
| OpenRouter (immagini e video AI) | a consumo, con tetto per cliente in `config.yaml` (default 5 €) |
| Google Drive, GitHub, Cloudflare Pages | gratis |

Un video AI di 5 secondi costa circa 0,60 €; una grafica da template, un reel da foto o un montaggio costano zero.

## Regole di sicurezza

- Niente viene programmato senza approvazione esplicita di Edoardo.
- Gli agenti non inventano prezzi, orari o promozioni: solo quello che c'è in `info.md`.
- Spesa AI con tetto mensile per cliente; chiavi API come network secret, mai nei file.
- Persone non autorizzate e minori nelle foto vengono segnalati e non usati.

Dettagli tecnici e scelte: `docs/architettura.md`.
