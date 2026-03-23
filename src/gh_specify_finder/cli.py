from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export import guardar_csv, mostrar_resumen
from .gh_client import enriquecer_estrellas, ejecutar_busqueda_gh
from .parser import cargar_desde_json


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-specify-finder",
        description="Busca y procesa coincidencias de .specify a partir de resultados de gh.",
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    buscar = subparsers.add_parser(
        "buscar",
        help="Ejecuta gh search code como fuente de entrada de mejor esfuerzo.",
    )
    buscar.add_argument(
        "consulta",
        nargs="?",
        default=".specify",
        help='Consulta para gh search code. Por defecto usa ".specify".',
    )
    buscar.add_argument("--limite", type=int, default=100, help="Número máximo de resultados.")
    buscar.add_argument(
        "--salida",
        default="salida.csv",
        help="Ruta del CSV a generar.",
    )
    buscar.add_argument(
        "--enriquecer-estrellas",
        action="store_true",
        help="Consulta gh repo view para completar el número de estrellas cuando falte.",
    )
    buscar.add_argument(
        "--vista-previa",
        type=int,
        default=10,
        help="Número de filas a mostrar en la tabla resumen.",
    )
    buscar.add_argument(
        "--sin-resumen",
        action="store_true",
        help="No mostrar la tabla resumen en consola.",
    )

    procesar = subparsers.add_parser(
        "procesar",
        help="Procesa un archivo JSON/JSONL exportado desde gh search code.",
    )
    procesar.add_argument("entrada", help="Archivo JSON o JSONL con resultados de gh.")
    procesar.add_argument(
        "--salida",
        default="salida.csv",
        help="Ruta del CSV a generar.",
    )
    procesar.add_argument(
        "--vista-previa",
        type=int,
        default=10,
        help="Número de filas a mostrar en la tabla resumen.",
    )
    procesar.add_argument(
        "--sin-resumen",
        action="store_true",
        help="No mostrar la tabla resumen en consola.",
    )

    return parser


def _ejecutar_buscar(args: argparse.Namespace) -> int:
    resultado = ejecutar_busqueda_gh(args.consulta, limite=args.limite)
    if args.enriquecer_estrellas:
        enriquecer_estrellas(resultado.registros)
    guardar_csv(resultado.registros, args.salida)
    if not args.sin_resumen:
        mostrar_resumen(resultado.registros, limite=args.vista_previa)
    return 0


def _ejecutar_procesar(args: argparse.Namespace) -> int:
    registros = cargar_desde_json(args.entrada)
    guardar_csv(registros, args.salida)
    if not args.sin_resumen:
        mostrar_resumen(registros, limite=args.vista_previa)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    try:
        if args.comando == "buscar":
            return _ejecutar_buscar(args)
        if args.comando == "procesar":
            return _ejecutar_procesar(args)
    except Exception as exc:  # pragma: no cover - mensajes de error para CLI
        parser.exit(1, f"error: {exc}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
