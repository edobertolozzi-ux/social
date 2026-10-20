#!/usr/bin/env bash
# Salva il lavoro: commit di tutte le modifiche e push sul branch main (anche dalle sessioni cloud).
# Uso: bash scripts/salva.sh "messaggio"
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1

messaggio="${1:-Aggiornamento VOLTA Social}"
git add -A
if git diff --cached --quiet; then
  echo "Niente di nuovo da salvare."
else
  git commit -q -m "$messaggio" || { echo "ERRORE: commit non riuscito"; exit 1; }
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Salvato in locale (nessun repository remoto configurato)."
  exit 0
fi

for tentativo in 1 2 3; do
  git fetch -q origin main 2>/dev/null || true
  if git rev-parse -q --verify origin/main >/dev/null; then
    if ! git rebase -q origin/main; then
      git rebase --abort
      echo "ERRORE: conflitto con modifiche fatte da un'altra sessione."
      echo "Risolvi: git pull --rebase origin main, sistema i file in conflitto (di solito un piano .yaml), poi rilancia."
      exit 1
    fi
  fi
  if git push -q origin HEAD:main; then
    echo "Salvato su main."
    exit 0
  fi
  sleep 3
done
echo "ERRORE: push su main non riuscito dopo 3 tentativi (controlla la connessione a GitHub)."
exit 1
