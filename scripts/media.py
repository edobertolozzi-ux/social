#!/usr/bin/env python3
"""Foto e video dei clienti su Drive: elencare, scaricare, caricare, provini per l'analisi, link.

Esempi:
  media.py elenca    --cliente bistrot [--cartella materiali] [--nuovi] [--conta] [--ultimi 5]
  media.py provini   --cliente bistrot [--nuovi] [--cartella materiali] [--max 120]
  media.py scarica   --cliente bistrot materiali/2026-10/IMG_1.jpg [...]
  media.py carica    --cliente bistrot --mese 2026-11 file1.jpg file2.mp4
  media.py link      --cliente bistrot pronti/2026-11/2026-11-03-a.jpg
  media.py fotogrammi video.mp4            (oppure --cliente bistrot pronti/.../x.mp4)
  media.py info      --cliente bistrot <percorso>   (dimensioni, formato, durata)
  media.py verifica-catalogo --cliente bistrot
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from comune import (CACHE, Errore, Media, carica_yaml, cartella_cliente, crea_anteprima, e_foto, e_video,
                    esegui_main, ffprobe_dimensioni, ffprobe_durata, info, mese_corrente, percorso_anteprima,
                    salva_yaml, valida_mese, avviso)

try:  # foto HEIC degli iPhone
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

LATO = 360          # lato di una miniatura nei provini
COLONNE, RIGHE = 4, 3


def _font(dimensione: int):
    for nome in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nome, dimensione)
        except OSError:
            continue
    return ImageFont.load_default()


def _catalogati(slug: str) -> set[str]:
    p = cartella_cliente(slug) / "media.yaml"
    if not p.exists():
        return set()
    return {str(v.get("percorso")) for v in (carica_yaml(p).get("file") or [])}


def _filtra(voci, nuovi: bool, slug: str):
    voci = [v for v in voci if e_foto(v["percorso"]) or e_video(v["percorso"])]
    if nuovi:
        presenti = _catalogati(slug)
        voci = [v for v in voci if v["percorso"] not in presenti]
    return voci


def cmd_elenca(a):
    m = Media(a.cliente)
    voci = _filtra(m.elenca(a.cartella), a.nuovi, a.cliente)
    if a.ultimi:
        voci = sorted(voci, key=lambda v: v["modificato"], reverse=True)[: a.ultimi]
    if a.conta:
        foto = sum(1 for v in voci if e_foto(v["percorso"]))
        info(f"{len(voci)} file ({foto} foto, {len(voci) - foto} video){' nuovi' if a.nuovi else ''}")
        return 0
    if a.json:
        print(json.dumps(voci, ensure_ascii=False, indent=2))
        return 0
    for v in voci:
        info(f"{v['percorso']}  ({v['dimensione'] / 1_000_000:.1f} MB, {v['modificato'][:16]})")
    if not voci:
        info("Nessun file" + (" nuovo." if a.nuovi else "."))
    return 0


def _miniatura_foto(percorso: Path) -> Image.Image:
    with Image.open(percorso) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((LATO, LATO))
        return im.copy()


def _fotogramma(video: Path, secondo: float, larghezza: int) -> Image.Image | None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "f.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{secondo:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={larghezza}:-2", "-y", str(out)], capture_output=True, timeout=120)
        if out.exists():
            with Image.open(out) as im:
                return im.convert("RGB").copy()
    return None


def _miniatura_video(percorso: Path) -> tuple[Image.Image, float | None]:
    durata = ffprobe_durata(percorso) or 1.0
    fotogrammi = [f for f in (_fotogramma(percorso, durata * x, LATO // 3) for x in (0.15, 0.5, 0.85)) if f]
    tela = Image.new("RGB", (LATO, LATO), (20, 20, 20))
    if fotogrammi:
        largh = LATO // 3
        for i, f in enumerate(fotogrammi):
            f.thumbnail((largh - 4, LATO - 40))
            tela.paste(f, (i * largh + (largh - f.width) // 2, (LATO - f.height) // 2))
    d = ImageDraw.Draw(tela)
    d.rectangle([0, LATO - 34, LATO, LATO], fill=(0, 0, 0))
    d.text((8, LATO - 30), f"VIDEO {durata:.0f}s", fill=(255, 210, 0), font=_font(22))
    return tela, durata


def cmd_provini(a):
    m = Media(a.cliente)
    voci = _filtra(m.elenca(a.cartella), a.nuovi, a.cliente)[: a.max]
    if not voci:
        info("Nessun file da mostrare.")
        return 0
    dest = CACHE / "provini" / a.cliente
    dest.mkdir(parents=True, exist_ok=True)
    for vecchio in dest.glob("provino-*.jpg"):
        vecchio.unlink()
    indice = {}
    per_foglio = COLONNE * RIGHE
    fogli = math.ceil(len(voci) / per_foglio)
    font = _font(26)
    for f in range(fogli):
        gruppo = voci[f * per_foglio:(f + 1) * per_foglio]
        righe = math.ceil(len(gruppo) / COLONNE)
        foglio = Image.new("RGB", (COLONNE * (LATO + 10) + 10, righe * (LATO + 10) + 10), (245, 245, 245))
        for i, v in enumerate(gruppo):
            numero = f * per_foglio + i + 1
            try:
                locale = m.scarica(v["percorso"])
                if e_video(v["percorso"]):
                    tile, durata = _miniatura_video(locale)
                    v["durata_s"] = durata
                else:
                    tile = _miniatura_foto(locale)
                    with Image.open(locale) as im:
                        im = ImageOps.exif_transpose(im)
                        v["dimensioni"] = f"{im.width}x{im.height}"
            except Exception as e:  # file rotto: segnalalo nel provino
                avviso(f"{v['percorso']}: {e}")
                tile = Image.new("RGB", (LATO, LATO), (200, 60, 60))
            x = 10 + (i % COLONNE) * (LATO + 10)
            y = 10 + (i // COLONNE) * (LATO + 10)
            foglio.paste(tile, (x + (LATO - tile.width) // 2, y + (LATO - tile.height) // 2))
            d = ImageDraw.Draw(foglio)
            d.rectangle([x, y, x + 52, y + 38], fill=(0, 0, 0))
            d.text((x + 6, y + 4), str(numero), fill=(255, 255, 255), font=font)
            indice[numero] = v
        out = dest / f"provino-{f + 1:02d}.jpg"
        foglio.save(out, quality=82)
        info(f"Provino: {out}")
    (dest / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
    info(f"Indice numero → file: {dest / 'indice.json'}  ({len(voci)} file in {fogli} provini)")
    return 0


def cmd_scarica(a):
    m = Media(a.cliente)
    for p in a.percorsi:
        info(str(m.scarica(p)))
    return 0


def cmd_carica(a):
    m = Media(a.cliente)
    mese = valida_mese(a.mese or mese_corrente())
    for f in a.file:
        nome = Path(f).name
        dest = f"{a.cartella.strip('/')}/{nome}" if a.cartella else f"pronti/{mese}/{nome}"
        info(m.carica(f, dest))
        if dest.startswith("pronti/"):
            crea_anteprima(Path(f), percorso_anteprima(a.cliente, dest))
    return 0


def cmd_link(a):
    m = Media(a.cliente)
    for p in a.percorsi:
        info(m.link(p) or "(link non disponibile)")
    return 0


def cmd_fotogrammi(a):
    if a.cliente:
        video = Media(a.cliente).scarica(a.video)
    else:
        video = Path(a.video)
        if not video.exists():
            raise Errore(f"video non trovato: {video}")
    durata = ffprobe_durata(video)
    if not durata:
        raise Errore("non riesco a leggere il video (file danneggiato o non è un video)")
    n = 6
    largh = 320
    immagini = []
    for i in range(n):
        t = 0.05 + (durata - 0.1) * i / (n - 1) if durata > 0.2 else 0
        fr = _fotogramma(video, t, largh)
        if fr:
            immagini.append((t, fr))
    if not immagini:
        raise Errore("nessun fotogramma estratto")
    alt = max(im.height for _, im in immagini)
    foglio = Image.new("RGB", (3 * (largh + 8) + 8, 2 * (alt + 40) + 8), (30, 30, 30))
    d = ImageDraw.Draw(foglio)
    for i, (t, im) in enumerate(immagini):
        x = 8 + (i % 3) * (largh + 8)
        y = 8 + (i // 3) * (alt + 40)
        foglio.paste(im, (x, y + 32))
        d.text((x, y + 4), f"{t:.1f}s", fill=(255, 255, 255), font=_font(20))
    dims = ffprobe_dimensioni(video)
    out = CACHE / "fotogrammi" / f"{video.stem}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    foglio.save(out, quality=85)
    formato = f"{dims[0]}x{dims[1]}" if dims else "dimensioni sconosciute"
    info(f"{out}  (durata {durata:.1f}s, {formato})")
    return 0


def cmd_info(a):
    m = Media(a.cliente)
    for p in a.percorsi:
        locale = m.scarica(p)
        if e_video(p):
            dims = ffprobe_dimensioni(locale)
            info(f"{p}: video {dims[0]}x{dims[1]}, {ffprobe_durata(locale)}s, {locale.stat().st_size / 1e6:.1f} MB" if dims else f"{p}: video illeggibile")
        else:
            with Image.open(locale) as im:
                im = ImageOps.exif_transpose(im)
                r = im.width / im.height
                info(f"{p}: foto {im.width}x{im.height} (rapporto {r:.2f}), {locale.stat().st_size / 1e6:.1f} MB")
    return 0


CAMPI = ["percorso", "tipo", "categoria", "descrizione", "qualita", "orientamento", "adatta_a"]


def cmd_verifica_catalogo(a):
    p = cartella_cliente(a.cliente) / "media.yaml"
    if not p.exists():
        raise Errore("media.yaml non esiste")
    catalogo = carica_yaml(p)
    voci = catalogo.get("file") or []
    problemi = []
    visti = set()
    for v in voci:
        perc = str(v.get("percorso"))
        if perc in visti:
            problemi.append(f"duplicato: {perc}")
        visti.add(perc)
        for c in CAMPI:
            if v.get(c) in (None, "", []):
                problemi.append(f"{perc}: manca '{c}'")
        q = v.get("qualita")
        if q is not None and (not isinstance(q, int) or not 1 <= q <= 5):
            problemi.append(f"{perc}: qualita deve essere un numero da 1 a 5")
    if a.controlla_drive:
        esistenti = {v["percorso"] for v in Media(a.cliente).elenca("materiali")}
        for perc in visti:
            if perc.startswith("materiali/") and perc not in esistenti:
                problemi.append(f"{perc}: non esiste più su Drive")
    for x in problemi:
        info(f"- {x}")
    info(f"{len(voci)} voci, {len(problemi)} problemi.")
    return 1 if problemi else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("elenca"); s.add_argument("--cliente", required=True)
    s.add_argument("--cartella", default="materiali"); s.add_argument("--nuovi", action="store_true")
    s.add_argument("--conta", action="store_true"); s.add_argument("--ultimi", type=int)
    s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_elenca)

    s = sub.add_parser("provini"); s.add_argument("--cliente", required=True)
    s.add_argument("--cartella", default="materiali"); s.add_argument("--nuovi", action="store_true")
    s.add_argument("--max", type=int, default=120); s.set_defaults(f=cmd_provini)

    s = sub.add_parser("scarica"); s.add_argument("--cliente", required=True); s.add_argument("percorsi", nargs="+")
    s.set_defaults(f=cmd_scarica)

    s = sub.add_parser("carica"); s.add_argument("--cliente", required=True); s.add_argument("--mese")
    s.add_argument("--cartella", help="cartella di destinazione (default pronti/AAAA-MM)")
    s.add_argument("file", nargs="+"); s.set_defaults(f=cmd_carica)

    s = sub.add_parser("link"); s.add_argument("--cliente", required=True); s.add_argument("percorsi", nargs="+")
    s.set_defaults(f=cmd_link)

    s = sub.add_parser("fotogrammi"); s.add_argument("video"); s.add_argument("--cliente")
    s.set_defaults(f=cmd_fotogrammi)

    s = sub.add_parser("info"); s.add_argument("--cliente", required=True); s.add_argument("percorsi", nargs="+")
    s.set_defaults(f=cmd_info)

    s = sub.add_parser("verifica-catalogo"); s.add_argument("--cliente", required=True)
    s.add_argument("--controlla-drive", action="store_true"); s.set_defaults(f=cmd_verifica_catalogo)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
