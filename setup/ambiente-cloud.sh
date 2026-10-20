#!/usr/bin/env bash
# Script di setup per l'ambiente cloud di Claude Code (Ubuntu 24.04, gira come root prima di ogni nuova sessione).
# Da incollare nel campo "Setup script" dell'ambiente su claude.ai/code. Il risultato viene messo in cache:
# le sessioni successive partono già pronte.
set -e
export DEBIAN_FRONTEND=noninteractive

# programmi: video, accesso a Drive/Dropbox, font (anche emoji) per le grafiche
( apt-get update -qq && apt-get install -y -qq ffmpeg rclone fonts-dejavu fonts-liberation fonts-noto-color-emoji >/dev/null ) &

# librerie Python
( python3 -m pip install -q ruamel.yaml jinja2 pillow pillow-heif requests markdown playwright 2>/dev/null \
  || python3 -m pip install -q --break-system-packages ruamel.yaml jinja2 pillow pillow-heif requests markdown playwright ) &

wait

# browser usato per trasformare i template HTML in immagini
python3 -m playwright install --with-deps chromium >/dev/null

echo "VOLTA Social: ambiente pronto"
