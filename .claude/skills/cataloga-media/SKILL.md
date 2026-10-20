---
name: cataloga-media
description: Cataloga i nuovi foto e video caricati su Drive per uno o tutti i clienti (tag, qualità, avvisi su liberatorie). Usala per "ci sono foto nuove del bistrot", "cataloga i materiali", o dalla routine settimanale.
---

# Cataloga i materiali

1. Per ogni cliente indicato (o tutti i clienti attivi):
   ```bash
   python3 scripts/media.py elenca --cliente <slug> --nuovi --conta
   ```
2. Per i clienti con file nuovi delega all'agente `analista-media` (clienti diversi possono andare in parallelo: ognuno modifica solo il proprio `media.yaml`).
3. Salva:
   ```bash
   bash scripts/salva.sh "Catalogo media aggiornato"
   ```
4. Rispondi (o, in una routine, includi nell'email a `EMAIL_EDOARDO` solo se c'è qualcosa da segnalare): file nuovi per cliente, i migliori, i file segnalati (liberatorie, minori, diritti), cosa manca per il mese prossimo.
