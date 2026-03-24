"""
Interfaz de línea de comandos para buscar repositorios con Spec Kit (`.specify` / `.gitignore`).
"""

from __future__ import annotations

import argparse
import sys

from .export import VISTA_PREVIA_TABLA_DEFAULT, guardar_csv, mostrar_resumen, mostrar_tabla_csv
from .gh_client import (
    DEFAULT_ESPERA_ENTRE_CONSULTAS,
    DEFAULT_PAGE_DELAY,
    DEFAULT_RATE_LIMIT_RETRIES,
    DEFAULT_RATE_LIMIT_WAIT,
    DEFAULT_TIMEOUT_RETRIES,
    DEFAULT_TIMEOUT_WAIT,
    enriquecer_estrellas,
    ejecutar_busqueda_specify_kit,
)
from .parser import cargar_desde_json

_EPILOGO = """ejemplos (desde el repo, con uv):
  uv run %(prog)s --help
  uv run %(prog)s buscar --help
  uv run %(prog)s buscar --salida repos.csv
  uv run %(prog)s buscar --limite 500 --no-estrellas --sin-resumen
  uv run %(prog)s procesar resultados.json --salida repos.csv
  uv run %(prog)s mostrar matched_repos/resultados.csv
  uv run %(prog)s mostrar repos.csv --filas 50

Si %(prog)s está en el PATH (p. ej. tras pip install -e), puedes ejecutarlo sin "uv run ".

Por defecto ~31 consultas (máx. cobertura vía API); GitHub limita 1000 resultados por consulta.
Usa --rapido para solo 5 consultas de directorio. --limite 0 = sin tope de repos.
Requiere gh instalado y autenticado.
"""


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-specify-finder",
        description=(
            "Spec Kit en GitHub: buscar repos (carpeta .specify o .gitignore), procesar JSON de gh, "
            "o mostrar un CSV completo en la terminal con Rich."
        ),
        epilog=_EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="comando",
        required=True,
        metavar="{buscar,procesar,mostrar}",
    )

    buscar = subparsers.add_parser(
        "buscar",
        help="Ejecuta la búsqueda en GitHub y exporta CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    buscar.add_argument(
        "--salida",
        default="salida.csv",
        help="Ruta del CSV a generar.",
    )
    buscar.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Máximo de repositorios en el CSV (0 = sin tope; por defecto se exportan todos los hallados).",
    )
    buscar.add_argument(
        "--rapido",
        action="store_true",
        help="Solo 5 consultas bajo .specify (sin lenguaje/extensión); más rápido y peor cobertura.",
    )
    buscar.add_argument(
        "--sin-resumen",
        action="store_true",
        help="No mostrar la tabla resumen en consola.",
    )
    buscar.add_argument(
        "--no-estrellas",
        action="store_true",
        help="No consultar estrellas vía GraphQL (más rápido, CSV con estrellas vacías si no vienen en la búsqueda).",
    )
    avanzado_buscar = buscar.add_argument_group("avanzado", "Afinado de ritmo y reintentos (pocas veces necesario).")
    avanzado_buscar.add_argument(
        "--espera",
        type=float,
        default=DEFAULT_PAGE_DELAY,
        help="Segundos de espera entre páginas de la misma consulta a search/code.",
    )
    avanzado_buscar.add_argument(
        "--espera-consultas",
        type=float,
        default=DEFAULT_ESPERA_ENTRE_CONSULTAS,
        help="Segundos entre consultas distintas (fragmentos + gitignore); alivia el límite ~9 req/min de code search.",
    )
    avanzado_buscar.add_argument(
        "--reintentos-rate-limit",
        type=int,
        default=DEFAULT_RATE_LIMIT_RETRIES,
        help="Reintentos cuando GitHub responde rate limit (por solicitud paginada).",
    )
    avanzado_buscar.add_argument(
        "--espera-rate-limit",
        type=float,
        default=DEFAULT_RATE_LIMIT_WAIT,
        help="Segundos de espera antes de cada reintento por rate limit.",
    )
    avanzado_buscar.add_argument(
        "--reintentos-timeout",
        type=int,
        default=DEFAULT_TIMEOUT_RETRIES,
        help="Reintentos por petición ante timeout HTTP 408 / consulta demasiado pesada.",
    )
    avanzado_buscar.add_argument(
        "--espera-timeout",
        type=float,
        default=DEFAULT_TIMEOUT_WAIT,
        help="Segundos entre reintentos por timeout de búsqueda de código.",
    )
    avanzado_buscar.add_argument(
        "--vista-previa",
        type=int,
        default=VISTA_PREVIA_TABLA_DEFAULT,
        help="Filas máximas en la tabla resumen (solo si no se usa --sin-resumen).",
    )

    procesar = subparsers.add_parser(
        "procesar",
        help="Procesa JSON/JSONL exportado desde gh search code.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    procesar.add_argument("entrada", help="Archivo JSON o JSONL con resultados de gh.")
    procesar.add_argument(
        "--salida",
        default="salida.csv",
        help="Ruta del CSV a generar.",
    )
    procesar.add_argument(
        "--sin-resumen",
        action="store_true",
        help="No mostrar la tabla resumen en consola.",
    )
    procesar.add_argument(
        "--no-estrellas",
        action="store_true",
        help="No consultar estrellas vía GraphQL.",
    )
    avanzado_proc = procesar.add_argument_group("avanzado")
    avanzado_proc.add_argument(
        "--vista-previa",
        type=int,
        default=VISTA_PREVIA_TABLA_DEFAULT,
        help="Filas máximas en la tabla resumen.",
    )

    mostrar = subparsers.add_parser(
        "mostrar",
        help="Muestra un CSV como tabla Rich en la terminal (todas las columnas; filas opcionales).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    mostrar.add_argument("csv", help="Ruta al archivo CSV.")
    mostrar.add_argument(
        "--filas",
        type=int,
        default=None,
        metavar="N",
        help="Mostrar solo las primeras N filas de datos (por defecto: todas).",
    )
    mostrar.add_argument(
        "--titulo",
        default=None,
        help="Título de la tabla (por defecto: nombre del archivo).",
    )
    mostrar.add_argument(
        "--encoding",
        default="utf-8",
        help="Codificación del archivo.",
    )

    return parser


def _ejecutar_buscar(args: argparse.Namespace) -> int:
    limite_repos = None if args.limite <= 0 else args.limite
    resultado = ejecutar_busqueda_specify_kit(
        limite=limite_repos,
        espera_segundos=args.espera,
        espera_entre_consultas=args.espera_consultas,
        reintentos_rate_limit=args.reintentos_rate_limit,
        espera_rate_limit=args.espera_rate_limit,
        reintentos_timeout=args.reintentos_timeout,
        espera_timeout=args.espera_timeout,
        busqueda_rapida=args.rapido,
    )
    for linea in resultado.info_metricas:
        print(f"info: {linea}", file=sys.stderr)
    print(
        f"info: repositorios únicos tras deduplicar: {len(resultado.registros)}",
        file=sys.stderr,
    )
    if resultado.advertencia:
        print(f"warning: {resultado.advertencia}", file=sys.stderr)
    if not args.no_estrellas:
        enriquecer_estrellas(resultado.registros)
    destino = guardar_csv(resultado.registros, args.salida)
    if str(destino) != str(args.salida):
        print(
            f"info: salida existente detectada en matched_repos; guardado en {destino}",
            file=sys.stderr,
        )
    if not args.sin_resumen:
        mostrar_resumen(resultado.registros, limite=args.vista_previa)
    return 0


def _ejecutar_procesar(args: argparse.Namespace) -> int:
    registros = cargar_desde_json(args.entrada)
    if not args.no_estrellas:
        enriquecer_estrellas(registros)
    destino = guardar_csv(registros, args.salida)
    if str(destino) != str(args.salida):
        print(
            f"info: salida existente detectada en matched_repos; guardado en {destino}",
            file=sys.stderr,
        )
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
        if args.comando == "mostrar":
            mostrar_tabla_csv(
                args.csv,
                titulo=args.titulo,
                encoding=args.encoding,
                max_filas=args.filas,
            )
            return 0
    except Exception as exc:  # pragma: no cover - mensajes de error para CLI
        parser.exit(1, f"error: {exc}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
