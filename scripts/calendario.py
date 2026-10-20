#!/usr/bin/env python3
"""Genera la pagina calendario in site/ (indice clienti + una pagina per ogni mese con anteprime e testi).

Uso:
  calendario.py                     tutti i clienti
  calendario.py --cliente bistrot   un cliente (l'indice si aggiorna sempre)
  calendario.py --senza-anteprime   non scarica i file da Drive (usa solo le miniature già presenti)
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from comune import (CLIENTI, GIORNI, GIORNI_BREVI, RADICE, SITE, STATI_POST, Errore, Media, adesso, avviso,
                    carica_config, carica_piano, crea_anteprima, e_video, elenco_slug, esegui_main, info,
                    nome_mese, oggi, percorso_anteprima, post_numerati)

ENV = Environment(loader=FileSystemLoader(str(RADICE / "templates" / "sito")), autoescape=select_autoescape(["html"]))


def _comune_contesto(radice: str) -> dict:
    return {"stati": STATI_POST, "radice": radice,
            "aggiornato": "aggiornato " + adesso().strftime("%d/%m %H:%M")}


def _conteggi(posts) -> list[tuple[str, int]]:
    c = Counter(p.get("stato", "bozza") for p in posts)
    return [(s, c[s]) for s in STATI_POST if c[s]]


def badge_piano(piano) -> str:
    return {"bozza": "bozza", "in_revisione": "da_rivedere", "pronto": "pronto", "approvato": "approvato",
            "programmato": "programmato"}.get(piano.get("stato_piano") or "bozza", "bozza")


def _tutti_i_slug() -> list[str]:
    return [p.name for p in sorted(CLIENTI.iterdir())
            if p.is_dir() and not p.name.startswith((".", "_")) and (p / "config.yaml").exists()]


class Anteprime:
    """Trova o crea le miniature dei file pronti; mappa i percorsi Drive ai link."""

    def __init__(self, slug: str, mese: str, scarica: bool):
        self.slug, self.mese, self.scarica = slug, mese, scarica
        self.media = Media(slug)
        self.ids = {}
        if scarica:
            try:
                for voce in self.media.elenca(f"pronti/{mese}"):
                    if voce.get("id"):
                        self.ids[voce["percorso"]] = voce["id"]
            except Errore as e:
                avviso(f"{slug}: Drive non raggiungibile ({e}), anteprime solo da cache")
                self.scarica = False

    def link(self, percorso: str) -> str:
        if percorso in self.ids:
            return f"https://drive.google.com/file/d/{self.ids[percorso]}/view"
        if self.media.locale:
            return ""
        return ""

    def anteprima(self, percorso: str, pagina_dir: Path) -> str:
        dest = percorso_anteprima(self.slug, percorso)
        if not dest.exists() and self.scarica:
            try:
                crea_anteprima(self.media.scarica(percorso), dest)
            except Errore as e:
                avviso(f"{self.slug}: {percorso}: {e}")
        if dest.exists():
            return str(dest.relative_to(pagina_dir)).replace("\\", "/")
        return ""


def pagina_mese(slug: str, percorso_piano: Path, scarica: bool) -> dict:
    cfg = carica_config(slug)
    piano = carica_piano(percorso_piano)
    mese = str(piano.get("mese") or percorso_piano.stem)
    pagina_dir = SITE / slug
    pagina_dir.mkdir(parents=True, exist_ok=True)
    ant = Anteprime(slug, mese, scarica)
    chiusura = {str(g).lower() for g in ((cfg.get("frequenza") or {}).get("giorni_chiusura") or [])}

    post_view = []
    giorni_visti = set()
    for n, p in post_numerati(piano):
        media = p.get("media") or {}
        file = [str(x) for x in (media.get("pronto") or []) if x]
        elementi = [{"nome": Path(f).name, "video": e_video(f), "anteprima": ant.anteprima(f, pagina_dir),
                     "link": ant.link(f)} for f in file]
        try:
            d = dt.date.fromisoformat(str(p.get("data")))
            etichetta = f"{GIORNI_BREVI[d.weekday()]} {d.day}"
        except ValueError:
            etichetta = str(p.get("data"))
        testi_grafica = media.get("testi_grafica") or []
        if isinstance(testi_grafica, dict):
            testi_grafica = [testi_grafica]
        testi = " / ".join(" · ".join(str(v) for v in t.values() if v) for t in testi_grafica if isinstance(t, dict))
        post_view.append({
            "numero": n, "id": p.get("id"), "data": str(p.get("data")), "ora": p.get("ora") or "--:--",
            "etichetta_data": etichetta, "formato": p.get("formato", ""),
            "canali": " + ".join({"instagram": "IG", "facebook": "FB"}.get(c, c) for c in (p.get("canali") or [])),
            "stato": p.get("stato", "bozza"), "media": elementi, "lavorazione": media.get("lavorazione", ""),
            "pilastro": p.get("pilastro", ""), "obiettivo": p.get("obiettivo", ""), "idea": p.get("idea", ""),
            "caption": (p.get("caption") or "").strip(), "testi_grafica": testi,
            "hashtag": " ".join(str(h) for h in (p.get("hashtag") or [])),
            "primo_commento": p.get("primo_commento", ""),
            "nota_revisore": (p.get("revisione") or {}).get("note", "") if p.get("stato") != "pubblicato" else "",
            "note_edoardo": p.get("note_edoardo", ""),
            "errore": (p.get("scheduler") or {}).get("errore", "") if p.get("stato") == "errore" else "",
            "url": (p.get("scheduler") or {}).get("url", ""),
            "primo_del_giorno": str(p.get("data")) not in giorni_visti,
        })
        giorni_visti.add(str(p.get("data")))

    # griglia del mese
    anno, m = map(int, mese.split("-"))
    celle = [None] * calendar.monthrange(anno, m)[0]
    for giorno in range(1, calendar.monthrange(anno, m)[1] + 1):
        d = dt.date(anno, m, giorno)
        celle.append({
            "giorno": giorno, "data": d.isoformat(), "oggi": d == oggi(),
            "chiuso": GIORNI[d.weekday()] in chiusura,
            "post": [{"numero": p["numero"], "stato": p["stato"], "formato": p["formato"]}
                     for p in post_view if p["data"] == d.isoformat()],
        })
    while len(celle) % 7:
        celle.append(None)

    strategia = piano.get("strategia") or {}
    html = ENV.get_template("mese.html").render(
        **_comune_contesto("../"), piano=piano, post=post_view, celle=celle, strategia=strategia,
        obiettivo=strategia.get("obiettivo_mese", ""), nome_cliente=cfg.get("nome", slug),
        nome_mese=nome_mese(mese), conteggi=_conteggi(piano["post"]))
    (pagina_dir / f"{mese}.html").write_text(html, encoding="utf-8")
    return {"mese": mese, "nome": nome_mese(mese).capitalize(), "stato_piano": piano.get("stato_piano", "bozza"),
            "stato_badge": badge_piano(piano),
            "conteggi": _conteggi(piano["post"]), "totale": max(len(piano["post"]), 1)}


def genera(solo: str | None, scarica: bool) -> None:
    SITE.mkdir(exist_ok=True)
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    clienti = []
    for slug in _tutti_i_slug():
        cfg = carica_config(slug)
        cartella = CLIENTI / slug / "piani"
        mesi = []
        piani = sorted(cartella.glob("*.yaml"), reverse=True) if cartella.exists() else []
        for p in piani:
            if solo and slug != solo:
                # rigenera solo l'indice: legge i dati senza riscrivere la pagina
                piano = carica_piano(p)
                mesi.append({"mese": p.stem, "nome": nome_mese(p.stem).capitalize(),
                             "stato_piano": piano.get("stato_piano", "bozza"), "stato_badge": badge_piano(piano),
                             "conteggi": _conteggi(piano["post"]), "totale": max(len(piano["post"]), 1)})
                continue
            mesi.append(pagina_mese(slug, p, scarica))
            info(f"site/{slug}/{p.stem}.html")
        report = sorted({p.stem for p in (SITE / slug).glob("report-*.html")}, reverse=True) if (SITE / slug).exists() else []
        clienti.append({"slug": slug, "nome": cfg.get("nome", slug), "citta": cfg.get("citta", ""),
                        "attivo": cfg.get("attivo", True), "mesi": mesi[:6],
                        "report": [r.replace("report-", "") for r in report][:3]})
    clienti.sort(key=lambda c: (not c["attivo"], c["nome"].lower()))
    html = ENV.get_template("indice.html").render(**_comune_contesto(""), clienti=clienti)
    (SITE / "index.html").write_text(html, encoding="utf-8")
    info("site/index.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cliente")
    ap.add_argument("--senza-anteprime", action="store_true")
    a = ap.parse_args()
    if a.cliente and a.cliente not in _tutti_i_slug():
        raise Errore(f"cliente '{a.cliente}' non trovato")
    genera(a.cliente, not a.senza_anteprime)
    return 0


if __name__ == "__main__":
    esegui_main(main)
