# Come funziona

```
iPhone / computer ──► Claude Code (sessioni cloud, abbonamento Max)
                         │  CLAUDE.md = capo redazione
                         │  .claude/agents = brand, analista-media, stratega, copywriter, creativo, revisore, analista-risultati
                         │  .claude/skills = comandi (/prepara-mese, /approva-e-programma, /post-express, ...)
                         ▼
                 repository GitHub volta-social  ◄── routine programmate (cloud, anche col computer spento)
                 (testi, piani, catalogo, config)
                         │
        ┌────────────────┼──────────────────────┬──────────────────────┐
        ▼                ▼                      ▼                      ▼
  Google Drive      Upload-Post            OpenRouter            Cloudflare Pages
  foto e video      pubblica IG + FB       immagini/video AI     pagina calendario (site/)
  (rclone)          all'orario giusto      (a consumo, tetti)    privata, si aggiorna da sola
```

## Le scelte e il perché

- **Claude Code come applicazione**: il ragionamento usa l'abbonamento Max invece delle API a pagamento. È consentito perché è uso personale di Claude Code; se un giorno lo strumento diventasse un prodotto da vendere, il cervello va spostato sulle chiavi API (la struttura dei file resta uguale).
- **Tutto in file nel repository**: ogni sessione, dal telefono o da una routine, riparte da zero e legge lo stesso stato. `scripts/salva.sh` fa commit e push su `main` alla fine di ogni lavoro.
- **Upload-Post** invece delle API dirette di Meta: niente App Review, prezzo fisso, supporta post, caroselli, reel e story su Instagram e Facebook, ha analytics via API. Il codice di pubblicazione è tutto in `scripts/scheduler.py`: per cambiare fornitore si riscrive solo la classe `UploadPost`.
- **Drive per i file pesanti**: GitHub non è fatto per foto e video. Nel repository ci sono solo testi, il catalogo e le miniature della pagina calendario.
- **Template HTML per le grafiche** invece di grafiche generate dall'AI: font e colori del brand esatti, testo sempre corretto, costo zero. L'AI generativa resta per sfondi, atmosfere e video, con tetto di spesa.
- **Approvazione umana obbligatoria**: niente viene programmato senza un ok esplicito di Edoardo in chat.

## Il ciclo di un mese

| Quando | Chi | Cosa |
|---|---|---|
| ogni lunedì | routine | cataloga le foto nuove su Drive |
| 20-25 del mese | routine | prepara le bozze del mese dopo (4 clienti per notte), email "bozze pronte" |
| fine mese | Edoardo | pagina calendario → modifiche in chat → "approva e programma" |
| ogni sera | routine | controlla cosa è uscito, email solo se qualcosa è fallito |
| 2-4 del mese | routine | report del mese chiuso, bozze email ai clienti in Gmail |
| quando serve | Edoardo | post express dal telefono |

## Da verificare nella prima settimana di uso reale

1. **Story via Upload-Post** su Instagram e Facebook con un account vero.
2. **Foto allegate alla chat** dalla scheda Code dell'app iPhone: se non arrivano come file nella sessione, il post express usa la cartella `express/` su Drive.
3. **Consumo dell'abbonamento**: dopo il primo mese controlla claude.ai/settings/usage e regola quanti clienti prepara la routine per notte.
4. **Metriche per il report**: la forma esatta delle risposte analytics di Upload-Post; `report.py` salva i dati grezzi e l'agente li interpreta, ma se servono aggiustamenti vanno fatti lì.
