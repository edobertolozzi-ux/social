---
name: calendario
description: Rigenera la pagina calendario (vista mensile con anteprime, caption e stato di ogni post) e la pubblica. Usala per "aggiorna il calendario", "fammi vedere novembre", o dopo ogni modifica ai piani.
---

# Calendario

```bash
python3 scripts/calendario.py                    # tutti i clienti
python3 scripts/calendario.py --cliente <slug>   # un cliente
python3 scripts/calendario.py --senza-anteprime  # più veloce, senza scaricare i file da Drive
bash scripts/salva.sh "Calendario aggiornato"
```

La pagina si pubblica da sola dopo il salvataggio (Cloudflare Pages legge la cartella `site/`). Il link è nella variabile `CALENDARIO_URL`: rispondi con il link diretto al mese, `CALENDARIO_URL/<slug>/AAAA-MM.html`.

Se Edoardo chiede "com'è messo novembre?" senza voler vedere la pagina, rispondi con il riepilogo testuale:
```bash
python3 scripts/piano.py elenco clienti/<slug>/piani/AAAA-MM.yaml --breve
```
