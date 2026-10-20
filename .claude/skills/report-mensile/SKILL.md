---
name: report-mensile
description: Prepara il report del mese chiuso per uno o tutti i clienti, aggiorna lo storico e crea la bozza email per il cliente. Usala per "fai il report di ottobre", o dalla routine del 2 del mese.
---

# Report mensile

**Mese**: quello indicato, altrimenti il mese appena chiuso.

1. Prima aggiorna gli stati dei post del mese:
   ```bash
   python3 scripts/scheduler.py stato clienti/<slug>/piani/AAAA-MM.yaml
   ```
2. Delega all'agente `analista-risultati` (un agente per cliente, in parallelo). Produce `report/AAAA-MM.md`, `report/AAAA-MM-interno.md`, la versione HTML, e aggiorna `storico.md`.
3. Bozza email per il cliente con il connettore Gmail (**bozza, mai invio**): destinatario `approvazione.email_report_cliente` di `config.yaml`, oggetto "Il tuo mese social: <mese>", corpo = il contenuto di `clienti/<slug>/report/AAAA-MM-email.html` (versione per email creata da `report.py html`). Se l'email del cliente manca, salta e segnalalo.
4. Salva:
   ```bash
   python3 scripts/calendario.py
   bash scripts/salva.sh "Report AAAA-MM"
   ```
5. Avviso a Edoardo (in routine: email a `EMAIL_EDOARDO`): per ogni cliente la sintesi in 3 righe, le raccomandazioni principali e "bozza email pronta in Gmail".
