#!/usr/bin/env python3
"""Controlla che l'ambiente sia configurato: programmi, librerie, variabili, Drive, scheduler, OpenRouter, GitHub.

  verifica_setup.py            controllo completo (anche le connessioni)
  verifica_setup.py --rapido   solo controlli locali (veloce, per l'inizio di ogni lavoro)
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys

OK, KO, AV = "✓", "✗", "!"
risultati = []


def voce(stato: str, cosa: str, aiuto: str = "") -> None:
    risultati.append(stato)
    print(f"{stato} {cosa}" + (f"\n    → {aiuto}" if aiuto and stato != OK else ""))


def librerie():
    mancanti = []
    for modulo, pip in [("ruamel.yaml", "ruamel.yaml"), ("jinja2", "jinja2"), ("PIL", "pillow"),
                        ("requests", "requests"), ("markdown", "markdown"), ("playwright", "playwright")]:
        try:
            importlib.import_module(modulo)
        except ImportError:
            mancanti.append(pip)
    if mancanti:
        voce(KO, f"librerie Python mancanti: {', '.join(mancanti)}", f"pip install {' '.join(mancanti)}")
    else:
        voce(OK, "librerie Python")
    try:
        importlib.import_module("pillow_heif")
        voce(OK, "supporto foto HEIC (iPhone)")
    except ImportError:
        voce(AV, "supporto foto HEIC assente", "pip install pillow-heif")


def programmi():
    for prog, aiuto in [("ffmpeg", "apt-get install -y ffmpeg"), ("ffprobe", "apt-get install -y ffmpeg"),
                        ("git", "")]:
        voce(OK if shutil.which(prog) else KO, prog, aiuto)
    if shutil.which("rclone"):
        voce(OK, "rclone")
    elif os.environ.get("VOLTA_MEDIA_LOCALE"):
        voce(AV, "rclone assente (uso la cartella locale VOLTA_MEDIA_LOCALE)")
    else:
        voce(KO, "rclone", "apt-get install -y rclone (vedi setup/ambiente-cloud.sh)")


def browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            b.close()
        voce(OK, "browser per le grafiche (Chromium)")
    except Exception as e:
        voce(KO, f"browser per le grafiche non avviabile ({e.__class__.__name__})", "python3 -m playwright install --with-deps chromium")


def variabili():
    for nome, aiuto, obbligatoria in [
        ("SCHEDULER", "imposta SCHEDULER=uploadpost nelle variabili dell'ambiente (senza: modalità prova)", True),
        ("EMAIL_EDOARDO", "indirizzo per gli avvisi delle routine", False),
        ("CALENDARIO_URL", "indirizzo della pagina calendario (Cloudflare Pages)", False),
    ]:
        if os.environ.get(nome):
            voce(OK, f"{nome}={os.environ[nome]}")
        else:
            voce(KO if obbligatoria else AV, f"{nome} non impostata", aiuto)
    if os.environ.get("RCLONE_CONFIG_DRIVE_TYPE") or os.environ.get("VOLTA_MEDIA_LOCALE"):
        voce(OK, "accesso a Drive configurato (variabili rclone)")
    else:
        voce(KO, "accesso a Drive non configurato", "aggiungi RCLONE_CONFIG_DRIVE_TYPE, _SCOPE e _TOKEN (docs/setup.md, passo 4)")


def connessioni():
    import requests
    if shutil.which("rclone") and os.environ.get("RCLONE_CONFIG_DRIVE_TYPE"):
        r = subprocess.run(["rclone", "lsd", "drive:", "--max-depth", "1"], capture_output=True, text=True, timeout=60)
        voce(OK if r.returncode == 0 else KO, "Drive raggiungibile",
             (r.stderr or "").strip().splitlines()[-1] if r.returncode and r.stderr else "")
    if os.environ.get("SCHEDULER", "").lower() == "uploadpost":
        h = {"Authorization": f"Apikey {os.environ['UPLOADPOST_API_KEY']}"} if os.environ.get("UPLOADPOST_API_KEY") else {}
        try:
            r = requests.get("https://api.upload-post.com/api/uploadposts/users", headers=h, timeout=30)
            voce(OK if r.status_code == 200 else KO, f"Upload-Post (HTTP {r.status_code})",
                 "controlla il network secret per api.upload-post.com (header Authorization, prefisso Apikey)")
        except Exception as e:
            voce(KO, f"Upload-Post non raggiungibile ({e.__class__.__name__})", "aggiungi api.upload-post.com ai domini consentiti")
    h = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"} if os.environ.get("OPENROUTER_API_KEY") else {}
    try:
        r = requests.get("https://openrouter.ai/api/v1/key", headers=h, timeout=30)
        voce(OK if r.status_code == 200 else AV, f"OpenRouter (HTTP {r.status_code})",
             "serve solo per immagini e video AI: network secret per openrouter.ai (Bearer)")
    except Exception as e:
        voce(AV, f"OpenRouter non raggiungibile ({e.__class__.__name__})", "aggiungi openrouter.ai ai domini consentiti")
    r = subprocess.run(["git", "ls-remote", "--heads", "origin", "main"], capture_output=True, text=True, timeout=60)
    voce(OK if r.returncode == 0 else AV, "GitHub raggiungibile (per salvare il lavoro)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args()
    programmi()
    librerie()
    variabili()
    if not a.rapido:
        browser()
        connessioni()
    errori = risultati.count(KO)
    print(f"\n{'Tutto pronto.' if not errori else f'{errori} cose da sistemare.'}")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
