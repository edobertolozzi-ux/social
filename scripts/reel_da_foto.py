#!/usr/bin/env python3
"""Reel verticale (9:16) a partire da foto: zoom lento, dissolvenze, titolo iniziale, cartello finale, musica.

Esempio:
  reel_da_foto.py --cliente bistrot --foto materiali/a.jpg materiali/b.jpg materiali/c.jpg \
      --titolo "Il pescato di oggi" --chiusura "Prenota il tuo tavolo" --musica materiali/audio/brano.mp3 \
      --out .cache/lavoro/bistrot/2026-11-05-a.mp4

Le foto possono essere percorsi su Drive (materiali/...) o file locali. Durata consigliata: 7-20 secondi.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from comune import CACHE, Errore, Media, esegui_main, ffprobe_durata, info
from grafica import ritaglia_immagine
from video import FPS, H, W, codifica_finale, ffmpeg, file_locale, filtro_audio_musica, grafica_video

MOVIMENTI = [
    # (zoom iniziale, zoom finale, ancora x, ancora y)
    (1.00, 1.12, 0.5, 0.5),
    (1.12, 1.00, 0.5, 0.45),
    (1.02, 1.14, 0.35, 0.5),
    (1.14, 1.02, 0.65, 0.5),
]


def costruisci(a) -> Path:
    media = Media(a.cliente)
    if len(a.foto) < 2:
        raise Errore("servono almeno 2 foto")
    if len(a.foto) > 20:
        raise Errore("massimo 20 foto")
    lavoro = CACHE / "lavoro" / a.cliente / "_reel"
    lavoro.mkdir(parents=True, exist_ok=True)

    # 1. foto al formato 9:16 (ritaglio o sfondo sfocato se si perderebbe troppo)
    immagini = []
    for i, f in enumerate(a.foto):
        locale = media.scarica(f)
        immagini.append(ritaglia_immagine(locale, "9:16", lavoro / f"foto-{i:02d}.jpg"))

    segmenti = [(img, a.secondi, True) for img in immagini]
    if a.chiusura is not None:
        cartello = grafica_video(a.cliente, "chiusura", {"titolo": a.chiusura, "sottotitolo": a.chiusura_sotto or ""},
                                 png=False, nome="chiusura.jpg")
        segmenti.append((cartello, max(2.0, a.secondi), False))

    t = min(a.transizione, a.secondi / 2)
    ingressi, filtri = [], []
    for i, (img, durata, movimento) in enumerate(segmenti):
        ingressi += ["-i", str(img)]
        frames = int(round(durata * FPS))
        if movimento:
            z0, z1, ax, ay = MOVIMENTI[i % len(MOVIMENTI)]
            passo = (z1 - z0) / max(frames - 1, 1)
            z = f"if(eq(on,0),{z0},{z0}+{passo:.6f}*on)"
            filtri.append(
                f"[{i}:v]scale={W * 2}:{H * 2},zoompan=z='{z}':d={frames}:s={W}x{H}:fps={FPS}:"
                f"x='(iw-iw/zoom)*{ax}':y='(ih-ih/zoom)*{ay}',setsar=1,format=yuv420p[v{i}]")
        else:
            filtri.append(f"[{i}:v]loop=loop={frames - 1}:size=1:start=0,setpts=N/{FPS}/TB,"
                          f"fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[v{i}]")

    # 2. dissolvenze in catena
    accumulata = segmenti[0][1]
    corrente = "v0"
    for i in range(1, len(segmenti)):
        offset = accumulata - t
        uscita = f"x{i}"
        filtri.append(f"[{corrente}][v{i}]xfade=transition=fade:duration={t:.2f}:offset={offset:.2f}[{uscita}]")
        accumulata = accumulata + segmenti[i][1] - t
        corrente = uscita
    durata_totale = accumulata

    # 3. titolo nei primi secondi
    n = len(segmenti)
    if a.titolo:
        sovrapposizione = grafica_video(a.cliente, "overlay-titolo",
                                        {"titolo": a.titolo, "sottotitolo": a.sottotitolo or ""}, png=True,
                                        nome="titolo.png")
        ingressi += ["-i", str(sovrapposizione)]
        fine = min(2.8, durata_totale)
        filtri.append(f"[{n}:v]format=rgba,fade=t=out:st={fine - 0.4:.2f}:d=0.4:alpha=1[tit]")
        filtri.append(f"[{corrente}][tit]overlay=0:0:enable='lte(t,{fine:.2f})'[vt]")
        corrente = "vt"
        n += 1

    # 4. audio: musica o silenzio
    musica = file_locale(media, a.musica)
    if musica:
        ingressi += ["-i", str(musica)]
        filtri.append(filtro_audio_musica(n, durata_totale, a.volume))
    else:
        ingressi += ["-f", "lavfi", "-t", f"{durata_totale:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        filtri.append(f"[{n}:a]anull[musica]")

    out = Path(a.out) if a.out else CACHE / "lavoro" / a.cliente / "reel.mp4"
    out = out.with_suffix(".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg([*ingressi, "-filter_complex", ";".join(filtri), "-map", f"[{corrente}]", "-map", "[musica]",
            "-t", f"{durata_totale:.2f}", *codifica_finale(), str(out)])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--foto", nargs="+", required=True)
    ap.add_argument("--out")
    ap.add_argument("--secondi", type=float, default=2.6, help="durata di ogni foto (default 2.6)")
    ap.add_argument("--transizione", type=float, default=0.5, help="durata della dissolvenza (default 0.5)")
    ap.add_argument("--titolo", help="gancio nei primi secondi")
    ap.add_argument("--sottotitolo")
    ap.add_argument("--chiusura", nargs="?", const="", default=None,
                    help="aggiunge il cartello finale; testo opzionale, es. 'Prenota il tuo tavolo'")
    ap.add_argument("--chiusura-sotto", help="seconda riga del cartello (default: firma del brand kit)")
    ap.add_argument("--musica", help="file audio (Drive o locale): solo brani con licenza d'uso")
    ap.add_argument("--volume", type=float, default=0.8)
    a = ap.parse_args()
    out = costruisci(a)
    info(f"{out}  ({ffprobe_durata(out)}s)")
    return 0


if __name__ == "__main__":
    esegui_main(main)
