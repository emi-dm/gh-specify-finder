import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gh_specify_finder.cli import construir_parser, _ejecutar_buscar
from gh_specify_finder.gh_client import (
    CONSULTAS_DIRECTORIO_TODAS,
    DEFAULT_ESPERA_ENTRE_CONSULTAS,
    DEFAULT_TIMEOUT_RETRIES,
    DEFAULT_TIMEOUT_WAIT,
    enriquecer_estrellas,
    ejecutar_busqueda_specify_kit,
    total_consultas_busqueda,
)
from gh_specify_finder.models import MatchRecord

N_CONSULTAS_RAPIDO = total_consultas_busqueda(busqueda_rapida=True)
N_CONSULTAS_COMPLETO = total_consultas_busqueda(busqueda_rapida=False)


def _pagina_busqueda_vacia() -> SimpleNamespace:
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"items": [], "total_count": 0}),
        stderr="",
    )


class CliTests(unittest.TestCase):
    def test_buscar_opciones_por_defecto(self):
        parser = construir_parser()
        args = parser.parse_args(["buscar"])
        self.assertEqual(args.limite, 0)
        self.assertFalse(args.rapido)
        self.assertEqual(args.espera, 1.0)
        self.assertEqual(args.espera_consultas, DEFAULT_ESPERA_ENTRE_CONSULTAS)
        self.assertEqual(args.reintentos_rate_limit, 6)
        self.assertEqual(args.espera_rate_limit, 30.0)
        self.assertEqual(args.reintentos_timeout, DEFAULT_TIMEOUT_RETRIES)
        self.assertEqual(args.espera_timeout, DEFAULT_TIMEOUT_WAIT)
        self.assertFalse(args.no_estrellas)
        self.assertEqual(args.vista_previa, 15)

    def test_buscar_no_estrellas(self):
        parser = construir_parser()
        args = parser.parse_args(["buscar", "--no-estrellas"])
        self.assertTrue(args.no_estrellas)

    @patch("gh_specify_finder.cli.guardar_csv")
    @patch("gh_specify_finder.cli.enriquecer_estrellas")
    @patch("gh_specify_finder.cli.ejecutar_busqueda_specify_kit")
    def test_buscar_enriquece_estrellas_por_defecto(self, mock_buscar, mock_enriquecer, mock_guardar):
        mock_buscar.return_value = SimpleNamespace(registros=[], advertencia=None, info_metricas=[])

        args = SimpleNamespace(
            limite=0,
            espera=1.0,
            espera_consultas=7.0,
            reintentos_rate_limit=6,
            espera_rate_limit=30.0,
            reintentos_timeout=3,
            espera_timeout=15.0,
            no_estrellas=False,
            rapido=False,
            salida="salida.csv",
            sin_resumen=True,
            vista_previa=15,
        )

        _ejecutar_buscar(args)

        mock_enriquecer.assert_called_once()
        mock_guardar.assert_called_once()
        mock_buscar.assert_called_once()
        c_kw = mock_buscar.call_args.kwargs
        self.assertIsNone(c_kw.get("limite"))
        self.assertFalse(c_kw.get("busqueda_rapida"))

    @patch("gh_specify_finder.cli.guardar_csv")
    @patch("gh_specify_finder.cli.enriquecer_estrellas")
    @patch("gh_specify_finder.cli.ejecutar_busqueda_specify_kit")
    def test_buscar_con_no_estrellas_no_enriquece(self, mock_buscar, mock_enriquecer, mock_guardar):
        mock_buscar.return_value = SimpleNamespace(registros=[], advertencia=None, info_metricas=[])
        args = SimpleNamespace(
            limite=100,
            espera=1.0,
            espera_consultas=7.0,
            reintentos_rate_limit=6,
            espera_rate_limit=30.0,
            reintentos_timeout=3,
            espera_timeout=15.0,
            no_estrellas=True,
            rapido=False,
            salida="out.csv",
            sin_resumen=True,
            vista_previa=15,
        )
        _ejecutar_buscar(args)
        mock_enriquecer.assert_not_called()
        mock_guardar.assert_called_once()

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_ejecutar_busqueda_specify_kit_fusiona_fragmentos_y_gitignore(self, mock_which, mock_run):
        def page(owner: str, path: str):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "total_count": 1,
                        "items": [
                            {"repository": {"nameWithOwner": owner, "url": f"https://github.com/{owner}"}, "path": path}
                        ],
                    }
                ),
                stderr="",
            )

        mock_run.side_effect = [
            page("acme/con-carpeta", ".specify/README.md"),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            page("acme/solo-gitignore", ".gitignore"),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )

        self.assertEqual(len(resultado.registros), 2)
        self.assertIsNone(resultado.advertencia)
        self.assertEqual(len(resultado.info_metricas), N_CONSULTAS_RAPIDO)
        mock_which.assert_called_once_with("gh")
        self.assertEqual(mock_run.call_count, N_CONSULTAS_RAPIDO)
        nombres = {r.nombre_repo for r in resultado.registros}
        self.assertEqual(nombres, {"acme/con-carpeta", "acme/solo-gitignore"})

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_filtra_ruido_en_pasada_directorio(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "total_count": 2,
                        "items": [
                            {
                                "repository": {"nameWithOwner": "acme/buen", "url": "https://github.com/acme/buen"},
                                "path": ".specify/x.md",
                            },
                            {
                                "repository": {"nameWithOwner": "acme/malo", "url": "https://github.com/acme/malo"},
                                "path": ".claude/commands/speckit.specify.md",
                            },
                        ],
                    }
                ),
                stderr="",
            ),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )

        self.assertEqual(len(resultado.registros), 1)
        self.assertEqual(resultado.registros[0].nombre_repo, "acme/buen")

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_rate_limit_en_segunda_consulta_deja_resultados_de_la_primera(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "total_count": 1,
                        "items": [
                            {
                                "repository": {"nameWithOwner": "acme/app-1", "url": "https://github.com/acme/app-1"},
                                "path": ".specify/a.md",
                            }
                        ],
                    }
                ),
                stderr="",
            ),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )

        self.assertEqual(len(resultado.registros), 1)
        self.assertIsNotNone(resultado.advertencia)
        self.assertIn("rate limit", resultado.advertencia.lower())
        self.assertEqual(mock_run.call_count, N_CONSULTAS_RAPIDO - 1 + 7)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_reintenta_cuando_hay_rate_limit(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded"),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "items": [
                            {
                                "repository": {"nameWithOwner": "acme/app-1", "url": "https://github.com/acme/app-1"},
                                "path": ".gitignore",
                            }
                        ]
                    }
                ),
                stderr="",
            ),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None,
            reintentos_rate_limit=1,
            espera_rate_limit=0.5,
            espera_entre_consultas=0,
            busqueda_rapida=True,
        )

        self.assertEqual(len(resultado.registros), 1)
        self.assertIsNone(resultado.advertencia)
        self.assertEqual(mock_run.call_count, N_CONSULTAS_RAPIDO + 1)
        mock_sleep.assert_any_call(0.5)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_trata_como_advertencia_el_limite_de_1000(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=1, stdout="", stderr="gh: Cannot access beyond the first 1000 results (HTTP 422)"
            ),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )

        self.assertEqual(len(resultado.registros), 0)
        self.assertIsNotNone(resultado.advertencia)
        self.assertIn("1000", resultado.advertencia)
        self.assertEqual(mock_run.call_count, N_CONSULTAS_RAPIDO)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_mismo_repo_en_varios_fragmentos_un_solo_registro(self, mock_which, mock_sleep, mock_run):
        def hit(path: str):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "total_count": 1,
                        "items": [
                            {
                                "repository": {"nameWithOwner": "acme/uno", "url": "https://github.com/acme/uno"},
                                "path": path,
                            }
                        ],
                    }
                ),
                stderr="",
            )

        mock_run.side_effect = [
            hit(".specify/memory/spec.md"),
            hit(".specify/scripts/x.sh"),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
            _pagina_busqueda_vacia(),
        ]

        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )

        self.assertEqual(len(resultado.registros), 1)
        self.assertEqual(resultado.registros[0].nombre_repo, "acme/uno")
        self.assertEqual(len(resultado.registros[0].rutas_coincidentes), 2)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_info_metricas_avisa_tope_mil_cuando_total_count_alto(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"total_count": 7500, "items": []}),
                stderr="",
            ),
            *([_pagina_busqueda_vacia()] * (N_CONSULTAS_RAPIDO - 1)),
        ]
        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )
        self.assertTrue(any("7500" in m and "1000" in m for m in resultado.info_metricas))

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_gitignore_acepta_items_solo_con_name(self, mock_which, mock_sleep, mock_run):
        vacias = [_pagina_busqueda_vacia()] * (N_CONSULTAS_RAPIDO - 1)
        solo_name = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "total_count": 1,
                    "items": [
                        {
                            "repository": {"nameWithOwner": "acme/gi", "url": "https://github.com/acme/gi"},
                            "name": ".gitignore",
                        }
                    ],
                }
            ),
            stderr="",
        )
        mock_run.side_effect = [*vacias, solo_name]
        resultado = ejecutar_busqueda_specify_kit(
            limite=None, espera_entre_consultas=0, busqueda_rapida=True
        )
        self.assertEqual(len(resultado.registros), 1)
        self.assertEqual(resultado.registros[0].nombre_repo, "acme/gi")

    def test_total_consultas_completo_mayor_que_rapido(self):
        self.assertGreater(N_CONSULTAS_COMPLETO, N_CONSULTAS_RAPIDO)
        self.assertEqual(N_CONSULTAS_COMPLETO, len(CONSULTAS_DIRECTORIO_TODAS) + 1)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_timeout_408_conserva_parciales_y_sigue_consultas(self, mock_which, mock_sleep, mock_run):
        vacias = [_pagina_busqueda_vacia()] * (N_CONSULTAS_RAPIDO - 2)
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "total_count": 1,
                        "items": [
                            {
                                "repository": {"nameWithOwner": "acme/ok", "url": "https://github.com/acme/ok"},
                                "path": ".specify/a.md",
                            }
                        ],
                    }
                ),
                stderr="",
            ),
            *vacias,
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="gh: This query timed out. Try a simpler query, or try again later (HTTP 408)",
            ),
            _pagina_busqueda_vacia(),
        ]
        resultado = ejecutar_busqueda_specify_kit(
            limite=None,
            espera_entre_consultas=0,
            busqueda_rapida=True,
            reintentos_timeout=0,
        )
        self.assertEqual(len(resultado.registros), 1)
        self.assertIsNotNone(resultado.advertencia)
        self.assertIn("408", resultado.advertencia.lower())
        self.assertEqual(mock_run.call_count, N_CONSULTAS_RAPIDO)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_enriquecer_estrellas_en_lote(self, mock_which, mock_run):
        registros = [
            MatchRecord(nombre_repo="acme/app-1"),
            MatchRecord(nombre_repo="acme/app-2"),
        ]
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "r0": {"stargazerCount": 12, "url": "https://github.com/acme/app-1"},
                        "r1": {"stargazerCount": 34, "url": "https://github.com/acme/app-2"},
                    }
                }
            ),
            stderr="",
        )

        enriquecer_estrellas(registros)

        self.assertEqual(registros[0].estrellas, 12)
        self.assertEqual(registros[1].estrellas, 34)
        self.assertEqual(registros[0].url_repo, "https://github.com/acme/app-1")
        self.assertEqual(registros[1].url_repo, "https://github.com/acme/app-2")
        mock_which.assert_called_once_with("gh")
        mock_run.assert_called_once()

    @patch("gh_specify_finder.gh_client.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gh api graphql", timeout=10))
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_enriquecer_estrellas_timeout_no_cuelga(self, mock_which, mock_run):
        registros = [MatchRecord(nombre_repo="acme/app-1")]

        enriquecer_estrellas(registros)

        self.assertIsNone(registros[0].estrellas)
        mock_which.assert_called_once_with("gh")
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
