# Formato del piano editoriale

Un file per cliente e per mese: `clienti/<slug>/piani/AAAA-MM.yaml`. È la fonte di verità: la pagina calendario, lo scheduler e il report leggono da qui. Controllalo sempre con `python3 scripts/valida_piano.py <file>`.

```yaml
cliente: bistrot-marea          # slug della cartella
mese: "2026-11"
stato_piano: bozza              # bozza | in_revisione | pronto | approvato | programmato
aggiornato: "2026-10-21"

strategia:
  obiettivo_mese: "Riempire i pranzi infrasettimanali e lanciare il menu autunnale"
  pilastri:                     # 3-5 temi ricorrenti del mese
    - nome: "Il piatto"
      perche: "Il cibo è il motivo n.1 per cui ci seguono"
    - nome: "Dietro le quinte"
      perche: "Rende umano il locale"
  ricorrenze:                   # date utili del mese (festività, eventi locali, stagionalità)
    - data: "2026-11-11"
      nome: "San Martino"
      uso: "Post vino novello e castagne"
  note_per_edoardo: "Mancano foto del nuovo dessert: chiedile al cliente entro il 5."

post:
  - id: "2026-11-03-a"          # data + lettera, unico nel mese
    data: "2026-11-03"
    ora: "12:15"                # ora di Roma (fuso in config.yaml)
    canali: [instagram, facebook]
    formato: carosello          # foto | carosello | reel | story
    pilastro: "Il piatto"
    obiettivo: "Prenotazioni pranzo"
    idea: "Tre piatti del nuovo menu autunnale, uno per slide"
    media:
      lavorazione: grafica      # nessuna | grafica | reel_da_foto | montaggio | ai_immagine | ai_video
      sorgente:                 # file su Drive, relativi alla cartella del cliente
        - materiali/2026-10/IMG_2201.jpg
        - materiali/2026-10/IMG_2207.jpg
      template: carosello-slide # solo per lavorazione: grafica
      testi_grafica:            # testi dentro la grafica (pochi e brevi)
        - {titolo: "Menu d'autunno", sottotitolo: "Da martedì a pranzo"}
        - {titolo: "Tagliatelle ai funghi"}
      prompt_ai: ""             # solo per ai_immagine / ai_video
      pronto:                   # file finiti su Drive, compilati dal creativo
        - pronti/2026-11/2026-11-03-a-1.jpg
        - pronti/2026-11/2026-11-03-a-2.jpg
    caption: |
      L'autunno è arrivato anche nel piatto 🍂
      ...
    hashtag: ["#viareggio", "#pranzoviareggio"]
    primo_commento: ""          # opzionale, utile per hashtag extra o link
    alt_text: "Piatto di tagliatelle ai funghi porcini su tavolo in legno"
    stato: bozza                # bozza | da_rivedere | da_correggere | pronto | approvato | programmato | pubblicato | errore | scartato
    revisione:
      esito: ""                 # ok | correggere
      note: ""
    note_edoardo: ""            # richieste di modifica di Edoardo
    scheduler:                  # compilato da scripts/scheduler.py, non toccare a mano
      job_id: ""                # post programmato a una data
      request_id: ""            # post pubblicato subito (--subito)
      programmato_il: ""
      canali_job: []            # canali inviati con l'ultimo invio
      piattaforme: {}           # esito per canale: in coda | pubblicato | errore: motivo
      tentativi: []             # invii precedenti (dopo un 'riprova')
      url: ""
      errore: ""
```

## Regole per formato

| Formato | Media | Caption | Note |
|---|---|---|---|
| `foto` | 1 immagine, 4:5 (1080×1350) consigliato | sì | |
| `carosello` | 2-10 immagini (o video, solo Instagram) | sì | prima slide = gancio |
| `reel` | 1 video verticale 9:16, 5-90 s | sì | primi 2 secondi decisivi |
| `story` | 1 immagine o video 9:16 | no (il testo va dentro la grafica) | |

Limiti utili: caption fino a 2.200 caratteri (meglio 150-600), massimo 30 hashtag su Instagram (noi ne usiamo 3-8), Instagram non rende cliccabili i link nella caption.

## Chi scrive cosa

- `stratega`: `strategia`, e per ogni post `id`, `data`, `ora`, `canali`, `formato`, `pilastro`, `obiettivo`, `idea`, `media.lavorazione`, `media.sorgente`, `media.template`.
- `copywriter`: `caption`, `hashtag`, `primo_commento`, `alt_text`, `media.testi_grafica`, `media.prompt_ai`.
- `creativo`: `media.pronto` (e carica i file su Drive). Porta lo stato a `da_rivedere`.
- `revisore`: `revisione`, stato `pronto` o `da_correggere`.
- Edoardo (tramite te): `note_edoardo`, stato `approvato` o `scartato`.
- `scripts/scheduler.py`: `scheduler`, stato `programmato`, `pubblicato`, `errore`.

`stato_piano` può essere: `bozza`, `in_revisione`, `pronto`, `approvato`, `programmato`.
