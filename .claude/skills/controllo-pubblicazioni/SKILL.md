---
name: controllo-pubblicazioni
description: Controlla sullo scheduler cosa è stato pubblicato e cosa è fallito, aggiorna i piani e avvisa Edoardo solo se c'è un problema. Usala per "è uscito tutto?", "controlla le pubblicazioni", o dalla routine serale.
---

# Controllo pubblicazioni

1. Per ogni cliente attivo, sul mese corrente (e sul precedente nei primi 3 giorni del mese):
   ```bash
   python3 scripts/scheduler.py stato clienti/<slug>/piani/AAAA-MM.yaml
   ```
   Aggiorna i post `programmato` a `pubblicato` (con il link) o `errore` (con il motivo).
2. Per ogni `errore` capisci la causa dal messaggio:
   - account scollegato o token scaduto → serve Edoardo: deve ricollegare l'account dal sito dello scheduler
   - formato o file non valido → rifai il file con il `creativo`, mostralo a Edoardo e dopo il suo ok usa `scheduler.py riprova` (invia i file nuovi solo sui canali falliti)
   - limite o errore temporaneo → riprova una volta con `python3 scripts/scheduler.py riprova clienti/<slug>/piani/AAAA-MM.yaml <id> --subito` (rimanda solo sui canali falliti, niente doppioni), solo se la data del post era oggi
3. Salva:
   ```bash
   python3 scripts/calendario.py --senza-anteprime
   bash scripts/salva.sh "Controllo pubblicazioni"
   ```
4. Avviso: se non ci sono errori, nessuna email (in sessione: "Tutto uscito regolarmente"). Se ci sono errori, email a `EMAIL_EDOARDO` con oggetto "VOLTA · post non pubblicati" e, per ogni post: cliente, data, motivo, cosa serve da lui.
