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

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
  set +a
fi

if [ -z "${GH_TOKEN-}" ] && [ -z "${GITHUB_TOKEN-}" ]; then
  if token=$(gh auth token 2>/dev/null); then
    if [ -z "$token" ]; then
      echo "error: gh auth token no devolvió ningún token; pon GH_TOKEN o GITHUB_TOKEN en .env." >&2
      exit 1
    fi
    export GH_TOKEN="$token"
    export GITHUB_TOKEN="$token"
  else
    echo "error: no puedo obtener un token de gh; pon GH_TOKEN o GITHUB_TOKEN en .env." >&2
    exit 1
  fi
fi

cd "$REPO_ROOT"
"$PYTHON" -m gh_specify_finder.cli buscar --salida matched_repos/resultados.csv

git add -A matched_repos
if ! git diff --cached --quiet; then
  TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
  git commit -m "Actualizar resultados Spec Kit en matched_repos ($TIMESTAMP)"
  git push
fi
