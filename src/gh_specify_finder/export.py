from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from .models import MatchRecord


console = Console()


def registros_a_dataframe(registros: list[MatchRecord]) -> pd.DataFrame:
    filas = []
    for registro in registros:
        filas.append(
            {
                "nombre_repo": registro.nombre_repo,
                "url_repo": registro.url_repo,
                "estrellas": registro.estrellas,
                "ruta_coincidente": registro.ruta_coincidente,
                "rutas_coincidentes": "; ".join(registro.rutas_coincidentes),
                "coincidencias": len(registro.rutas_coincidentes),
                "origen": registro.origen,
            }
        )
    return pd.DataFrame(filas, columns=["nombre_repo", "url_repo", "estrellas", "ruta_coincidente", "rutas_coincidentes", "coincidencias", "origen"])


def guardar_csv(registros: list[MatchRecord], salida: str | Path) -> Path:
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    df = registros_a_dataframe(registros)
    df.to_csv(salida, index=False)
    return salida


def mostrar_resumen(registros: list[MatchRecord], limite: int = 10) -> None:
    tabla = Table(title="Resultados .specify")
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
