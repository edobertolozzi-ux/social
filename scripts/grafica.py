#!/usr/bin/env python3
"""Grafiche dei post: template HTML + brand kit → JPEG pronti per Instagram e Facebook.

Esempi:
  grafica.py template --cliente bistrot
  grafica.py render --cliente bistrot --template post-promo --formato 4:5 \
      --foto materiali/2026-10/IMG_1.jpg --dati '{"titolo":"Menu d\\'autunno","prezzo":"18€"}' --out post.jpg
  grafica.py carosello --cliente bistrot --template carosello-slide --formato 4:5 \
      --foto f1.jpg f2.jpg f3.jpg --dati-lista '[{"titolo":"..."},{"titolo":"..."}]' --prefisso 2026-11-03-a
  grafica.py ritaglia --cliente bistrot --sorgente materiali/x.jpg --formato 4:5 --out x.jpg [--fuoco alto]
  grafica.py verifica-brand --cliente bistrot
  grafica.py anteprima-brand --cliente bistrot

Formati: 4:5 (1080x1350, feed), 1:1 (1080x1080), 9:16 (1080x1920, story e reel), 1.91:1 (1080x566).
Instagram accetta solo JPEG per le foto: l'output è sempre .jpg (tranne --png per le sovrapposizioni).
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from comune import (CACHE, TEMPLATE_GRAFICHE, Errore, Media, carica_brand_kit, carica_config, carica_yaml,
                    cartella_cliente, esegui_main, info, avviso)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

FORMATI = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "1.91:1": (1080, 566)}

DEFAULT_KIT = {
    "colori": {"primario": "#1F3A5F", "secondario": "#E8DCC8", "sfondo": "#FAF7F2", "testo": "#1C1C1C",
               "testo_su_primario": "#FFFFFF", "accento": "#C9732B"},
    "font": {"titoli": "Playfair Display", "titoli_peso": 600, "testi": "Inter", "testi_peso": 400},
    "stile": {"angoli_px": 0, "titoli_maiuscoli": False, "velatura_foto": 0.35, "mostra_logo": True, "firma": ""},
}


# ---------------------------------------------------------------- brand kit

def kit_completo(slug: str) -> dict:
    kit = carica_brand_kit(slug)
    for sezione, valori in DEFAULT_KIT.items():
        kit.setdefault(sezione, {})
        if kit[sezione] is None:
            kit[sezione] = {}
        for k, v in valori.items():
            if kit[sezione].get(k) in (None, ""):
                kit[sezione][k] = v
    return kit


def google_fonts_url(kit: dict) -> str:
    famiglie = []
    f = kit["font"]
    pesi_titoli = sorted({int(f.get("titoli_peso", 600)), 700})
    pesi_testi = sorted({int(f.get("testi_peso", 400)), 700})
    for nome, pesi in ((f["titoli"], pesi_titoli), (f["testi"], pesi_testi)):
        voce = f"family={quote(str(nome)).replace('%20', '+')}:wght@{';'.join(map(str, pesi))}"
        if voce not in famiglie:
            famiglie.append(voce)
    return "https://fonts.googleapis.com/css2?" + "&".join(famiglie) + "&display=block"


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = str(h).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrasto(a: str, b: str) -> float:
    def lum(rgb):
        out = []
        for c in rgb:
            c = c / 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    l1, l2 = sorted([lum(_hex_rgb(a)), lum(_hex_rgb(b))], reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


# ---------------------------------------------------------------- template

def cartelle_template(slug: str) -> list[Path]:
    cartelle = []
    personali = cartella_cliente(slug) / "templates"
    if personali.is_dir():
        cartelle.append(personali)
    cartelle.append(TEMPLATE_GRAFICHE)
    return cartelle


def elenco_template(slug: str) -> list[tuple[str, str, str]]:
    visti, risultato = set(), []
    for cartella in cartelle_template(slug):
        for p in sorted(cartella.glob("*.html")):
            if p.name.startswith("_") or p.stem in visti:
                continue
            visti.add(p.stem)
            m = re.search(r"\{#\s*descrizione:\s*(.*?)#\}", p.read_text(encoding="utf-8"), re.S)
            origine = "cliente" if cartella != TEMPLATE_GRAFICHE else "comune"
            risultato.append((p.stem, origine, (m.group(1).strip() if m else "")))
    return risultato


def dimensione_titolo(titolo: str, formato: str) -> int:
    n = len(titolo or "")
    base = 104 if formato == "9:16" else 92 if formato in ("4:5", "1:1") else 64
    if n <= 14:
        return int(base * 1.15)
    if n <= 24:
        return base
    if n <= 40:
        return int(base * 0.82)
    if n <= 70:
        return int(base * 0.66)
    return int(base * 0.52)


def _file_url(p: Path | None) -> str:
    return p.resolve().as_uri() if p else ""


def _prepara_foto(media: Media, sorgente: str | None) -> Path | None:
    if not sorgente:
        return None
    locale = media.scarica(sorgente)
    # converte HEIC/PNG grandi in JPEG ruotato correttamente (il browser non legge HEIC né l'EXIF in background-image)
    out = CACHE / "lavoro" / media.slug / "_foto" / (Path(str(sorgente)).stem + ".jpg")
    if not out.exists() or out.stat().st_mtime < locale.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(locale) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((2400, 2400))
            im.save(out, quality=92)
    return out


def _logo(media: Media, kit: dict, chiave: str) -> Path | None:
    percorso = kit.get(chiave)
    if not percorso:
        return None
    try:
        return media.scarica(percorso)
    except Errore as e:
        avviso(f"logo non disponibile ({percorso}): {e}")
        return None


class Renderer:
    def __init__(self, slug: str):
        self.slug = slug
        self.cfg = carica_config(slug)
        self.kit = kit_completo(slug)
        self.media = Media(slug)
        self.env = Environment(loader=FileSystemLoader([str(c) for c in cartelle_template(slug)]),
                               autoescape=select_autoescape(["html"]))
        self._browser = None
        self._pw = None
        self.logo = _logo(self.media, self.kit, "logo")
        self.logo_chiaro = _logo(self.media, self.kit, "logo_chiaro")

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def html(self, template: str, formato: str, testi: dict, foto: Path | None,
             slide: int = 1, totale: int = 0, trasparente: bool = False, fuoco: str = "center") -> str:
        if formato not in FORMATI:
            raise Errore(f"formato '{formato}' non valido: {', '.join(FORMATI)}")
        larghezza, altezza = FORMATI[formato]
        try:
            tpl = self.env.get_template(f"{template}.html")
        except Exception:
            nomi = ", ".join(n for n, _, _ in elenco_template(self.slug))
            raise Errore(f"template '{template}' non trovato. Disponibili: {nomi}")
        testi = {k: (str(v) if v is not None else "") for k, v in (testi or {}).items()}
        return tpl.render(
            larghezza=larghezza, altezza=altezza, formato=formato,
            c=self.kit["colori"], f=self.kit["font"], s=self.kit["stile"],
            google_fonts_url=google_fonts_url(self.kit),
            margine=72 if formato != "1.91:1" else 48,
            fs_titolo=dimensione_titolo(testi.get("titolo", ""), formato),
            fs_sottotitolo=40 if formato == "9:16" else 36,
            altezza_logo=64 if formato != "9:16" else 80,
            t=testi, foto_url=_file_url(foto), logo_url=_file_url(self.logo),
            logo_chiaro_url=_file_url(self.logo_chiaro), nome=self.cfg.get("nome", ""),
            slide=slide, totale=totale, trasparente=trasparente,
            fuoco={"alto": "center 20%", "basso": "center 80%"}.get(fuoco, "center"),
        )

    def render(self, template: str, formato: str, testi: dict, foto_sorgente: str | None, out: Path,
               slide: int = 1, totale: int = 0, png: bool = False, fuoco: str = "center") -> Path:
        foto = _prepara_foto(self.media, foto_sorgente)
        larghezza, altezza = FORMATI.get(formato, (1080, 1350))
        contenuto = self.html(template, formato, testi, foto, slide, totale, trasparente=png, fuoco=fuoco)
        out = Path(out)
        if png:
            out = out.with_suffix(".png")
        elif out.suffix.lower() not in (".jpg", ".jpeg"):
            out = out.with_suffix(".jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8",
                                         dir=CACHE.mkdir(parents=True, exist_ok=True) or CACHE) as f:
            f.write(contenuto)
            html_path = Path(f.name)
        try:
            pagina = self._browser.new_page(viewport={"width": larghezza, "height": altezza}, device_scale_factor=1)
            pagina.goto(html_path.as_uri(), wait_until="load", timeout=30000)
            try:
                pagina.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                avviso("i font di Google non hanno risposto in tempo: uso i font di riserva")
            pagina.evaluate("document.fonts.ready")
            if png:
                pagina.screenshot(path=str(out), type="png", omit_background=True,
                                  clip={"x": 0, "y": 0, "width": larghezza, "height": altezza})
            else:
                pagina.screenshot(path=str(out), type="jpeg", quality=92,
                                  clip={"x": 0, "y": 0, "width": larghezza, "height": altezza})
            pagina.close()
        finally:
            html_path.unlink(missing_ok=True)
        return out


# ---------------------------------------------------------------- comandi

def _dati(testo: str | None) -> dict:
    if not testo:
        return {}
    try:
        d = json.loads(testo)
    except json.JSONDecodeError as e:
        raise Errore(f"--dati non è un JSON valido: {e}")
    if not isinstance(d, dict):
        raise Errore("--dati deve essere un oggetto JSON, es. '{\"titolo\": \"...\"}'")
    return d


def _out_default(slug: str, nome: str) -> Path:
    return CACHE / "lavoro" / slug / nome


def cmd_template(a):
    for nome, origine, descr in elenco_template(a.cliente):
        info(f"{nome:<18} [{origine}] {descr}")
    return 0


def cmd_render(a):
    out = Path(a.out) if a.out else _out_default(a.cliente, f"{a.template}.jpg")
    with Renderer(a.cliente) as r:
        res = r.render(a.template, a.formato, _dati(a.dati), a.foto, out, a.slide, a.totale, a.png, a.fuoco)
    info(str(res))
    return 0


def cmd_carosello(a):
    try:
        lista = json.loads(a.dati_lista) if a.dati_lista else []
    except json.JSONDecodeError as e:
        raise Errore(f"--dati-lista non è un JSON valido: {e}")
    foto = a.foto or []
    totale = max(len(lista), len(foto))
    if totale < 2:
        raise Errore("un carosello vuole almeno 2 slide (foto o voci di --dati-lista)")
    if totale > 10:
        raise Errore("massimo 10 slide")
    cartella = Path(a.cartella) if a.cartella else _out_default(a.cliente, "")
    risultati = []
    with Renderer(a.cliente) as r:
        for i in range(totale):
            testi = lista[i] if i < len(lista) else {}
            f = foto[i] if i < len(foto) else None
            out = cartella / f"{a.prefisso}-{i + 1}.jpg"
            risultati.append(r.render(a.template, a.formato, testi, f, out, i + 1, totale))
    for p in risultati:
        info(str(p))
    return 0


def ritaglia_immagine(sorgente: Path, formato: str, out: Path, fuoco: str = "centro",
                      sfondo_sfocato: bool | None = None) -> Path:
    larghezza, altezza = FORMATI[formato]
    obiettivo = larghezza / altezza
    with Image.open(sorgente) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        r = im.width / im.height
        # quanta immagine si perderebbe col ritaglio
        perdita = 1 - (min(r, obiettivo) / max(r, obiettivo))
        if sfondo_sfocato is None:
            sfondo_sfocato = perdita > 0.35
        if sfondo_sfocato:
            fondo = ImageOps.fit(im, (larghezza, altezza), method=Image.LANCZOS)
            fondo = fondo.filter(ImageFilter.GaussianBlur(40))
            fondo = Image.eval(fondo, lambda x: int(x * 0.7))
            primo = im.copy()
            primo.thumbnail((larghezza, altezza), Image.LANCZOS)
            fondo.paste(primo, ((larghezza - primo.width) // 2, (altezza - primo.height) // 2))
            risultato = fondo
        else:
            centri = {"alto": (0.5, 0.25), "basso": (0.5, 0.75), "sinistra": (0.25, 0.5), "destra": (0.75, 0.5)}
            risultato = ImageOps.fit(im, (larghezza, altezza), method=Image.LANCZOS,
                                     centering=centri.get(fuoco, (0.5, 0.5)))
        if min(im.width, im.height) < 800:
            avviso(f"{sorgente.name}: risoluzione bassa ({im.width}x{im.height}), il risultato potrebbe essere sgranato")
    out = Path(out).with_suffix(".jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    risultato.save(out, quality=92, optimize=True)
    return out


def cmd_ritaglia(a):
    media = Media(a.cliente)
    sorgente = media.scarica(a.sorgente)
    out = Path(a.out) if a.out else _out_default(a.cliente, Path(a.sorgente).stem + ".jpg")
    sfocato = True if a.sfondo_sfocato else (False if a.no_sfondo_sfocato else None)
    info(str(ritaglia_immagine(sorgente, a.formato, out, a.fuoco, sfocato)))
    return 0


def cmd_verifica_brand(a):
    p = cartella_cliente(a.cliente) / "brand-kit.yaml"
    if not p.exists():
        raise Errore("brand-kit.yaml non esiste: va creato dall'agente brand")
    kit = carica_yaml(p)
    problemi, note = [], []
    colori = kit.get("colori") or {}
    for chiave in DEFAULT_KIT["colori"]:
        v = colori.get(chiave)
        if not v:
            problemi.append(f"colore '{chiave}' mancante")
            continue
        try:
            _hex_rgb(v)
        except ValueError:
            problemi.append(f"colore '{chiave}' non è esadecimale: {v}")
    try:
        coppie = [("testo", "sfondo"), ("testo_su_primario", "primario"), ("testo", "secondario")]
        for a_, b_ in coppie:
            if colori.get(a_) and colori.get(b_):
                c = contrasto(colori[a_], colori[b_])
                msg = f"contrasto {a_} su {b_}: {c}"
                (problemi if c < 4.5 else note).append(msg + (" (minimo 4.5)" if c < 4.5 else ""))
        if colori.get("accento"):
            c = contrasto("#FFFFFF", colori["accento"])
            (note if c >= 3 else problemi).append(f"contrasto bianco su accento (etichette): {c}" + ("" if c >= 3 else " (minimo 3)"))
    except ValueError:
        pass
    font = kit.get("font") or {}
    for k in ("titoli", "testi"):
        if not font.get(k):
            problemi.append(f"font '{k}' mancante")
    if not kit.get("logo"):
        note.append("logo non indicato: le grafiche useranno il nome scritto")
    for n in note:
        info(f"ok      {n}")
    for pr in problemi:
        info(f"PROBLEMA {pr}")
    info("Brand kit valido." if not problemi else f"{len(problemi)} problemi da sistemare.")
    return 1 if problemi else 0


def cmd_anteprima_brand(a):
    cfg = carica_config(a.cliente)
    foto = a.foto
    if not foto:
        p_media = cartella_cliente(a.cliente) / "media.yaml"
        if p_media.exists():
            voci = [v for v in (carica_yaml(p_media).get("file") or []) if v.get("tipo") == "foto"]
            voci.sort(key=lambda v: -(v.get("qualita") or 0))
            foto = [str(v["percorso"]) for v in voci[:2]]
    foto = (foto or []) + [None, None]
    dest = CACHE / "anteprime" / a.cliente
    dest.mkdir(parents=True, exist_ok=True)
    prove = [
        ("post-foto-titolo", "4:5", {"titolo": f"Benvenuti da {cfg.get('nome', '')}", "sottotitolo": "Un esempio di post con foto e titolo"}, foto[0]),
        ("post-promo", "4:5", {"etichetta": "Solo questa settimana", "titolo": "Esempio di promo", "prezzo": "00€", "cta": "Prenota ora"}, foto[1] or foto[0]),
        ("post-citazione", "1:1", {"titolo": "Una frase che racconta chi siamo, in poche parole.", "sottotitolo": "Il titolare"}, None),
        ("story-annuncio", "9:16", {"etichetta": "Novità", "titolo": "Esempio di story", "sottotitolo": "Testo di supporto breve", "cta": "Scopri di più"}, foto[0]),
    ]
    file = []
    with Renderer(a.cliente) as r:
        for nome, formato, testi, f in prove:
            file.append(r.render(nome, formato, testi, f, dest / f"{nome}.jpg"))
    # tavola riassuntiva: palette + font + esempi
    kit = kit_completo(a.cliente)
    tavola = Image.new("RGB", (2200, 1500), "#FFFFFF")
    d = ImageDraw.Draw(tavola)
    try:
        f_tit = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
        f_txt = ImageFont.truetype("DejaVuSans.ttf", 26)
    except OSError:
        f_tit = f_txt = ImageFont.load_default()
    d.text((60, 40), f"Mood board · {cfg.get('nome', '')}", fill="#111", font=f_tit)
    d.text((60, 105), f"Titoli: {kit['font']['titoli']}   ·   Testi: {kit['font']['testi']}", fill="#444", font=f_txt)
    x = 60
    for nome, colore in kit["colori"].items():
        d.rectangle([x, 160, x + 220, 300], fill=colore, outline="#ddd")
        d.text((x, 310), f"{nome}\n{colore}", fill="#333", font=f_txt)
        x += 250
    x = 60
    for p in file:
        with Image.open(p) as im:
            im.thumbnail((480, 1000))
            tavola.paste(im, (x, 420))
            x += im.width + 40
    out = dest / "moodboard.jpg"
    tavola.save(out, quality=88)
    for p in file:
        info(str(p))
    info(f"Tavola riassuntiva: {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("template", help="elenca i template disponibili"); s.add_argument("--cliente", required=True)
    s.set_defaults(f=cmd_template)

    s = sub.add_parser("render", help="crea una grafica")
    s.add_argument("--cliente", required=True); s.add_argument("--template", required=True)
    s.add_argument("--formato", default="4:5", choices=list(FORMATI)); s.add_argument("--foto")
    s.add_argument("--dati", help="testi in JSON: titolo, sottotitolo, etichetta, prezzo, cta")
    s.add_argument("--out"); s.add_argument("--slide", type=int, default=1); s.add_argument("--totale", type=int, default=0)
    s.add_argument("--png", action="store_true", help="PNG trasparente (per sovrapposizioni ai video)")
    s.add_argument("--fuoco", default="center", choices=["center", "alto", "basso"])
    s.set_defaults(f=cmd_render)

    s = sub.add_parser("carosello", help="crea tutte le slide di un carosello")
    s.add_argument("--cliente", required=True); s.add_argument("--template", default="carosello-slide")
    s.add_argument("--formato", default="4:5", choices=list(FORMATI)); s.add_argument("--foto", nargs="*")
    s.add_argument("--dati-lista", help="JSON: lista di oggetti testi, una voce per slide")
    s.add_argument("--prefisso", required=True, help="id del post, es. 2026-11-03-a"); s.add_argument("--cartella")
    s.set_defaults(f=cmd_carosello)

    s = sub.add_parser("ritaglia", help="ritaglia una foto al formato giusto")
    s.add_argument("--cliente", required=True); s.add_argument("--sorgente", required=True)
    s.add_argument("--formato", default="4:5", choices=list(FORMATI)); s.add_argument("--out")
    s.add_argument("--fuoco", default="centro", choices=["centro", "alto", "basso", "sinistra", "destra"])
    s.add_argument("--sfondo-sfocato", action="store_true", help="adatta la foto intera su sfondo sfocato")
    s.add_argument("--no-sfondo-sfocato", action="store_true", help="ritaglia sempre, anche se si perde molto")
    s.set_defaults(f=cmd_ritaglia)

    s = sub.add_parser("verifica-brand", help="controlla il brand kit"); s.add_argument("--cliente", required=True)
    s.set_defaults(f=cmd_verifica_brand)

    s = sub.add_parser("anteprima-brand", help="esempi di grafiche col brand kit")
    s.add_argument("--cliente", required=True); s.add_argument("--foto", nargs="*")
    s.set_defaults(f=cmd_anteprima_brand)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
