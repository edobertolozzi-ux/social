#!/usr/bin/env python3
"""Montaggio dei video del cliente in un reel verticale 9:16: tagli, unione, titolo, sottotitoli, musica, cartello finale.

Esempio:
  monta_video.py --cliente bistrot \
      --clip "materiali/2026-10/VID_1.mp4@2-7" "materiali/2026-10/VID_2.mp4@0-4.5" \
      --titolo "Dietro le quinte" --sottotitoli sottotitoli.srt --musica materiali/audio/brano.mp3 \
      --volume-musica 0.25 --chiusura "Ci vediamo stasera" --out .cache/lavoro/bistrot/2026-11-08-a.mp4

Clip: "percorso" oppure "percorso@inizio-fine" in secondi. I video orizzontali vengono messi su sfondo sfocato,
quelli verticali riempiono lo schermo (--adatta riempi|sfocato|auto per cambiare).
Sottotitoli: file .srt (Drive o locale); con --trascrivi li genera da soli se è installato faster-whisper.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from comune import CACHE, Errore, Media, esegui_main, ffprobe_dimensioni, ffprobe_durata, info, avviso
from video import FPS, H, W, codifica_finale, ffmpeg, file_locale, filtro_audio_musica, grafica_video, ha_audio

RE_CLIP = re.compile(r"^(?P<p>.+?)(?:@(?P<i>\d+(?:\.\d+)?)-(?P<f>\d+(?:\.\d+)?))?$")


def _clip(spec: str):
    m = RE_CLIP.match(spec.strip())
    if not m:
        raise Errore(f"clip non valida: {spec}")
    inizio = float(m.group("i")) if m.group("i") else None
    fine = float(m.group("f")) if m.group("f") else None
    if inizio is not None and fine is not None and fine <= inizio:
        raise Errore(f"clip {spec}: la fine deve essere dopo l'inizio")
    return m.group("p"), inizio, fine


def _srt_escape(p: Path) -> str:
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def trascrivi(video: Path, out_srt: Path) -> Path:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise Errore("per --trascrivi serve faster-whisper (pip install faster-whisper); altrimenti passa un file .srt")
    modello = WhisperModel("small", device="cpu", compute_type="int8")
    segmenti, _ = modello.transcribe(str(video), language="it", vad_filter=True)

    def ts(s):
        h, r = divmod(s, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    righe = []
    for i, seg in enumerate(segmenti, 1):
        righe.append(f"{i}\n{ts(seg.start)} --> {ts(seg.end)}\n{seg.text.strip()}\n")
    out_srt.write_text("\n".join(righe), encoding="utf-8")
    return out_srt


def costruisci(a) -> Path:
    media = Media(a.cliente)
    lavoro = CACHE / "lavoro" / a.cliente / "_montaggio"
    lavoro.mkdir(parents=True, exist_ok=True)

    ingressi, filtri, etichette_v, etichette_a = [], [], [], []
    durata_totale = 0.0
    idx = 0
    for spec in a.clip:
        percorso, inizio, fine = _clip(spec)
        locale = media.scarica(percorso)
        durata_file = ffprobe_durata(locale)
        dims = ffprobe_dimensioni(locale)
        if not durata_file or not dims:
            raise Errore(f"{percorso}: non è un video leggibile")
        inizio = inizio or 0.0
        fine = min(fine or durata_file, durata_file)
        if inizio >= durata_file:
            raise Errore(f"{percorso}: inizio {inizio}s oltre la durata del video ({durata_file}s)")
        durata = fine - inizio
        ingressi += ["-ss", f"{inizio:.2f}", "-t", f"{durata:.2f}", "-i", str(locale)]
        verticale = dims[1] >= dims[0]
        modo = a.adatta if a.adatta != "auto" else ("riempi" if verticale else "sfocato")
        if modo == "riempi":
            filtri.append(f"[{idx}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                          f"fps={FPS},setsar=1,format=yuv420p[c{idx}]")
        else:
            filtri.append(f"[{idx}:v]split=2[f{idx}][p{idx}];"
                          f"[f{idx}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,"
                          f"eq=brightness=-0.12[fb{idx}];"
                          f"[p{idx}]scale={W}:-2[pp{idx}];"
                          f"[fb{idx}][pp{idx}]overlay=(W-w)/2:(H-h)/2,fps={FPS},setsar=1,format=yuv420p[c{idx}]")
        etichette_v.append(f"[c{idx}]")
        if ha_audio(locale) and not a.senza_audio_originale:
            filtri.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{idx}]")
        else:
            filtri.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{durata:.2f}[a{idx}]")
        etichette_a.append(f"[a{idx}]")
        durata_totale += durata
        idx += 1

    if a.chiusura is not None:
        cartello = grafica_video(a.cliente, "chiusura", {"titolo": a.chiusura}, png=False, nome="chiusura.jpg")
        durata = 2.2
        ingressi += ["-loop", "1", "-t", f"{durata}", "-i", str(cartello)]
        filtri.append(f"[{idx}:v]scale={W}:{H},fps={FPS},setsar=1,format=yuv420p,fade=t=in:d=0.3[c{idx}]")
        filtri.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{durata}[a{idx}]")
        etichette_v.append(f"[c{idx}]")
        etichette_a.append(f"[a{idx}]")
        durata_totale += durata
        idx += 1

    n = len(etichette_v)
    coppie = "".join(v + au for v, au in zip(etichette_v, etichette_a))
    filtri.append(f"{coppie}concat=n={n}:v=1:a=1[vcat][acat]")
    corrente_v, corrente_a = "vcat", "acat"

    # sottotitoli
    srt = None
    if a.trascrivi:
        provvisorio = lavoro / "senza-sottotitoli.mp4"
        ffmpeg([*ingressi, "-filter_complex", ";".join(filtri), "-map", f"[{corrente_v}]", "-map", f"[{corrente_a}]",
                *codifica_finale(), str(provvisorio)])
        srt = trascrivi(provvisorio, lavoro / "sottotitoli.srt")
        info(f"Sottotitoli generati: {srt} (controllali prima di pubblicare)")
    elif a.sottotitoli:
        srt = file_locale(media, a.sottotitoli)
    if srt:
        stile = "FontName=DejaVu Sans,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=70,Alignment=2"
        filtri.append(f"[{corrente_v}]subtitles='{_srt_escape(srt)}':force_style='{stile}'[vsub]")
        corrente_v = "vsub"

    # titolo
    if a.titolo:
        sovra = grafica_video(a.cliente, "overlay-titolo", {"titolo": a.titolo, "sottotitolo": a.sottotitolo or ""},
                              png=True, nome="titolo-montaggio.png")
        ingressi += ["-i", str(sovra)]
        fine = min(2.8, durata_totale)
        filtri.append(f"[{idx}:v]format=rgba,fade=t=out:st={fine - 0.4:.2f}:d=0.4:alpha=1[tit]")
        filtri.append(f"[{corrente_v}][tit]overlay=0:0:enable='lte(t,{fine:.2f})'[vtit]")
        corrente_v = "vtit"
        idx += 1

    # musica
    musica = file_locale(media, a.musica)
    if musica:
        ingressi += ["-i", str(musica)]
        filtri.append(filtro_audio_musica(idx, durata_totale, a.volume_musica))
        filtri.append(f"[{corrente_a}][musica]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix]")
        corrente_a = "amix"
        idx += 1

    if durata_totale > 90:
        avviso(f"durata {durata_totale:.0f}s: i reel più efficaci stanno sotto i 30-45 secondi")
    out = Path(a.out) if a.out else CACHE / "lavoro" / a.cliente / "montaggio.mp4"
    out = out.with_suffix(".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg([*ingressi, "-filter_complex", ";".join(filtri), "-map", f"[{corrente_v}]", "-map", f"[{corrente_a}]",
            "-t", f"{durata_totale:.2f}", *codifica_finale(), str(out)])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--clip", nargs="+", required=True, help='"percorso" o "percorso@inizio-fine"')
    ap.add_argument("--out")
    ap.add_argument("--adatta", choices=["auto", "riempi", "sfocato"], default="auto")
    ap.add_argument("--titolo"); ap.add_argument("--sottotitolo")
    ap.add_argument("--sottotitoli", help="file .srt da imprimere nel video")
    ap.add_argument("--trascrivi", action="store_true", help="genera i sottotitoli dall'audio (serve faster-whisper)")
    ap.add_argument("--musica", help="file audio con licenza d'uso"); ap.add_argument("--volume-musica", type=float, default=0.25)
    ap.add_argument("--senza-audio-originale", action="store_true")
    ap.add_argument("--chiusura", nargs="?", const="", default=None, help="cartello finale, testo opzionale")
    a = ap.parse_args()
    out = costruisci(a)
    info(f"{out}  ({ffprobe_durata(out)}s)")
    return 0


if __name__ == "__main__":
    esegui_main(main)
