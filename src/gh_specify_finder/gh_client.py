from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

from .models import MatchRecord
from .parser import normalizar_registros


@dataclass(slots=True)
class GhSearchResult:
    registros: list
    comando: list[str]
    stdout: str
    stderr: str


def ejecutar_busqueda_gh(
    consulta: str,
    limite: int = 100,
    incluir_texto: bool = False,
    extra_args: Sequence[str] | None = None,
) -> GhSearchResult:
    if shutil.which("gh") is None:
        raise RuntimeError("No se encontró 'gh' en PATH.")

    campos = ["repository", "path", "url"]
    if incluir_texto:
        campos.append("textMatches")

    comando = ["gh", "search", "code", consulta, "--limit", str(limite), "--json", ",".join(campos)]
    if extra_args:
        comando.extend(extra_args)

    proc = subprocess.run(comando, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "La búsqueda con gh falló.")

    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("La salida de gh no fue JSON válido.") from exc

    if isinstance(parsed, dict):
        items = parsed.get("items") or parsed.get("data") or parsed.get("results") or []
    else:
        items = parsed

    registros = normalizar_registros(items, origen="gh search code")
    return GhSearchResult(registros=registros, comando=comando, stdout=proc.stdout, stderr=proc.stderr)


def enriquecer_estrellas(registros: list[MatchRecord]) -> list[MatchRecord]:
    if shutil.which("gh") is None:
        return registros

    for registro in registros:
        if registro.estrellas is not None or not registro.nombre_repo:
            continue

        comando = ["gh", "repo", "view", registro.nombre_repo, "--json", "stargazerCount,url,nameWithOwner"]
        proc = subprocess.run(comando, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            continue

        try:
            datos = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue

        if isinstance(datos, dict):
            if registro.estrellas is None:
                estrellas = datos.get("stargazerCount") or datos.get("stargazersCount")
                try:
                    registro.estrellas = int(estrellas) if estrellas is not None else None
                except (TypeError, ValueError):
                    registro.estrellas = None
            if not registro.url_repo:
                registro.url_repo = datos.get("url") or registro.url_repo

    return registros
