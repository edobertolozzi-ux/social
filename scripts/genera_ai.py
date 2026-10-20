#!/usr/bin/env python3
"""Immagini e video generati con l'AI (OpenRouter), con tetto di spesa per cliente.

Prima di ogni generazione controlla config.yaml > ai (tetto_mensile_eur, video_ai_mese_max) e registra
la spesa in clienti/<slug>/costi/AAAA-MM.yaml. Se il tetto verrebbe superato, si ferma.

Esempi:
  genera_ai.py immagine --cliente bistrot --prompt "..." --formato 4:5 --out sfondo.jpg [--riferimento foto.jpg]
  genera_ai.py video    --cliente bistrot --prompt "..." --durata 5 --formato 9:16 --out clip.mp4 [--riferimento-url URL]
  genera_ai.py spesa    --cliente bistrot
  genera_ai.py modelli-video

Regole: niente persone reali riconoscibili, niente loghi di terzi, mai piatti/prodotti/risultati che il cliente
non offre davvero. L'AI va bene per sfondi, atmosfere, elementi decorativi, animare una foto vera.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import time
from pathlib import Path

import requests

from comune import (CACHE, RADICE, Errore, Media, avviso, carica_config, carica_yaml, esegui_main, info,
                    registra_spesa, spesa_mese)

BASE = os.environ.get("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
RAPPORTI = {"4:5": "4:5", "1:1": "1:1", "9:16": "9:16", "16:9": "16:9"}


def modelli() -> dict:
    return carica_yaml(RADICE / "config" / "modelli.yaml")


def sessione() -> requests.Session:
    s = requests.Session()
    chiave = os.environ.get("OPENROUTER_API_KEY")
    if chiave:
        s.headers["Authorization"] = f"Bearer {chiave}"
    s.headers["HTTP-Referer"] = "https://volta-social.local"
    s.headers["X-Title"] = "VOLTA Social"
    return s


def _errore_http(r: requests.Response) -> None:
    if r.status_code < 400:
        return
    if r.status_code == 401:
        raise Errore("OpenRouter: chiave mancante o non valida (network secret per openrouter.ai)")
    if r.status_code == 402:
        raise Errore("OpenRouter: credito esaurito, ricarica il conto OpenRouter")
    if r.status_code == 403 and "host_not_allowed" in r.headers.get("x-deny-reason", ""):
        raise Errore("rete: openrouter.ai non è tra i domini consentiti dell'ambiente cloud")
    try:
        msg = r.json().get("error", {}).get("message") or r.text[:300]
    except ValueError:
        msg = r.text[:300]
    raise Errore(f"OpenRouter {r.status_code}: {msg}")


def controlla_tetto(slug: str, costo_eur: float, video: bool) -> None:
    cfg = carica_config(slug)
    tetto = float(cfg["ai"].get("tetto_mensile_eur", 0) or 0)
    max_video = int(cfg["ai"].get("video_ai_mese_max", 0) or 0)
    spesa = spesa_mese(slug)
    if spesa["totale_eur"] + costo_eur > tetto:
        raise Errore(f"tetto AI del mese superato: spesi {spesa['totale_eur']:.2f}€ su {tetto:.2f}€, "
                     f"questa generazione costerebbe ~{costo_eur:.2f}€. Usa una lavorazione gratuita o chiedi a Edoardo di alzare il tetto.")
    if video and spesa["video"] >= max_video:
        raise Errore(f"limite video AI del mese raggiunto ({spesa['video']}/{max_video})")


def _data_url(percorso: Path) -> str:
    tipo = mimetypes.guess_type(str(percorso))[0] or "image/jpeg"
    return f"data:{tipo};base64,{base64.b64encode(percorso.read_bytes()).decode()}"


def cmd_immagine(a):
    m = modelli()
    cambio = float(m.get("cambio_usd_eur", 0.92))
    modello = a.modello or m["immagine"]["modello"]
    stima = float(m["immagine"].get("costo_stimato_usd", 0.04)) * cambio
    controlla_tetto(a.cliente, stima, video=False)
    contenuto = [{"type": "text", "text": f"{a.prompt}\n\nAspect ratio {a.formato}. No text, no logos, no watermarks."}]
    if a.riferimento:
        contenuto.append({"type": "image_url", "image_url": {"url": _data_url(Media(a.cliente).scarica(a.riferimento))}})
    corpo = {"model": modello, "messages": [{"role": "user", "content": contenuto}],
             "modalities": ["image", "text"], "image_config": {"aspect_ratio": RAPPORTI.get(a.formato, "4:5")},
             "usage": {"include": True}}
    r = sessione().post(f"{BASE}/chat/completions", json=corpo, timeout=300)
    _errore_http(r)
    dati = r.json()
    immagini = ((dati.get("choices") or [{}])[0].get("message") or {}).get("images") or []
    if not immagini:
        raise Errore("il modello non ha restituito immagini (prova a riformulare il prompt o cambia modello)")
    url = immagini[0]["image_url"]["url"]
    grezzo = CACHE / "lavoro" / a.cliente / "_ai" / f"immagine-{int(time.time())}.png"
    grezzo.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        grezzo.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    else:
        grezzo.write_bytes(requests.get(url, timeout=120).content)
    costo_usd = (dati.get("usage") or {}).get("cost")
    costo = float(costo_usd) * cambio if costo_usd is not None else stima
    from grafica import ritaglia_immagine
    out = ritaglia_immagine(grezzo, a.formato, Path(a.out) if a.out else grezzo.with_suffix(".jpg"),
                            sfondo_sfocato=False)
    registra_spesa(a.cliente, {"tipo": "immagine", "modello": modello, "costo_eur": round(costo, 4),
                               "stima": costo_usd is None, "post": a.post or "", "file": str(out),
                               "prompt": a.prompt[:160]})
    info(f"{out}  (costo {costo:.3f}€{' stimato' if costo_usd is None else ''})")
    return 0


def cmd_video(a):
    m = modelli()
    cambio = float(m.get("cambio_usd_eur", 0.92))
    cfg_v = m["video"]
    modello = a.modello or cfg_v["modello"]
    costo = float(cfg_v.get("costo_al_secondo_usd", 0.13)) * a.durata * cambio
    controlla_tetto(a.cliente, costo, video=True)
    corpo = {"model": modello, "prompt": a.prompt, "duration": a.durata, "aspect_ratio": a.formato,
             "resolution": a.risoluzione or cfg_v.get("risoluzione", "720p"),
             "generate_audio": bool(cfg_v.get("audio", False))}
    riferimento = a.riferimento_url
    if a.riferimento and not riferimento:
        riferimento = _data_url(Media(a.cliente).scarica(a.riferimento))
        avviso("riferimento inviato come immagine incorporata: se il modello lo rifiuta usa --riferimento-url con un link pubblico diretto")
    if riferimento:
        corpo["input_references"] = [{"type": "image_url", "image_url": {"url": riferimento}}]
    s = sessione()
    r = s.post(f"{BASE}/videos", json=corpo, timeout=120)
    _errore_http(r)
    lavoro = r.json()
    info(f"Generazione avviata ({modello}, {a.durata}s, ~{costo:.2f}€). Attendo...")
    # registra subito la spesa: il costo parte all'invio
    registra_spesa(a.cliente, {"tipo": "video", "modello": modello, "costo_eur": round(costo, 4), "stima": True,
                               "post": a.post or "", "file": "", "prompt": a.prompt[:160],
                               "job": lavoro.get("id", "")})
    inizio = time.time()
    while lavoro.get("status") not in ("completed", "failed", "cancelled", "expired"):
        if time.time() - inizio > a.attesa_max:
            raise Errore(f"il video non è pronto dopo {a.attesa_max // 60} minuti (job {lavoro.get('id')})")
        time.sleep(15)
        url = lavoro.get("polling_url") or f"{BASE}/videos/{lavoro.get('id')}"
        if url.startswith("/"):
            url = "https://openrouter.ai" + url
        r = s.get(url, timeout=60)
        _errore_http(r)
        lavoro = r.json()
    if lavoro.get("status") != "completed":
        raise Errore(f"generazione video {lavoro.get('status')}: {lavoro.get('error', '')}")
    link = (lavoro.get("unsigned_urls") or [None])[0] or f"{BASE}/videos/{lavoro['id']}/content?index=0"
    r = s.get(link, timeout=300) if link.startswith("https://openrouter.ai/") else requests.get(link, timeout=300)
    _errore_http(r)
    out = Path(a.out) if a.out else CACHE / "lavoro" / a.cliente / "_ai" / f"video-{lavoro['id']}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    info(f"{out}  (costo stimato {costo:.2f}€)")
    return 0


def cmd_spesa(a):
    cfg = carica_config(a.cliente)
    s = spesa_mese(a.cliente, a.mese)
    info(f"{cfg.get('nome')} · {s['mese']}: {s['totale_eur']:.2f}€ su {float(cfg['ai']['tetto_mensile_eur'] or 0):.2f}€, "
         f"video {s['video']}/{cfg['ai']['video_ai_mese_max']}")
    for v in s["voci"]:
        info(f"  {str(v.get('quando', ''))[:16]} {v.get('tipo'):<8} {float(v.get('costo_eur') or 0):.3f}€ {v.get('post', '')}")
    return 0


def cmd_modelli_video(a):
    r = sessione().get(f"{BASE}/videos/models", timeout=60)
    _errore_http(r)
    dati = r.json()
    elenco = dati.get("data") if isinstance(dati, dict) else dati
    for mod in elenco or []:
        prezzo = mod.get("pricing") or mod.get("price") or ""
        info(f"{mod.get('id')}: durate {mod.get('supported_durations')}, formati {mod.get('supported_aspect_ratios')}, "
             f"risoluzioni {mod.get('supported_resolutions')} {json.dumps(prezzo) if prezzo else ''}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("immagine"); s.add_argument("--cliente", required=True); s.add_argument("--prompt", required=True)
    s.add_argument("--formato", default="4:5", choices=["4:5", "1:1", "9:16"]); s.add_argument("--out")
    s.add_argument("--riferimento", help="foto di partenza (Drive o locale)"); s.add_argument("--modello")
    s.add_argument("--post", help="id del post, per il registro spese"); s.set_defaults(f=cmd_immagine)

    s = sub.add_parser("video"); s.add_argument("--cliente", required=True); s.add_argument("--prompt", required=True)
    s.add_argument("--durata", type=int, default=5); s.add_argument("--formato", default="9:16", choices=["9:16", "1:1", "16:9"])
    s.add_argument("--risoluzione"); s.add_argument("--out"); s.add_argument("--modello")
    s.add_argument("--riferimento", help="foto da animare (Drive o locale)")
    s.add_argument("--riferimento-url", help="link pubblico diretto all'immagine di riferimento")
    s.add_argument("--attesa-max", type=int, default=1200, help="secondi massimi di attesa (default 20 minuti)")
    s.add_argument("--post"); s.set_defaults(f=cmd_video)

    s = sub.add_parser("spesa"); s.add_argument("--cliente", required=True); s.add_argument("--mese")
    s.set_defaults(f=cmd_spesa)
    s = sub.add_parser("modelli-video"); s.set_defaults(f=cmd_modelli_video)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
