#!/usr/bin/env python3
"""Crea un nuovo cliente dal modello (clienti/_modello) e le sue cartelle su Drive.

Esempio:
  nuovo_cliente.py --nome "La Bolla Hair Spa" --citta "Borgo a Mozzano" --settore beauty \
      --post-settimana 3 --story-settimana 3 --sito https://... --email-report cliente@...
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata

from comune import CLIENTI, Errore, Media, carica_yaml, esegui_main, info, salva_yaml, avviso

CARTELLE_DRIVE = ["materiali", "express", "pronti", "report"]


def slugify(testo: str) -> str:
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:40] or "cliente"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nome", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--citta", default="")
    ap.add_argument("--settore", default="altro")
    ap.add_argument("--post-settimana", type=int, default=3)
    ap.add_argument("--story-settimana", type=int, default=3)
    ap.add_argument("--sito", default="")
    ap.add_argument("--email-report", default="")
    ap.add_argument("--remote", default="drive", help="drive o dropbox")
    ap.add_argument("--cartella-drive", help="default: VOLTA/<nome>")
    ap.add_argument("--senza-drive", action="store_true", help="non creare le cartelle su Drive")
    a = ap.parse_args()

    slug = a.slug or slugify(a.nome)
    dest = CLIENTI / slug
    if dest.exists():
        raise Errore(f"il cliente '{slug}' esiste già")
    shutil.copytree(CLIENTI / "_modello", dest)

    cfg = carica_yaml(dest / "config.yaml")
    cfg["nome"] = a.nome
    cfg["slug"] = slug
    cfg["settore"] = a.settore
    cfg["citta"] = a.citta
    cfg["pubblicazione"]["scheduler_profilo"] = slug
    cfg["frequenza"]["post_settimana"] = a.post_settimana
    cfg["frequenza"]["story_settimana"] = a.story_settimana
    cfg["drive"]["remote"] = a.remote
    cfg["drive"]["cartella"] = a.cartella_drive or f"VOLTA/{a.nome}"
    cfg["approvazione"]["email_report_cliente"] = a.email_report
    salva_yaml(dest / "config.yaml", cfg)

    for nome in ("brand.md", "info.md", "storico.md"):
        p = dest / nome
        p.write_text(p.read_text(encoding="utf-8").replace("Nome Attività", a.nome), encoding="utf-8")
    if a.sito:
        p = dest / "info.md"
        p.write_text(p.read_text(encoding="utf-8").replace("- Sito:", f"- Sito: {a.sito}"), encoding="utf-8")
    info(f"Creato clienti/{slug}/")

    if not a.senza_drive:
        m = Media(slug)
        try:
            for c in CARTELLE_DRIVE:
                m.crea_cartella(c)
            info(f"Cartelle su Drive: {cfg['drive']['remote']}:{cfg['drive']['cartella']}/ ({', '.join(CARTELLE_DRIVE)})")
            if not m.locale and a.remote == "drive":
                r = m._rclone("lsjson", "--stat", "--no-mimetype", m._remoto("materiali"))
                voce = json.loads(r.stdout or "{}")
                if voce.get("ID"):
                    info(f"Cartella da condividere col cliente (per caricare foto e video): "
                         f"https://drive.google.com/drive/folders/{voce['ID']}")
        except Errore as e:
            avviso(f"cartelle Drive non create: {e}")
    info(f"Slug: {slug}")
    return 0


if __name__ == "__main__":
    esegui_main(main)
