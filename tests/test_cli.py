import json
import argparse
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gh_specify_finder.cli import construir_parser
from gh_specify_finder.gh_client import enriquecer_estrellas, ejecutar_busqueda_gh
from gh_specify_finder.models import MatchRecord


class CliTests(unittest.TestCase):
    def test_buscar_usa_limite_por_defecto_de_mil(self):
        parser = construir_parser()
        args = parser.parse_args(["buscar"])
        self.assertEqual(args.limite, 10000)
        self.assertEqual(args.espera, 1.0)
        self.assertEqual(args.reintentos_rate_limit, 6)
        self.assertEqual(args.espera_rate_limit, 30.0)
        self.assertTrue(args.enriquecer_estrellas)

    @patch("gh_specify_finder.cli.guardar_csv")
    @patch("gh_specify_finder.cli.enriquecer_estrellas")
    @patch("gh_specify_finder.cli.ejecutar_busqueda_gh")
    def test_buscar_enriquece_estrellas_por_defecto(self, mock_buscar, mock_enriquecer, mock_guardar):
        mock_buscar.return_value = SimpleNamespace(registros=[], advertencia=None)
        from gh_specify_finder.cli import _ejecutar_buscar

        args = SimpleNamespace(
            consulta=".specify",
            limite=10000,
            espera=1.0,
            reintentos_rate_limit=6,
            espera_rate_limit=30.0,
            enriquecer_estrellas=True,
            salida="salida.csv",
            sin_resumen=True,
            vista_previa=10,
        )

        _ejecutar_buscar(args)

        mock_enriquecer.assert_called_once()
        mock_guardar.assert_called_once()

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_ejecutar_busqueda_gh_pasa_el_limite_solicitado(self, mock_which, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout='{"items": []}', stderr="")

        resultado = ejecutar_busqueda_gh(".specify", limite=250)

        self.assertEqual(resultado.registros, [])
        self.assertIn("gh", resultado.comando)
        self.assertIn("api", resultado.comando)
        self.assertIn("search/code", resultado.comando)
        self.assertIn("q=.specify", resultado.comando)
        self.assertIn("per_page=100", resultado.comando)
        self.assertIn("page=1", resultado.comando)
        mock_which.assert_called_once_with("gh")
        self.assertEqual(mock_run.call_count, 3)
        self.assertIn("q=.specify in:file", mock_run.call_args_list[1].args[0])
        self.assertIn("q=.specify in:path", mock_run.call_args_list[2].args[0])

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_ejecutar_busqueda_gh_combina_variantes(self, mock_which, mock_sleep, mock_run):
        page = lambda owner: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"items": [{"repository": {"nameWithOwner": owner, "url": f"https://github.com/{owner}"}, "path": "a/.specify"}]}),
            stderr="",
        )
        mock_run.side_effect = [
            page("acme/app-1"),
            page("acme/app-2"),
            page("acme/app-3"),
        ]

        resultado = ejecutar_busqueda_gh(".specify", limite=10000)

        self.assertEqual(len(resultado.registros), 3)
        self.assertIsNone(resultado.advertencia)
        mock_which.assert_called_once_with("gh")
        self.assertEqual(mock_run.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_ejecutar_busqueda_gh_con_rate_limit_devuelve_resultados_parciales(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"items": [{"repository": {"nameWithOwner": "acme/app-1", "url": "https://github.com/acme/app-1"}, "path": "a/.specify"}]}),
                stderr="",
            ),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded for user ID 1"),
        ]

        resultado = ejecutar_busqueda_gh(".specify", limite=10000)

        self.assertEqual(len(resultado.registros), 1)
        self.assertIsNotNone(resultado.advertencia)
        self.assertIn("rate limit", resultado.advertencia.lower())
        mock_which.assert_called_once_with("gh")
        self.assertEqual(mock_run.call_count, 8)
        self.assertEqual(mock_sleep.call_count, 7)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(30.0)

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_reintenta_cuando_hay_rate_limit(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(returncode=1, stdout="", stderr="gh: API rate limit exceeded"),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"items": [{"repository": {"nameWithOwner": "acme/app-1", "url": "https://github.com/acme/app-1"}, "path": "a/.specify"}]}),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout=json.dumps({"items": []}), stderr=""),
            SimpleNamespace(returncode=0, stdout=json.dumps({"items": []}), stderr=""),
        ]

        resultado = ejecutar_busqueda_gh(".specify", limite=10000, reintentos_rate_limit=1, espera_rate_limit=0.5)

        self.assertEqual(len(resultado.registros), 1)
        self.assertIsNone(resultado.advertencia)
        self.assertEqual(mock_run.call_count, 4)
        self.assertIn(0.5, [call.args[0] for call in mock_sleep.call_args_list])
        mock_which.assert_called_once_with("gh")

    @patch("gh_specify_finder.gh_client.subprocess.run")
    @patch("gh_specify_finder.gh_client.time.sleep")
    @patch("gh_specify_finder.gh_client.shutil.which", return_value="/usr/bin/gh")
    def test_trata_como_advertencia_el_limite_de_1000(self, mock_which, mock_sleep, mock_run):
        mock_run.side_effect = [
            SimpleNamespace(returncode=1, stdout="", stderr="gh: Cannot access beyond the first 1000 results (HTTP 422)"),
        ]

        resultado = ejecutar_busqueda_gh(".specify", limite=10000)

        self.assertEqual(len(resultado.registros), 0)
        self.assertIsNotNone(resultado.advertencia)
        self.assertIn("1000", resultado.advertencia)
        self.assertEqual(mock_run.call_count, 1)
        mock_which.assert_called_once_with("gh")

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
