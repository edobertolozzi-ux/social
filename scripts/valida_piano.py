#!/usr/bin/env python3
"""Controlla un piano editoriale: struttura, date, formati, testi, stati, coerenza con la config del cliente.

Uso:  python3 scripts/valida_piano.py clienti/<slug>/piani/2026-11.yaml [--json]
Esce con codice 1 se ci sono errori. Gli avvisi non bloccano.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter

from comune import (CANALI, FORMATI, GIORNI, LAVORAZIONI, STATI_POST, Errore, carica_config, carica_piano,
                    contiene_segnaposto, esegui_main, post_numerati, slug_da_piano)

RE_ORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
RE_HASHTAG = re.compile(r"^#[\wÀ-ÿ]+$", re.UNICODE)
STATI_CON_MEDIA = {"da_rivedere", "pronto", "approvato", "programmato", "pubblicato"}
STATI_CON_TESTO = {"da_rivedere", "pronto", "approvato", "programmato", "pubblicato"}


def valida(percorso: str) -> tuple[list[str], list[str]]:
    errori: list[str] = []
    avvisi: list[str] = []
    piano = carica_piano(percorso)
    slug = slug_da_piano(percorso, piano)
    try:
        cfg = carica_config(slug)
    except Errore as e:
        return [str(e)], []

    mese = str(piano.get("mese", ""))
    if not re.match(r"^\d{4}-\d{2}$", mese):
        errori.append("campo 'mese' mancante o non nel formato AAAA-MM")
    if piano.get("stato_piano", "bozza") not in ("bozza", "in_revisione", "pronto", "approvato", "programmato"):
        errori.append(f"stato_piano '{piano.get('stato_piano')}' non valido (bozza, in_revisione, pronto, approvato, programmato)")
    if not (piano.get("strategia") or {}).get("obiettivo_mese"):
        avvisi.append("strategia.obiettivo_mese vuoto")

    canali_ok = {c for c in CANALI if (cfg.get("canali") or {}).get(c)}
    giorni_chiusura = {str(g).lower() for g in ((cfg.get("frequenza") or {}).get("giorni_chiusura") or [])}
    ids = Counter(str(p.get("id")) for p in piano["post"])
    for i, n in ids.items():
        if n > 1:
            errori.append(f"id '{i}' usato {n} volte")

    prime_righe = Counter()
    per_settimana = Counter()
    story_settimana = Counter()

    for num, p in post_numerati(piano):
        tag = f"post {num} ({p.get('id', '?')})"
        stato = p.get("stato", "bozza")
        if stato not in STATI_POST:
            errori.append(f"{tag}: stato '{stato}' non valido ({', '.join(STATI_POST)})")
        if stato == "scartato":
            continue

        # data e ora
        try:
            d = dt.date.fromisoformat(str(p.get("data")))
            if mese and d.strftime("%Y-%m") != mese:
                errori.append(f"{tag}: la data {d} non è nel mese {mese}")
            sett = d.isocalendar()[1]
            if p.get("formato") == "story":
                story_settimana[sett] += 1
            else:
                per_settimana[sett] += 1
            if GIORNI[d.weekday()] in giorni_chiusura and stato not in ("pubblicato",):
                testo = (p.get("caption") or "").lower()
                if any(x in testo for x in ("oggi", "stasera", "stanotte", "vi aspettiamo")):
                    avvisi.append(f"{tag}: invita a venire di {GIORNI[d.weekday()]}, giorno di chiusura")
        except (TypeError, ValueError):
            errori.append(f"{tag}: data mancante o non valida (formato AAAA-MM-GG)")
        if not RE_ORA.match(str(p.get("ora", ""))):
            errori.append(f"{tag}: ora mancante o non valida (formato HH:MM)")

        # canali e formato
        canali = p.get("canali") or []
        if not canali:
            errori.append(f"{tag}: nessun canale")
        for c in canali:
            if c not in CANALI:
                errori.append(f"{tag}: canale '{c}' non valido")
            elif c not in canali_ok:
                avvisi.append(f"{tag}: canale '{c}' non attivo in config.yaml")
        formato = p.get("formato")
        if formato not in FORMATI:
            errori.append(f"{tag}: formato '{formato}' non valido ({', '.join(FORMATI)})")

        media = p.get("media") or {}
        lav = media.get("lavorazione", "nessuna")
        if lav not in LAVORAZIONI:
            errori.append(f"{tag}: lavorazione '{lav}' non valida ({', '.join(LAVORAZIONI)})")
        if lav == "grafica" and not media.get("template"):
            avvisi.append(f"{tag}: lavorazione grafica senza template")
        if lav in ("ai_immagine", "ai_video") and stato in STATI_CON_TESTO and not media.get("prompt_ai"):
            avvisi.append(f"{tag}: lavorazione AI senza prompt_ai")
        if lav in ("nessuna", "grafica", "reel_da_foto", "montaggio") and not media.get("sorgente") and stato != "bozza":
            avvisi.append(f"{tag}: nessun file di partenza in media.sorgente")

        pronti = [str(x) for x in (media.get("pronto") or []) if x]
        if stato in STATI_CON_MEDIA:
            if not pronti:
                errori.append(f"{tag}: stato '{stato}' ma media.pronto è vuoto")
            if formato in ("foto", "story", "reel") and len(pronti) > 1:
                errori.append(f"{tag}: il formato {formato} vuole un solo file, ce ne sono {len(pronti)}")
            if formato == "carosello" and not (2 <= len(pronti) <= 10):
                errori.append(f"{tag}: un carosello vuole da 2 a 10 file, ce ne sono {len(pronti)}")
            if formato == "reel" and pronti and not pronti[0].lower().endswith((".mp4", ".mov")):
                errori.append(f"{tag}: un reel vuole un video .mp4/.mov")
            if formato == "carosello" and "facebook" in canali and any(x.lower().endswith((".mp4", ".mov")) for x in pronti):
                avvisi.append(f"{tag}: carosello con video: non verrà pubblicato su Facebook, solo su Instagram")

        # testi
        caption = p.get("caption") or ""
        hashtag = p.get("hashtag") or []
        if not isinstance(caption, str):
            errori.append(f"{tag}: la caption deve essere un testo")
            caption = str(caption)
        if not isinstance(hashtag, list):
            errori.append(f"{tag}: hashtag deve essere una lista, es. [\"#viareggio\", \"#pranzo\"]")
            hashtag = []
        if formato != "story" and stato in STATI_CON_TESTO and not caption.strip():
            errori.append(f"{tag}: caption vuota")
        if len(caption) > 2200:
            errori.append(f"{tag}: caption di {len(caption)} caratteri (massimo 2200)")
        elif len(caption) > 1200:
            avvisi.append(f"{tag}: caption lunga ({len(caption)} caratteri)")
        if contiene_segnaposto(p):
            (errori if stato in ("approvato", "programmato") else avvisi).append(f"{tag}: contiene [DA VERIFICARE]")
        tutti_hashtag = list(hashtag) + re.findall(r"#[\wÀ-ÿ]+", caption)
        if len(tutti_hashtag) > 30:
            errori.append(f"{tag}: {len(tutti_hashtag)} hashtag (Instagram ne accetta al massimo 30)")
        elif formato != "story" and stato in STATI_CON_TESTO and len(hashtag) > 10:
            avvisi.append(f"{tag}: {len(hashtag)} hashtag, ne bastano 3-8")
        for h in hashtag:
            if not RE_HASHTAG.match(str(h)):
                avvisi.append(f"{tag}: hashtag non valido '{h}' (deve iniziare con # e non avere spazi o simboli)")
        if caption.strip():
            prima = caption.strip().split("\n")[0].strip().lower()[:30]
            prime_righe[prima] += 1
            if len(caption.strip().split("\n")[0]) > 150:
                avvisi.append(f"{tag}: la prima riga è lunga, il gancio si perde dopo ~125 caratteri")

        if stato == "da_correggere" and not (p.get("revisione") or {}).get("note"):
            avvisi.append(f"{tag}: da correggere senza note del revisore")

    for prima, n in prime_righe.items():
        if n > 1:
            avvisi.append(f"{n} caption iniziano allo stesso modo: '{prima}...'")

    freq = cfg.get("frequenza") or {}
    attesi = freq.get("post_settimana")
    if attesi:
        for sett, n in sorted(per_settimana.items()):
            if abs(n - int(attesi)) >= 2:
                avvisi.append(f"settimana {sett}: {n} post invece di {attesi}")
    return errori, avvisi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("piano")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    errori, avvisi = valida(a.piano)
    if a.json:
        print(json.dumps({"errori": errori, "avvisi": avvisi}, ensure_ascii=False, indent=2))
    else:
        for e in errori:
            print(f"ERRORE  {e}")
        for w in avvisi:
            print(f"avviso  {w}")
        if not errori and not avvisi:
            print("Piano valido, nessun problema.")
        elif not errori:
            print(f"Piano valido ({len(avvisi)} avvisi).")
        else:
            print(f"{len(errori)} errori, {len(avvisi)} avvisi.")
    return 1 if errori else 0


if __name__ == "__main__":
    esegui_main(main)
