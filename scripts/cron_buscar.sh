#!/bin/sh
set -eu

# Cron arranca con un PATH mínimo; usamos el Python del repositorio para no depender de `uv`.
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$REPO_ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "error: no encuentro .venv/bin/python; ejecuta 'uv sync' primero." >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$REPO_ROOT"
"$PYTHON" -m gh_specify_finder.cli buscar --salida matched_repos/resultados.csv

git add -A matched_repos
if ! git diff --cached --quiet; then
  git commit -m "Actualizar resultados Spec Kit en matched_repos"
  git push
fi
