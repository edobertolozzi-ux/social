"""Funzioni video condivise da reel_da_foto.py e monta_video.py (ffmpeg)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from comune import CACHE, Errore, Media

W, H, FPS = 1080, 1920, 30


def ffmpeg(args: list[str], timeout: int = 1800) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Errore("ffmpeg ci sta mettendo troppo: prova con meno clip o più corte")
    if r.returncode != 0:
        righe = [x for x in (r.stderr or "").strip().splitlines() if x.strip()]
        raise Errore("ffmpeg: " + (" | ".join(righe[-3:]) if righe else "errore sconosciuto"))


def ha_audio(percorso: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "json", str(percorso)], capture_output=True, text=True, timeout=60)
    try:
        return bool(json.loads(r.stdout).get("streams"))
    except Exception:
        return False


def grafica_video(slug: str, template: str, testi: dict, png: bool, nome: str) -> Path:
    """Crea con i template una sovrapposizione trasparente (png=True) o un cartello 9:16."""
    from grafica import Renderer
    out = CACHE / "lavoro" / slug / "_video" / nome
    with Renderer(slug) as r:
        return r.render(template, "9:16", testi, None, out, png=png)


def file_locale(media: Media, percorso: str | None) -> Path | None:
    if not percorso:
        return None
    return media.scarica(percorso)


def codifica_finale() -> list[str]:
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart"]


def filtro_audio_musica(indice: int, durata: float, volume: float) -> str:
    fine = max(durata - 1.2, 0)
    return (f"[{indice}:a]atrim=0:{durata:.2f},asetpts=PTS-STARTPTS,volume={volume},"
            f"afade=t=in:d=0.4,afade=t=out:st={fine:.2f}:d=1.2,aresample=44100,"
            f"aformat=channel_layouts=stereo[musica]")
