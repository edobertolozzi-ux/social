---
name: nuovo-cliente
description: Aggiunge un nuovo cliente a VOLTA Social — cartelle, config, cartelle Drive, raccolta info, mood board con l'agente brand, collegamento allo scheduler. Usala per "nuovo cliente", "aggiungi La Bolla", "onboarding di un cliente".
---

# Nuovo cliente

## 1. Le informazioni minime

Chiedi a Edoardo solo quello che non sai già, in un unico messaggio (lui risponde a voce):
- Nome dell'attività, città, settore
- Canali (Instagram, Facebook) e quanti post e story a settimana
- Sito web o link utili; dove stanno foto e video (Drive o Dropbox)
- Email del referente per i report

Poi:
```bash
python3 scripts/nuovo_cliente.py --nome "<Nome>" --citta "<Città>" --settore <settore> \
  --post-settimana 3 --story-settimana 3 [--sito URL] [--email-report EMAIL]
```
Lo script crea `clienti/<slug>/` dal modello, compila `config.yaml` e crea su Drive `VOLTA/<Nome>/` con `materiali/`, `express/`, `pronti/`, `report/`. Stampa lo slug e il link alla cartella Drive da condividere col cliente.

## 2. Le informazioni sul cliente → `info.md`

Compila `clienti/<slug>/info.md` con quello che trovi sul sito (WebFetch) e nei documenti che Edoardo ti passa. Tutto quello che non è certo va in `## Domande aperte`. Mostra a Edoardo le domande aperte in una lista breve: lui le gira al cliente.

## 3. La mood board → agente `brand`

Se ci sono già logo e foto su Drive, prima l'agente `analista-media` cataloga i materiali, poi l'agente `brand` crea `brand.md`, `brand-kit.yaml` e le anteprime. Mostra a Edoardo la sintesi in 3 righe e le anteprime (link Drive o pagina calendario). Le modifiche che chiede vanno nel kit; quando approva, scrivilo in `storico.md` ("AAAA-MM-GG: mood board approvata").

## 4. Collegamento allo scheduler

Edoardo deve farlo una volta dal sito dello scheduler (Upload-Post): creare un profilo con il nome dello slug e collegare Instagram (account Business o Creator) e la Pagina Facebook del cliente. Poi:
```bash
python3 scripts/scheduler.py profili                       # verifica che il profilo esista e cosa è collegato
python3 scripts/scheduler.py pagine-facebook --profilo <slug>
```
Scrivi `pubblicazione.scheduler_profilo` e `pubblicazione.facebook_page_id` in `config.yaml`.

## 5. Chiusura

```bash
python3 scripts/calendario.py
bash scripts/salva.sh "Nuovo cliente: <slug>"
```
Rispondi con: cosa è pronto, cosa manca (domande per il cliente, collegamento account), e il link alla cartella Drive da mandare al cliente per caricare i materiali.
