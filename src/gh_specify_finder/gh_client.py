"""
Cliente de GitHub CLI (`gh`) para búsqueda de código.

Ejecuta varias consultas a `search/code` (fragmentación por subrutas bajo `.specify` más
una consulta amplia y la vía `.gitignore`), fusiona ítems y agrupa por repositorio.
La API solo devuelve hasta 1000 coincidencias por consulta; varias consultas suman cobertura.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .criteria import es_ruta_archivo_gitignore, es_ruta_directorio_specify
from .models import MatchRecord
from .parser import _as_dict, _extraer_ruta, normalizar_registros

DEFAULT_SEARCH_LIMIT = 10000
SEARCH_PAGE_SIZE = 100
DEFAULT_PAGE_DELAY = 1.0
# La API de búsqueda de código limita ~9 peticiones/min; entre consultas distintas conviene pausar más.
DEFAULT_ESPERA_ENTRE_CONSULTAS = 7.0

# Subrutas habituales de Spec Kit (cada una cuenta como consulta aparte, hasta 1000 hits c/u).
CONSULTAS_DIRECTORIO_FRAGMENTADAS: tuple[str, ...] = (
    "path:.specify/memory",
    "path:.specify/scripts",
    "path:.specify/templates",
    "path:.specify/extensions",
    "path:.specify",
)
# Archivos .gitignore que contienen la cadena literal ".specify".
CONSULTA_GITIGNORE_SPECIFY = 'filename:.gitignore ".specify"'

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
    info_metricas: list[str] = field(default_factory=list)


def _total_count_desde_respuesta(parsed: object) -> int | None:
    if isinstance(parsed, dict):
        tc = parsed.get("total_count")
        if isinstance(tc, int):
            return tc
    return None


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
        "Se conservaron las coincidencias ya obtenidas para esa consulta."
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
) -> tuple[list[object], str, str, str | None, int | None]:
    items: list[object] = []
    stdout_total: list[str] = []
    stderr_total: list[str] = []
    pagina = 1
    advertencia = None
    total_count_api: int | None = None
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

        if pagina == 1:
            total_count_api = _total_count_desde_respuesta(parsed)

        page_items = _extraer_items_paginate(parsed)
        items.extend(page_items)
        if len(page_items) < SEARCH_PAGE_SIZE:
            break

        pagina += 1
        if espera_segundos > 0:
            time.sleep(espera_segundos)

    return items, "\n".join(stdout_total), "\n".join(stderr_total), advertencia, total_count_api


def _filtrar_items_por_ruta(items: list[object], criterio_ruta: Callable[[str], bool]) -> list[object]:
    salida: list[object] = []
    for item in items:
        data = _as_dict(item)
        ruta = _extraer_ruta(data)
        if ruta and criterio_ruta(ruta):
            salida.append(item)
    return salida


def _combinar_advertencias(*avisos: str | None) -> str | None:
    partes = [a.strip() for a in avisos if a and a.strip()]
    if not partes:
        return None
    return " ".join(partes) if len(partes) == 1 else " | ".join(partes)


def _resumir_metrica_consulta(consulta_q: str, total_count: int | None, n_items: int, n_filtrados: int) -> str:
    q_corta = consulta_q if len(consulta_q) <= 72 else consulta_q[:69] + "..."
    if total_count is not None:
        cap_msg = f"GitHub total_count={total_count} coincidencias de código"
        if total_count > 1000:
            cap_msg += " (la API solo permite recuperar 1000 por consulta)"
        return f"{q_corta} → {cap_msg}; ítems obtenidos={n_items}, tras filtro={n_filtrados}"
    return f"{q_corta} → ítems obtenidos={n_items}, tras filtro={n_filtrados}"


def ejecutar_busqueda_specify_kit(
    limite: int = DEFAULT_SEARCH_LIMIT,
    espera_segundos: float = DEFAULT_PAGE_DELAY,
    espera_entre_consultas: float = DEFAULT_ESPERA_ENTRE_CONSULTAS,
    reintentos_rate_limit: int = DEFAULT_RATE_LIMIT_RETRIES,
    espera_rate_limit: float = DEFAULT_RATE_LIMIT_WAIT,
    extra_args: Sequence[str] | None = None,
) -> GhSearchResult:
    """
    Busca repositorios con carpeta `.specify` (varias consultas fragmentadas + filtro) o
    `.gitignore` con `.specify`. Une todo, deduplica por repo y aplica ``limite``.
    """
    if shutil.which("gh") is None:
        raise RuntimeError("No se encontró 'gh' en PATH.")

    stderr_total: list[str] = []
    stdout_total: list[str] = []
    items_totales: list[object] = []
    advertencias: list[str | None] = []
    info_metricas: list[str] = []

    consultas: list[tuple[str, Callable[[str], bool]]] = [
        *[(q, es_ruta_directorio_specify) for q in CONSULTAS_DIRECTORIO_FRAGMENTADAS],
        (CONSULTA_GITIGNORE_SPECIFY, es_ruta_archivo_gitignore),
    ]

    for indice, (consulta_q, filtro_ruta) in enumerate(consultas):
        if indice > 0 and espera_entre_consultas > 0:
            time.sleep(espera_entre_consultas)

        consulta_items, consulta_stdout, consulta_stderr, consulta_advertencia, total_count_api = _ejecutar_consulta_paginated(
            consulta_q,
            espera_segundos=espera_segundos,
            reintentos_rate_limit=reintentos_rate_limit,
            espera_rate_limit=espera_rate_limit,
            extra_args=extra_args,
        )
        filtrados = _filtrar_items_por_ruta(consulta_items, filtro_ruta)
        items_totales.extend(filtrados)
        stdout_total.append(consulta_stdout)
        if consulta_stderr:
            stderr_total.append(consulta_stderr)
        advertencias.append(consulta_advertencia)
        info_metricas.append(
            _resumir_metrica_consulta(consulta_q, total_count_api, len(consulta_items), len(filtrados))
        )

    advertencia = _combinar_advertencias(*advertencias)
    registros = normalizar_registros(items_totales, origen="gh search code")
    if limite is not None:
        registros = registros[:limite]

    comando_repr = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/code",
        f"fragmentos_directorio={len(CONSULTAS_DIRECTORIO_FRAGMENTADAS)}",
        f"+gitignore=1",
        f"per_page={SEARCH_PAGE_SIZE}",
    ]
    return GhSearchResult(
        registros=registros,
        comando=comando_repr,
        stdout="\n".join(stdout_total),
        stderr="\n".join(stderr_total),
        advertencia=advertencia,
        info_metricas=info_metricas,
    )


def enriquecer_estrellas(registros: list[MatchRecord]) -> list[MatchRecord]:
    if shutil.which("gh") is None:
        return registros

    _aplicar_estrellas_batch(registros)

    return registros
