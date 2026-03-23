"""Criterios para detectar Spec Kit: directorio `.specify` y menciones en `.gitignore`."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath


def es_ruta_directorio_specify(ruta: str) -> bool:
    """
    True si la ruta contiene el segmento de directorio `.specify` (p. ej. `.specify/foo`,
    `apps/x/.specify/bar`). Excluye nombres de archivo como `speckit.specify.md` o `specify.mk`.
    """
    ruta = (ruta or "").strip().replace("\\", "/")
    if not ruta:
        return False
    return any(part == ".specify" for part in ruta.split("/"))


def es_ruta_archivo_gitignore(ruta: str) -> bool:
    """True si el último componente de la ruta es el archivo `.gitignore`."""
    ruta = (ruta or "").strip().replace("\\", "/")
    if not ruta:
        return False
    return PurePosixPath(ruta).name == ".gitignore"


def inferir_vias_deteccion(rutas: Iterable[str]) -> str:
    """
    Resume cómo se detectó el repositorio a partir de las rutas de coincidencia.

    Valores posibles (combinados con `;` si aplican ambos): `directorio`, `gitignore`.
    Cadena vacía si ninguna ruta encaja (no debería ocurrir tras búsquedas bien filtradas).
    """
    rutas_lista = [p for p in rutas if (p or "").strip()]
    partes: list[str] = []
    if any(es_ruta_directorio_specify(p) for p in rutas_lista):
        partes.append("directorio")
    if any(es_ruta_archivo_gitignore(p) for p in rutas_lista):
        partes.append("gitignore")
    return ";".join(partes)
