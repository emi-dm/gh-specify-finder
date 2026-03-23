"""
Carga y normalización de resultados de `gh search code` (JSON / JSONL).

Agrupa filas por repositorio y acumula rutas de coincidencia en un solo `MatchRecord`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import MatchRecord


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        texto = item.strip()
        if not texto:
            return {}
        try:
            parsed = json.loads(texto)
        except json.JSONDecodeError:
            return {"raw": texto}
        if isinstance(parsed, dict):
            return parsed
        return {"raw": parsed}
    return {"raw": item}


def _es_repositorio_publico_en_payload(data: dict[str, Any]) -> bool:
    """Si el JSON trae ``visibility`` en ``repository``, exige ``public``; si no hay campo, se acepta el ítem."""
    repo = data.get("repository") or data.get("repo") or data.get("repositorio")
    if not isinstance(repo, dict):
        return True
    vis = repo.get("visibility")
    if vis is None:
        return True
    return str(vis).lower() == "public"


def _extraer_repositorio(data: dict[str, Any]) -> tuple[str, str, int | None]:
    repo = data.get("repository") or data.get("repo") or data.get("repositorio")
    nombre = ""
    url = ""
    estrellas: int | None = None

    if isinstance(repo, dict):
        nombre = (
            repo.get("nameWithOwner")
            or repo.get("name_with_owner")
            or repo.get("full_name")
            or repo.get("fullName")
            or repo.get("name")
            or ""
        )
        url = repo.get("url") or repo.get("htmlUrl") or repo.get("html_url") or ""
        estrellas = (
            repo.get("stargazerCount")
            or repo.get("stargazersCount")
            or repo.get("stargazers_count")
            or repo.get("stars")
        )
    elif isinstance(repo, str):
        nombre = repo

    nombre = nombre or data.get("repository_name") or data.get("nombre_repo") or ""
    url = url or data.get("repository_url") or data.get("url") or data.get("htmlUrl") or data.get("html_url") or ""
    estrellas = estrellas if estrellas is not None else data.get("stars") or data.get("estrellas")

    try:
        estrellas = int(estrellas) if estrellas is not None and estrellas != "" else None
    except (TypeError, ValueError):
        estrellas = None

    return nombre, url, estrellas


def _extraer_ruta(data: dict[str, Any]) -> str:
    ruta = (
        data.get("path")
        or data.get("matched_path")
        or data.get("ruta")
        or data.get("filePath")
        or data.get("file_path")
        or ""
    )
    ruta = str(ruta).strip()
    if ruta:
        return ruta
    nombre = data.get("name")
    if nombre is not None:
        return str(nombre).strip()
    return ""


def normalizar_registros(items: Iterable[Any], origen: str = "") -> list[MatchRecord]:
    """Unifica ítems de búsqueda en registros únicos por `nombre_repo`, ordenados alfabéticamente."""
    registros: dict[str, MatchRecord] = {}

    for item in items:
        data = _as_dict(item)
        if not data:
            continue
        if not _es_repositorio_publico_en_payload(data):
            continue
        nombre, url, estrellas = _extraer_repositorio(data)
        ruta = _extraer_ruta(data)
        if not nombre:
            continue
        registro = registros.get(nombre)
        if registro is None:
            registro = MatchRecord(
                nombre_repo=nombre,
                url_repo=url,
                estrellas=estrellas,
                origen=origen,
                metadatos={k: v for k, v in data.items() if k not in {"repository", "repo"}},
            )
            registros[nombre] = registro
        else:
            if not registro.url_repo and url:
                registro.url_repo = url
            if registro.estrellas is None and estrellas is not None:
                registro.estrellas = estrellas
        if ruta:
            registro.add_path(ruta)

    return sorted(registros.values(), key=lambda r: (r.nombre_repo.lower(), r.ruta_coincidente.lower()))


def cargar_desde_json(path: str | Path) -> list[MatchRecord]:
    """Lee un JSON array/objeto o JSONL desde disco y devuelve registros normalizados."""
    texto = Path(path).read_text(encoding="utf-8")
    if not texto.strip():
        return []

    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        items = [json.loads(line) for line in texto.splitlines() if line.strip()]
        return normalizar_registros(items, origen=str(path))

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("items") or parsed.get("data") or parsed.get("results") or [parsed]
    else:
        items = [parsed]

    return normalizar_registros(items, origen=str(path))
