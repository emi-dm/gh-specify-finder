from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export import guardar_csv, mostrar_resumen
from .gh_client import (
    DEFAULT_PAGE_DELAY,
    DEFAULT_RATE_LIMIT_RETRIES,
    DEFAULT_RATE_LIMIT_WAIT,
    DEFAULT_SEARCH_LIMIT,
    enriquecer_estrellas,
    ejecutar_busqueda_gh,
)
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
    buscar.add_argument(
        "--limite",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=f"Número máximo de resultados (por defecto {DEFAULT_SEARCH_LIMIT}).",
    )
    buscar.add_argument(
        "--espera",
        type=float,
        default=DEFAULT_PAGE_DELAY,
        help=f"Segundos de espera entre páginas (por defecto {DEFAULT_PAGE_DELAY}).",
    )
    buscar.add_argument(
        "--reintentos-rate-limit",
        type=int,
        default=DEFAULT_RATE_LIMIT_RETRIES,
        help=f"Reintentos cuando GitHub responde rate limit (por defecto {DEFAULT_RATE_LIMIT_RETRIES}).",
    )
    buscar.add_argument(
        "--espera-rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT_WAIT,
        help=f"Segundos de espera antes de cada reintento por rate limit (por defecto {DEFAULT_RATE_LIMIT_WAIT}).",
    )
    buscar.add_argument(
        "--salida",
        default="salida.csv",
        help="Ruta del CSV a generar.",
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
    buscar_enriquecer = buscar.add_mutually_exclusive_group()
    buscar_enriquecer.add_argument(
        "--enriquecer-estrellas",
        dest="enriquecer_estrellas",
        action="store_true",
        default=True,
        help="Completa automáticamente el número de estrellas cuando falte.",
    )
    buscar_enriquecer.add_argument(
        "--sin-enriquecer-estrellas",
        dest="enriquecer_estrellas",
        action="store_false",
        help="No consultar estrellas adicionales.",
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
    procesar_enriquecer = procesar.add_mutually_exclusive_group()
    procesar_enriquecer.add_argument(
        "--enriquecer-estrellas",
        dest="enriquecer_estrellas",
        action="store_true",
        default=True,
        help="Completa automáticamente el número de estrellas cuando falte.",
    )
    procesar_enriquecer.add_argument(
        "--sin-enriquecer-estrellas",
        dest="enriquecer_estrellas",
        action="store_false",
        help="No consultar estrellas adicionales.",
    )

    return parser


def _ejecutar_buscar(args: argparse.Namespace) -> int:
    resultado = ejecutar_busqueda_gh(
        args.consulta,
        limite=args.limite,
        espera_segundos=args.espera,
        reintentos_rate_limit=args.reintentos_rate_limit,
        espera_rate_limit=args.espera_rate_limit,
    )
    if resultado.advertencia:
        print(f"warning: {resultado.advertencia}", file=sys.stderr)
    if args.enriquecer_estrellas:
        enriquecer_estrellas(resultado.registros)
    guardar_csv(resultado.registros, args.salida)
    if not args.sin_resumen:
        mostrar_resumen(resultado.registros, limite=args.vista_previa)
    return 0


def _ejecutar_procesar(args: argparse.Namespace) -> int:
    registros = cargar_desde_json(args.entrada)
    if args.enriquecer_estrellas:
        enriquecer_estrellas(registros)
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
