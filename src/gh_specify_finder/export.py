"""
Exportación de coincidencias a CSV y visualización en consola con Rich.

Incluye un resumen tras ``buscar``/``procesar`` y ``mostrar_tabla_csv`` para volcar un CSV
en tabla (opcionalmente acotando el número de filas).

La columna ``vias`` resume el criterio inferido por ruta: ``directorio`` (segmento ``.specify``),
``gitignore`` (archivo ``.gitignore``) o ambos separados por ``;``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from .criteria import inferir_vias_deteccion
from .models import MatchRecord

VISTA_PREVIA_TABLA_DEFAULT = 15


def enlace_github_canonico(nombre_repo: str) -> str:
    """URL web del repo ``https://github.com/owner/repo`` a partir de ``nameWithOwner``."""
    n = (nombre_repo or "").strip()
    if not n or "/" not in n:
        return ""
    return f"https://github.com/{n}"

console = Console()


def _resolver_destino_sin_sobrescritura(salida: Path) -> Path:
    """
    Evita sobrescribir archivos existentes dentro de ``matched_repos``.

    Si ``salida`` ya existe y está dentro de una ruta que contiene el segmento
    ``matched_repos``, genera un nombre alternativo con marca temporal.
    """
    if "matched_repos" not in salida.parts or not salida.exists():
        return salida
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidato = salida.with_name(f"{salida.stem}_{marca}{salida.suffix}")
    indice = 1
    while candidato.exists():
        candidato = salida.with_name(f"{salida.stem}_{marca}_{indice}{salida.suffix}")
        indice += 1
    return candidato


def registros_a_dataframe(registros: list[MatchRecord]) -> pd.DataFrame:
    """Construye un DataFrame con una fila por repositorio y la columna derivada ``vias``."""
    filas = []
    for registro in registros:
        filas.append(
            {
                "nombre_repo": registro.nombre_repo,
                "enlace_github": enlace_github_canonico(registro.nombre_repo),
                "url_repo": registro.url_repo,
                "estrellas": registro.estrellas,
                "ruta_coincidente": registro.ruta_coincidente,
                "rutas_coincidentes": "; ".join(registro.rutas_coincidentes),
                "coincidencias": len(registro.rutas_coincidentes),
                "vias": inferir_vias_deteccion(registro.rutas_coincidentes),
                "origen": registro.origen,
            }
        )
    return pd.DataFrame(
        filas,
        columns=[
            "nombre_repo",
            "enlace_github",
            "url_repo",
            "estrellas",
            "ruta_coincidente",
            "rutas_coincidentes",
            "coincidencias",
            "vias",
            "origen",
        ],
    )


def guardar_csv(registros: list[MatchRecord], salida: str | Path) -> Path:
    """Escribe el CSV en ``salida`` (crea directorios padre si hace falta)."""
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    destino = _resolver_destino_sin_sobrescritura(salida)
    df = registros_a_dataframe(registros)
    df.to_csv(destino, index=False)
    return destino


def mostrar_resumen(registros: list[MatchRecord], limite: int = VISTA_PREVIA_TABLA_DEFAULT) -> None:
    """Imprime una tabla con los primeros ``limite`` repositorios y el total."""
    tabla = Table(title="Resultados Spec Kit (.specify / .gitignore)")
    tabla.add_column("Repositorio", style="cyan", no_wrap=False)
    tabla.add_column("Estrellas", justify="right")
    tabla.add_column("Ruta principal", style="green")
    tabla.add_column("Más rutas", style="magenta")

    for registro in registros[:limite]:
        otras = ", ".join(registro.rutas_coincidentes[1:]) if len(registro.rutas_coincidentes) > 1 else ""
        tabla.add_row(
            registro.nombre_repo,
            "" if registro.estrellas is None else str(registro.estrellas),
            registro.ruta_coincidente or "-",
            otras,
        )

    console.print(tabla)
    console.print(f"[bold]{len(registros)}[/bold] repositorio(s) procesado(s).")


def mostrar_tabla_csv(
    path: str | Path,
    *,
    titulo: str | None = None,
    encoding: str = "utf-8",
    max_filas: int | None = None,
) -> None:
    """
    Lee un CSV y lo imprime como tabla Rich (todas las columnas).

    Si ``max_filas`` es un entero positivo, solo se muestran las primeras N **filas de datos**
    (sin contar la cabecera del CSV).
    """
    path = Path(path)
    df = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
    df = df.fillna("")

    total_filas = len(df)
    if max_filas is not None and max_filas > 0:
        df = df.head(max_filas)

    titulo_tabla = titulo if titulo is not None else path.name
    tabla = Table(
        title=titulo_tabla,
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
        pad_edge=False,
    )
    for col in df.columns:
        tabla.add_column(str(col), overflow="fold", no_wrap=False)

    for _, row in df.iterrows():
        tabla.add_row(*["" if pd.isna(v) else str(v) for v in row])

    console.print(tabla)
    n_cols = len(df.columns)
    if max_filas is not None and max_filas > 0 and total_filas > len(df):
        console.print(
            f"[dim]mostrando {len(df)} de {total_filas} filas × {n_cols} columnas[/dim]"
        )
    else:
        console.print(f"[dim]{total_filas} filas × {n_cols} columnas[/dim]")
