# Attività programmate (routine)

Girano nel cloud di Anthropic anche col computer spento e consumano l'abbonamento Claude come una sessione normale.

## Come crearle (dal telefono o dal computer)

1. Vai su **claude.ai/code/routines** → **New task** → **Set up manually**
2. **Nome** e **prompt**: copia il testo dal file corrispondente qui sotto (solo la parte nel riquadro "Prompt")
3. **Modello**: Sonnet per controllo-pubblicazioni e cataloga-media; Opus (o il migliore disponibile) per prepara-mese e report-mensile
4. **Trigger**: la frequenza indicata nel file. Scegli minuti diversi da :00 (es. 02:07), partono più puntuali
5. **Advanced settings → Repository**: `edobertolozzi-ux/social`; **Cloud environment**: quello configurato in `docs/setup.md`
6. **Connectors**: lascia solo Gmail e Google Drive (togli gli altri: una routine può usare tutto quello che includi)
7. **Create**, poi **Run now** una volta per provarla e leggi il resoconto della sessione

| Routine | Quando | File |
|---|---|---|
| Prepara il mese | ogni giorno alle 02:07 (lavora solo dal 20 al 25) | `prepara-mese.md` |
| Controllo pubblicazioni | ogni giorno alle 21:07 | `controllo-pubblicazioni.md` |
| Cataloga materiali | ogni lunedì alle 03:07 | `cataloga-media.md` |
| Report mensile | ogni giorno alle 04:07 (lavora solo dal 2 al 4) | `report-mensile.md` |

Le routine "ogni giorno ma lavora solo in certi giorni" esistono perché la schermata web offre solo frequenze standard: nei giorni fuori finestra la sessione si chiude subito, quasi senza consumo. Se preferisci, dal terminale con `/schedule update` puoi impostare un cron preciso (es. `7 2 20-25 * *`).
