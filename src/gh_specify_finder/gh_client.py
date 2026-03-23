from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Sequence

from .models import MatchRecord
from .parser import normalizar_registros

DEFAULT_SEARCH_LIMIT = 10000
SEARCH_PAGE_SIZE = 100
DEFAULT_PAGE_DELAY = 1.0
SEARCH_VARIANTS = ("", "in:file", "in:path")
STAR_BATCH_SIZE = 25
DEFAULT_RATE_LIMIT_RETRIES = 6
DEFAULT_RATE_LIMIT_WAIT = 30.0
DEFAULT_STARS_TIMEOUT_SECONDS = 10.0


@dataclass(slots=True)
class GhSearchResult:
    registros: list
    comando: list[str]
    stdout: str
    stderr: str
    advertencia: str | None = None


def _extraer_items_paginate(parsed: object) -> list[object]:
    if isinstance(parsed, list):
        items: list[object] = []
        for page in parsed:
            items.extend(_extraer_items_paginate(page))
        return items

    if isinstance(parsed, dict):
        items = parsed.get("items") or parsed.get("data") or parsed.get("results") or []
        if isinstance(items, list):
            return items
        if items:
            return [items]
        return []

    if parsed is None:
        return []

    return [parsed]


def _es_error_rate_limit(stderr: str) -> bool:
    texto = stderr.lower()
    return "api rate limit exceeded" in texto or "rate limit exceeded" in texto


def _es_error_limite_mil(stderr: str) -> bool:
    texto = stderr.lower()
    return "cannot access beyond the first 1000 results" in texto or "beyond the first 1000" in texto


def _mensaje_rate_limit() -> str:
    return (
        "GitHub devolvió un rate limit durante la búsqueda. "
        "Se guardaron los resultados parciales obtenidos hasta ese momento. "
        "Vuelve a ejecutar más tarde o reduce la consulta con --limite."
    )


def _mensaje_limite_mil() -> str:
    return (
        "GitHub limitó esta consulta a las primeras 1000 coincidencias. "
        "Se conservaron los resultados obtenidos y se continuó con variantes de búsqueda."
    )


def _partes_repositorio(nombre_repo: str) -> tuple[str, str] | None:
    nombre_repo = (nombre_repo or "").strip()
    if "/" not in nombre_repo:
        return None
    owner, name = nombre_repo.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        return None
    return owner, name


def _construir_consultas(consulta: str) -> list[str]:
    texto = consulta.strip()
    if not texto:
        return [consulta]

    if "in:file" in texto or "in:path" in texto:
        return [texto]

    consultas = [texto]
    for variante in SEARCH_VARIANTS[1:]:
        consultas.append(f"{texto} {variante}")
    return consultas


def _formar_query_estrellas(registros: list[MatchRecord]) -> tuple[str, list[tuple[str, MatchRecord]]]:
    lineas = ["query {"]
    candidatos: list[tuple[str, MatchRecord]] = []

    for registro in registros:
        partes = _partes_repositorio(registro.nombre_repo)
        if partes is None:
            continue
        owner, name = partes
        alias = f"r{len(candidatos)}"
        lineas.append(
            f'{alias}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) '
            f'{{ nameWithOwner url stargazerCount }}'
        )
        candidatos.append((alias, registro))

    lineas.append("}")
    return "\n".join(lineas), candidatos


def _aplicar_estrellas_batch(registros: list[MatchRecord]) -> None:
    pendientes = [registro for registro in registros if registro.estrellas is None and _partes_repositorio(registro.nombre_repo)]
    if not pendientes:
        return

    for inicio in range(0, len(pendientes), STAR_BATCH_SIZE):
        lote = pendientes[inicio : inicio + STAR_BATCH_SIZE]
        query, candidatos = _formar_query_estrellas(lote)
        if not candidatos:
            continue

        try:
            proc = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={query}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=DEFAULT_STARS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            continue

        if proc.returncode != 0:
            continue

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            continue

        for alias, registro in candidatos:
            repositorio = data.get(alias)
            if not isinstance(repositorio, dict):
                continue
            if registro.estrellas is None:
                estrellas = repositorio.get("stargazerCount") or repositorio.get("stargazersCount")
                try:
                    registro.estrellas = int(estrellas) if estrellas is not None else None
                except (TypeError, ValueError):
                    registro.estrellas = None
            if not registro.url_repo:
                registro.url_repo = repositorio.get("url") or registro.url_repo


def _ejecutar_consulta_paginated(
    consulta: str,
    espera_segundos: float,
    reintentos_rate_limit: int,
    espera_rate_limit: float,
    extra_args: Sequence[str] | None,
) -> tuple[list[object], str, str, str | None]:
    items: list[object] = []
    stdout_total: list[str] = []
    stderr_total: list[str] = []
    pagina = 1
    advertencia = None
    comando_base = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/code",
        "-f",
        f"q={consulta}",
        "-f",
        f"per_page={SEARCH_PAGE_SIZE}",
    ]
    if extra_args:
        comando_base.extend(extra_args)

    while True:
        comando = [*comando_base, "-f", f"page={pagina}"]
        proc = subprocess.run(comando, capture_output=True, text=True, check=False)
        while proc.returncode != 0 and _es_error_rate_limit(proc.stderr) and reintentos_rate_limit > 0:
            reintentos_rate_limit -= 1
            if espera_rate_limit > 0:
                time.sleep(espera_rate_limit)
            proc = subprocess.run(comando, capture_output=True, text=True, check=False)
        stdout_total.append(proc.stdout)
        if proc.returncode != 0:
            stderr_total.append(proc.stderr)
            if _es_error_rate_limit(proc.stderr):
                advertencia = _mensaje_rate_limit()
                break
            if _es_error_limite_mil(proc.stderr):
                advertencia = _mensaje_limite_mil()
                break
            raise RuntimeError(proc.stderr.strip() or "La búsqueda con gh falló.")

        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("La salida de gh no fue JSON válido.") from exc

        page_items = _extraer_items_paginate(parsed)
        items.extend(page_items)
        if len(page_items) < SEARCH_PAGE_SIZE:
            break

        pagina += 1
        if espera_segundos > 0:
            time.sleep(espera_segundos)

    return items, "\n".join(stdout_total), "\n".join(stderr_total), advertencia


def ejecutar_busqueda_gh(
    consulta: str,
    limite: int = DEFAULT_SEARCH_LIMIT,
    espera_segundos: float = DEFAULT_PAGE_DELAY,
    reintentos_rate_limit: int = DEFAULT_RATE_LIMIT_RETRIES,
    espera_rate_limit: float = DEFAULT_RATE_LIMIT_WAIT,
    incluir_texto: bool = False,
    extra_args: Sequence[str] | None = None,
) -> GhSearchResult:
    if shutil.which("gh") is None:
        raise RuntimeError("No se encontró 'gh' en PATH.")

    items: list[object] = []
    stderr_total: list[str] = []
    stdout_total: list[str] = []
    advertencia = None

    consultas = _construir_consultas(consulta)
    for indice, consulta_actual in enumerate(consultas):
        if indice > 0 and espera_segundos > 0:
            time.sleep(espera_segundos)

        consulta_items, consulta_stdout, consulta_stderr, consulta_advertencia = _ejecutar_consulta_paginated(
            consulta_actual,
            espera_segundos=espera_segundos,
            reintentos_rate_limit=reintentos_rate_limit,
            espera_rate_limit=espera_rate_limit,
            extra_args=extra_args,
        )
        items.extend(consulta_items)
        stdout_total.append(consulta_stdout)
        if consulta_stderr:
            stderr_total.append(consulta_stderr)
        if consulta_advertencia:
            advertencia = consulta_advertencia
            break

    if limite is not None:
        registros = normalizar_registros(items, origen="gh search code")
        registros = registros[:limite]
    else:
        registros = normalizar_registros(items, origen="gh search code")

    return GhSearchResult(
        registros=registros,
        comando=["gh", "api", "-X", "GET", "search/code", "-f", f"q={consulta}", "-f", f"per_page={SEARCH_PAGE_SIZE}", "-f", "page=1"],
        stdout="\n".join(stdout_total),
        stderr="\n".join(stderr_total),
        advertencia=advertencia,
    )


def enriquecer_estrellas(registros: list[MatchRecord]) -> list[MatchRecord]:
    if shutil.which("gh") is None:
        return registros

    _aplicar_estrellas_batch(registros)

    return registros
