#!/usr/bin/env python3
"""Dati e pagine del report mensile.

  report.py raccogli --cliente bistrot --mese 2026-10   → clienti/<slug>/report/2026-10-dati.json
  report.py html     --cliente bistrot --mese 2026-10   → site/<slug>/report-2026-10.html + report/2026-10-email.html

'raccogli' unisce: piano del mese (cosa è uscito, formati, pilastri), metriche dell'account (Upload-Post
/analytics) e metriche dei singoli post (Upload-Post post-analytics). I dati mancanti vengono segnalati,
mai stimati.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os

import markdown
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from comune import (RADICE, SITE, STATI_POST, Errore, a_python, adesso, carica_config, carica_piano, cartella_cliente,
                    esegui_main, info, mese_precedente, nome_mese, percorso_piano, post_numerati, valida_mese)

BASE = os.environ.get("UPLOADPOST_BASE", "https://api.upload-post.com/api")


def _sessione() -> requests.Session:
    s = requests.Session()
    if os.environ.get("UPLOADPOST_API_KEY"):
        s.headers["Authorization"] = f"Apikey {os.environ['UPLOADPOST_API_KEY']}"
    return s


def _get(s, percorso, **params):
    try:
        r = s.get(f"{BASE}/{percorso}", params=params, timeout=90)
    except requests.RequestException as e:
        return None, f"rete: {e.__class__.__name__}"
    if r.status_code >= 400:
        return None, f"HTTP {r.status_code}: {r.text[:200]}"
    try:
        return r.json(), None
    except ValueError:
        return None, "risposta non JSON"


def cmd_raccogli(a):
    mese = valida_mese(a.mese or mese_precedente())
    slug = a.cliente
    cfg = carica_config(slug)
    p_piano = percorso_piano(slug, mese)
    note = []
    dati = {"cliente": slug, "nome": cfg.get("nome"), "mese": mese,
            "generato": adesso().isoformat(timespec="seconds"), "piano": [], "account": {}, "post_metriche": [],
            "note": note}

    piano = carica_piano(p_piano) if p_piano.exists() else {"post": []}
    if not p_piano.exists():
        note.append("nessun piano per il mese")
    dati["obiettivo_mese"] = (piano.get("strategia") or {}).get("obiettivo_mese", "")
    for n, p in post_numerati(piano):
        dati["piano"].append({
            "numero": n, "id": p.get("id"), "data": str(p.get("data")), "ora": p.get("ora"),
            "formato": p.get("formato"), "pilastro": p.get("pilastro"), "obiettivo": p.get("obiettivo"),
            "canali": list(p.get("canali") or []), "stato": p.get("stato"),
            "url": (p.get("scheduler") or {}).get("url", ""),
            "inizio_caption": (p.get("caption") or "").strip().split("\n")[0][:120],
        })

    if os.environ.get("SCHEDULER", "").lower() != "uploadpost":
        note.append("SCHEDULER non impostato: metriche non scaricate (modalità prova)")
    else:
        s = _sessione()
        pub = cfg.get("pubblicazione") or {}
        profilo = pub.get("scheduler_profilo") or slug
        canali = [c for c in ("instagram", "facebook") if (cfg.get("canali") or {}).get(c)]
        giorni = (dt.date.today() - dt.date.fromisoformat(f"{mese}-01")).days + 1
        params = {"platforms": ",".join(canali), "days": min(max(giorni, 1), 365)}
        if "facebook" in canali and pub.get("facebook_page_id"):
            params["page_id"] = pub["facebook_page_id"]
        account, errore = _get(s, f"analytics/{profilo}", **params)
        if errore:
            note.append(f"metriche account non disponibili: {errore}")
        else:
            dati["account"] = account

        # metriche dei singoli post: dalla cronologia di Upload-Post filtrata per external_id del cliente
        pagina, trovati = 1, []
        while pagina <= 10:
            storia, errore = _get(s, "uploadposts/history", page=pagina, limit=100)
            if errore or not storia:
                if errore:
                    note.append(f"cronologia non disponibile: {errore}")
                break
            voci = storia.get("history") or storia.get("uploads") or storia.get("data") or []
            if not voci:
                break
            for v in voci:
                ext = str(v.get("external_id") or "")
                if ext.startswith(f"{slug}/{mese}"):
                    trovati.append(v)
            pagina += 1
        visti = set()
        for v in trovati:
            rid = v.get("request_id") or v.get("job_id")
            if not rid or rid in visti:
                continue
            visti.add(rid)
            metriche, errore = _get(s, f"uploadposts/post-analytics/{rid}")
            dati["post_metriche"].append({"id": str(v.get("external_id", "")).split("/", 1)[-1], "request_id": rid,
                                          "piattaforma": v.get("platform"), "metriche": metriche, "errore": errore})
        if not trovati:
            note.append("nessun post del mese trovato nella cronologia di Upload-Post")

    out = cartella_cliente(slug) / "report" / f"{mese}-dati.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(a_python(dati), ensure_ascii=False, indent=2), encoding="utf-8")
    pubblicati = sum(1 for p in dati["piano"] if p["stato"] == "pubblicato")
    info(f"{out}  ({pubblicati} post pubblicati, {len(dati['post_metriche'])} con metriche, {len(note)} note)")
    for n in note:
        info(f"  nota: {n}")
    return 0


def cmd_html(a):
    mese = valida_mese(a.mese or mese_precedente())
    cfg = carica_config(a.cliente)
    sorgente = cartella_cliente(a.cliente) / "report" / f"{mese}.md"
    if not sorgente.exists():
        raise Errore(f"manca {sorgente}: va scritto dall'agente analista-risultati")
    corpo = markdown.markdown(sorgente.read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
    env = Environment(loader=FileSystemLoader(str(RADICE / "templates" / "sito")), autoescape=select_autoescape(["html"]))
    html = env.get_template("report.html").render(
        stati=STATI_POST, radice="../", aggiornato="aggiornato " + adesso().strftime("%d/%m %H:%M"),
        nome_cliente=cfg.get("nome"), nome_mese=nome_mese(mese), contenuto=corpo)
    pagina = SITE / a.cliente / f"report-{mese}.html"
    pagina.parent.mkdir(parents=True, exist_ok=True)
    pagina.write_text(html, encoding="utf-8")
    # versione per email: HTML semplice con stili in linea
    email = corpo.replace("<table>", '<table style="border-collapse:collapse;width:100%">') \
                 .replace("<th>", '<th style="text-align:left;border-bottom:1px solid #ddd;padding:6px">') \
                 .replace("<td>", '<td style="border-bottom:1px solid #eee;padding:6px">')
    email = f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#222;max-width:640px">{email}</div>'
    p_email = cartella_cliente(a.cliente) / "report" / f"{mese}-email.html"
    p_email.write_text(email, encoding="utf-8")
    info(str(pagina))
    info(str(p_email))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("raccogli"); s.add_argument("--cliente", required=True); s.add_argument("--mese")
    s.set_defaults(f=cmd_raccogli)
    s = sub.add_parser("html"); s.add_argument("--cliente", required=True); s.add_argument("--mese")
    s.set_defaults(f=cmd_html)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
