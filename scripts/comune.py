"""Funzioni comuni agli script di VOLTA Social: percorsi, YAML, clienti, piani, media su Drive, spese AI."""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

RADICE = Path(__file__).resolve().parent.parent
CLIENTI = RADICE / "clienti"
CACHE = RADICE / ".cache"
SITE = RADICE / "site"
TEMPLATE_GRAFICHE = RADICE / "templates" / "grafiche"
FUSO = ZoneInfo("Europe/Rome")

STATI_POST = [
    "bozza", "da_rivedere", "da_correggere", "pronto", "approvato",
    "programmato", "pubblicato", "errore", "scartato",
]
FORMATI = ["foto", "carosello", "reel", "story"]
LAVORAZIONI = ["nessuna", "grafica", "reel_da_foto", "montaggio", "ai_immagine", "ai_video"]
CANALI = ["instagram", "facebook"]
ESTENSIONI_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ESTENSIONI_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}


# ---------------------------------------------------------------- messaggi

class Errore(Exception):
    """Errore da mostrare a Edoardo in una riga, senza traceback."""


def avviso(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(msg)


def esegui_main(funzione) -> None:
    """Esegue il main di uno script mostrando gli errori in modo leggibile."""
    try:
        codice = funzione()
        sys.exit(codice or 0)
    except Errore as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


# ---------------------------------------------------------------- YAML

def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    y.allow_unicode = True
    return y


def carica_yaml(percorso: Path | str):
    percorso = Path(percorso)
    if not percorso.exists():
        raise Errore(f"file non trovato: {percorso}")
    with open(percorso, encoding="utf-8") as f:
        dati = _yaml().load(f)
    return dati if dati is not None else {}


def _testi_multiriga(obj):
    """Usa lo stile a blocco (|) per le stringhe su più righe, così le caption restano leggibili."""
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            obj[k] = _testi_multiriga(obj[k])
        return obj
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = _testi_multiriga(v)
        return obj
    if isinstance(obj, str) and "\n" in obj and not isinstance(obj, LiteralScalarString):
        testo = "\n".join(riga.rstrip() for riga in obj.split("\n"))
        return LiteralScalarString(testo)
    return obj


def salva_yaml(percorso: Path | str, dati) -> None:
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    dati = _testi_multiriga(dati)
    tmp = percorso.with_suffix(percorso.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        _yaml().dump(dati, f)
    tmp.replace(percorso)


def a_python(obj):
    """Converte gli oggetti ruamel in dict/list normali (per JSON)."""
    return json.loads(json.dumps(obj, default=str))


# ---------------------------------------------------------------- date

def oggi() -> dt.date:
    return dt.datetime.now(FUSO).date()


def adesso() -> dt.datetime:
    return dt.datetime.now(FUSO)


def mese_corrente() -> str:
    return oggi().strftime("%Y-%m")


def mese_prossimo() -> str:
    d = oggi().replace(day=1) + dt.timedelta(days=32)
    return d.strftime("%Y-%m")


def mese_precedente() -> str:
    d = oggi().replace(day=1) - dt.timedelta(days=1)
    return d.strftime("%Y-%m")


def valida_mese(mese: str) -> str:
    try:
        dt.datetime.strptime(mese, "%Y-%m")
    except ValueError:
        raise Errore(f"mese non valido '{mese}': usa il formato AAAA-MM, es. 2026-11")
    return mese


GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
GIORNI_BREVI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def nome_mese(mese: str) -> str:
    anno, m = mese.split("-")
    return f"{MESI[int(m) - 1]} {anno}"


def data_post(post) -> dt.datetime:
    """Data e ora del post nel fuso di Roma."""
    try:
        d = dt.date.fromisoformat(str(post.get("data")))
        h, m = str(post.get("ora") or "12:00").split(":")[:2]
        return dt.datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=FUSO)
    except (TypeError, ValueError):
        raise Errore(f"post {post.get('id')}: data '{post.get('data')}' o ora '{post.get('ora')}' non valida (AAAA-MM-GG e HH:MM)")


def contiene_segnaposto(post) -> bool:
    """True se il post contiene ancora [DA VERIFICARE ...] in un testo che verrebbe pubblicato."""
    media = post.get("media") or {}
    testi = [post.get("caption"), post.get("primo_commento"), post.get("alt_text"),
             json.dumps(a_python(media.get("testi_grafica") or []), ensure_ascii=False)]
    return any("[DA VERIFICARE" in str(t) for t in testi if t)


# ---------------------------------------------------------------- clienti

def cartella_cliente(slug: str) -> Path:
    p = CLIENTI / slug
    if not p.is_dir() or slug.startswith("_"):
        disponibili = ", ".join(elenco_slug()) or "nessuno"
        raise Errore(f"cliente '{slug}' non trovato. Clienti: {disponibili}")
    return p


def elenco_slug(solo_attivi: bool = False) -> list[str]:
    risultato = []
    if not CLIENTI.exists():
        return risultato
    for p in sorted(CLIENTI.iterdir()):
        if p.is_dir() and not p.name.startswith((".", "_")) and (p / "config.yaml").exists():
            if solo_attivi:
                try:
                    if not carica_yaml(p / "config.yaml").get("attivo", True):
                        continue
                except Exception:
                    continue
            risultato.append(p.name)
    return risultato


def carica_config(slug: str) -> dict:
    cfg = carica_yaml(cartella_cliente(slug) / "config.yaml")

    def sezione(nome, predefinita=None):
        if not isinstance(cfg.get(nome), dict):
            cfg[nome] = dict(predefinita or {})
        return cfg[nome]

    def valore(d, chiave, predefinito):
        if d.get(chiave) in (None, ""):
            d[chiave] = predefinito

    valore(cfg, "slug", slug)
    valore(cfg, "nome", slug)
    sezione("canali", {"instagram": True, "facebook": True})
    pub = sezione("pubblicazione")
    valore(pub, "fuso_orario", "Europe/Rome")
    valore(pub, "scheduler_profilo", slug)
    sezione("frequenza")
    drive = sezione("drive")
    valore(drive, "remote", "drive")
    valore(drive, "cartella", f"VOLTA/{cfg['nome']}")
    ai = sezione("ai")
    valore(ai, "tetto_mensile_eur", 5)
    valore(ai, "video_ai_mese_max", 2)
    sezione("approvazione")
    return cfg


def canali_attivi(cfg: dict) -> list[str]:
    return [c for c in CANALI if (cfg.get("canali") or {}).get(c)]


def carica_brand_kit(slug: str) -> dict:
    p = cartella_cliente(slug) / "brand-kit.yaml"
    if not p.exists():
        p = CLIENTI / "_modello" / "brand-kit.yaml"
    return a_python(carica_yaml(p))


# ---------------------------------------------------------------- piani

def percorso_piano(slug: str, mese: str) -> Path:
    return cartella_cliente(slug) / "piani" / f"{valida_mese(mese)}.yaml"


def carica_piano(percorso: Path | str) -> dict:
    piano = carica_yaml(percorso)
    piano.setdefault("post", [])
    if piano["post"] is None:
        piano["post"] = []
    return piano


def slug_da_piano(percorso: Path | str, piano: dict | None = None) -> str:
    """Il cliente è SEMPRE quello della cartella in cui sta il piano; 'cliente:' nel file deve coincidere."""
    percorso = Path(percorso).resolve()
    try:
        slug = percorso.relative_to(CLIENTI.resolve()).parts[0]
    except ValueError:
        raise Errore(f"il piano {percorso} non sta dentro clienti/<slug>/piani/")
    if piano and piano.get("cliente") and str(piano["cliente"]) != slug:
        raise Errore(f"il piano sta nella cartella '{slug}' ma dice 'cliente: {piano['cliente']}': correggi prima di continuare")
    return slug


def post_numerati(piano: dict) -> list[tuple[int, dict]]:
    """Post in ordine cronologico con il numero mostrato sul calendario (da 1)."""
    def chiave(p):
        return (str(p.get("data", "")), str(p.get("ora", "")), str(p.get("id", "")))
    ordinati = sorted(piano.get("post") or [], key=chiave)
    return [(i + 1, p) for i, p in enumerate(ordinati)]


def trova_post(piano: dict, riferimento: str) -> tuple[int, dict]:
    """Trova un post per numero (es. '5') o per id (es. '2026-11-03-a')."""
    numerati = post_numerati(piano)
    rif = str(riferimento).strip().lstrip("#")
    for n, p in numerati:
        if str(p.get("id")) == rif:
            return n, p
    if rif.isdigit():
        n = int(rif)
        for num, p in numerati:
            if num == n:
                return num, p
    raise Errore(f"post '{riferimento}' non trovato (numeri da 1 a {len(numerati)})")


def mediapronti(post) -> list[str]:
    return [str(x) for x in ((post.get("media") or {}).get("pronto") or []) if x]


# ---------------------------------------------------------------- media su Drive

def e_video(percorso: str | Path) -> bool:
    return Path(str(percorso)).suffix.lower() in ESTENSIONI_VIDEO


def e_foto(percorso: str | Path) -> bool:
    return Path(str(percorso)).suffix.lower() in ESTENSIONI_FOTO


class Media:
    """Accesso ai file di un cliente su Drive (via rclone) o in una cartella locale.

    Modalità locale: impostare VOLTA_MEDIA_LOCALE=/percorso, i file stanno in
    /percorso/<cartella del cliente>/... (utile per test e lavoro offline).
    """

    def __init__(self, slug: str):
        self.slug = slug
        self.cfg = carica_config(slug)
        self.cartella = str(self.cfg["drive"]["cartella"]).strip("/")
        self.remote = str(self.cfg["drive"]["remote"])
        self.locale = os.environ.get("VOLTA_MEDIA_LOCALE")
        self.cache = CACHE / "media" / slug

    # -- percorsi
    def _remoto(self, percorso: str = "") -> str:
        percorso = str(percorso).strip("/")
        base = f"{self.remote}:{self.cartella}"
        return f"{base}/{percorso}" if percorso else base

    def _locale_base(self) -> Path:
        return Path(self.locale) / self.cartella

    @staticmethod
    def _rclone(*args, timeout=600) -> subprocess.CompletedProcess:
        if not shutil.which("rclone"):
            raise Errore("rclone non è installato: controlla lo script di setup dell'ambiente (setup/ambiente-cloud.sh)")
        try:
            r = subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Errore(f"rclone non ha risposto in tempo ({' '.join(args[:2])})")
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).strip().splitlines()
            ultimo = msg[-1] if msg else "errore sconosciuto"
            if "didn't find section in config file" in ultimo or "not found in config" in ultimo:
                raise Errore("Drive non configurato: mancano le variabili RCLONE_CONFIG_DRIVE_* nell'ambiente (vedi docs/setup.md)")
            raise Errore(f"rclone: {ultimo}")
        return r

    # -- operazioni
    def elenca(self, sotto: str = "materiali", ricorsivo: bool = True) -> list[dict]:
        """Elenca i file sotto una cartella del cliente. Restituisce percorso relativo, dimensione, data."""
        sotto = sotto.strip("/")
        risultato = []
        if self.locale:
            base = self._locale_base()
            radice = base / sotto
            if not radice.exists():
                return []
            iteratore = radice.rglob("*") if ricorsivo else radice.glob("*")
            for p in iteratore:
                if p.is_file() and not p.name.startswith("."):
                    st = p.stat()
                    risultato.append({
                        "percorso": str(p.relative_to(base)).replace(os.sep, "/"),
                        "dimensione": st.st_size,
                        "modificato": dt.datetime.fromtimestamp(st.st_mtime, FUSO).isoformat(timespec="seconds"),
                        "id": "",
                    })
        else:
            args = ["lsjson", self._remoto(sotto), "--files-only", "--no-mimetype"]
            if ricorsivo:
                args.append("-R")
            try:
                r = self._rclone(*args)
            except Errore as e:
                if "directory not found" in str(e):
                    return []
                raise
            for voce in json.loads(r.stdout or "[]"):
                if voce.get("Name", "").startswith("."):
                    continue
                risultato.append({
                    "percorso": f"{sotto}/{voce['Path']}" if sotto else voce["Path"],
                    "dimensione": voce.get("Size", 0),
                    "modificato": voce.get("ModTime", ""),
                    "id": voce.get("ID", ""),
                })
        return sorted(risultato, key=lambda v: v["percorso"])

    def percorso_cache(self, percorso: str) -> Path:
        return self.cache / str(percorso).strip("/")

    def scarica(self, percorso: str) -> Path:
        """Restituisce un file locale per un percorso del cliente. Accetta anche percorsi locali esistenti."""
        p = Path(str(percorso)).expanduser()
        if p.is_absolute() and p.exists():
            return p
        if p.exists() and not str(percorso).startswith(("materiali/", "pronti/", "express/", "report/")):
            return p.resolve()
        rel = str(percorso).strip("/")
        if self.locale:
            sorgente = self._locale_base() / rel
            if not sorgente.exists():
                raise Errore(f"file non trovato nella cartella del cliente: {rel}")
            return sorgente
        dest = self.percorso_cache(rel)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._rclone("copyto", self._remoto(rel), str(dest))
        if not dest.exists():
            raise Errore(f"file non trovato su Drive: {rel}")
        return dest

    def carica(self, locale: Path | str, destinazione: str) -> str:
        """Carica un file locale nella cartella del cliente. Restituisce il percorso relativo."""
        locale = Path(locale)
        if not locale.exists():
            raise Errore(f"file da caricare non trovato: {locale}")
        dest = str(destinazione).strip("/")
        if self.locale:
            target = self._locale_base() / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            if locale.resolve() != target.resolve():
                shutil.copy2(locale, target)
        else:
            self._rclone("copyto", str(locale), self._remoto(dest))
        # tieni una copia in cache così le anteprime non riscaricano
        copia = self.percorso_cache(dest)
        copia.parent.mkdir(parents=True, exist_ok=True)
        if locale.resolve() != copia.resolve():
            shutil.copy2(locale, copia)
        return dest

    def crea_cartella(self, percorso: str) -> None:
        if self.locale:
            (self._locale_base() / percorso).mkdir(parents=True, exist_ok=True)
        else:
            self._rclone("mkdir", self._remoto(percorso))

    def link(self, percorso: str) -> str:
        """Link privato al file (si apre con l'account di Edoardo)."""
        rel = str(percorso).strip("/")
        if self.locale:
            return (self._locale_base() / rel).resolve().as_uri()
        if self.remote.startswith("drive"):
            r = self._rclone("lsjson", "--stat", "--no-mimetype", self._remoto(rel))
            voce = json.loads(r.stdout or "{}")
            if voce.get("ID"):
                return f"https://drive.google.com/file/d/{voce['ID']}/view"
        if self.remote.startswith("dropbox"):
            return f"https://www.dropbox.com/home/{self.cartella}/{rel}".replace(" ", "%20")
        return ""


# ---------------------------------------------------------------- spese AI

def percorso_costi(slug: str, mese: str) -> Path:
    return cartella_cliente(slug) / "costi" / f"{mese}.yaml"


def spesa_mese(slug: str, mese: str | None = None) -> dict:
    mese = mese or mese_corrente()
    p = percorso_costi(slug, mese)
    voci = []
    if p.exists():
        voci = list((carica_yaml(p) or {}).get("voci") or [])
    totale = round(sum(float(v.get("costo_eur") or 0) for v in voci), 4)
    video = sum(1 for v in voci if v.get("tipo") == "video")
    return {"mese": mese, "totale_eur": totale, "video": video, "voci": voci}


def registra_spesa(slug: str, voce: dict) -> None:
    mese = mese_corrente()
    p = percorso_costi(slug, mese)
    dati = carica_yaml(p) if p.exists() else {"mese": mese, "voci": []}
    dati.setdefault("voci", [])
    if dati["voci"] is None:
        dati["voci"] = []
    voce = {"quando": adesso().isoformat(timespec="seconds"), **voce}
    dati["voci"].append(voce)
    salva_yaml(p, dati)


def ffprobe_durata(percorso: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(percorso)],
            capture_output=True, text=True, timeout=60)
        return round(float(json.loads(r.stdout)["format"]["duration"]), 2)
    except Exception:
        return None


def ffprobe_dimensioni(percorso: Path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:stream_side_data=rotation", "-of", "json", str(percorso)],
            capture_output=True, text=True, timeout=60)
        s = json.loads(r.stdout)["streams"][0]
        w, h = int(s["width"]), int(s["height"])
        rot = 0
        for sd in s.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = abs(int(sd["rotation"]))
        return (h, w) if rot in (90, 270) else (w, h)
    except Exception:
        return None


def crea_anteprima(sorgente: Path, destinazione: Path, larghezza: int = 540) -> Path | None:
    """Miniatura JPEG leggera per la pagina calendario (per i video: un fotogramma)."""
    from PIL import Image, ImageOps
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    try:
        if e_video(sorgente):
            durata = ffprobe_durata(sorgente) or 2
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{min(1.0, durata / 3):.2f}", "-i", str(sorgente),
                            "-frames:v", "1", "-vf", f"scale={larghezza}:-2", "-q:v", "5", "-y", str(destinazione)],
                           capture_output=True, timeout=120)
            return destinazione if destinazione.exists() else None
        with Image.open(sorgente) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((larghezza, larghezza * 2))
            im.save(destinazione, quality=72, optimize=True)
        return destinazione
    except Exception:
        return None


def percorso_anteprima(slug: str, percorso_drive: str) -> Path:
    """Dove sta la miniatura di un file su Drive dentro site/ (es. pronti/2026-11/x.mp4 → site/slug/img/2026-11/x.jpg)."""
    rel = Path(str(percorso_drive).strip("/"))
    parti = rel.parts[1:] if rel.parts and rel.parts[0] in ("pronti", "materiali", "express") else rel.parts
    return SITE / slug / "img" / Path(*parti).with_suffix(".jpg")
