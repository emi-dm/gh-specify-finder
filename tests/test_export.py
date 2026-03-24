import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gh_specify_finder.export import guardar_csv, mostrar_tabla_csv
from gh_specify_finder.models import MatchRecord


class MostrarCsvTests(unittest.TestCase):
    def test_mostrar_tabla_csv_imprime_tabla(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "datos.csv"
            ruta.write_text("col_a,col_b\nx,1\ny,2\n", encoding="utf-8")
            with patch("gh_specify_finder.export.console.print") as mock_print:
                mostrar_tabla_csv(ruta)
            self.assertEqual(mock_print.call_count, 2)
            primera = mock_print.call_args_list[0].args[0]
            self.assertEqual(primera.title, "datos.csv")
            self.assertEqual(len(primera.rows), 2)

    def test_mostrar_respeta_titulo(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "a.csv"
            ruta.write_text("n\nv\n", encoding="utf-8")
            with patch("gh_specify_finder.export.console.print") as mock_print:
                mostrar_tabla_csv(ruta, titulo="Mi tabla")
            tabla = mock_print.call_args_list[0].args[0]
            self.assertEqual(tabla.title, "Mi tabla")

    def test_mostrar_limita_filas(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "t.csv"
            ruta.write_text("a,b\n1,1\n2,2\n3,3\n", encoding="utf-8")
            with patch("gh_specify_finder.export.console.print") as mock_print:
                mostrar_tabla_csv(ruta, max_filas=2)
            tabla = mock_print.call_args_list[0].args[0]
            self.assertEqual(len(tabla.rows), 2)
            pie = mock_print.call_args_list[1].args[0]
            self.assertIn("mostrando 2 de 3", pie)

    def test_guardar_csv_no_sobrescribe_en_matched_repos(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "matched_repos" / "repos.csv"
            base.parent.mkdir(parents=True, exist_ok=True)
            base.write_text("previo\n", encoding="utf-8")
            registros = [MatchRecord(nombre_repo="acme/repo", ruta_coincidente=".specify/a.md")]
            registros[0].add_path(".specify/a.md")

            salida_real = guardar_csv(registros, base)

            self.assertNotEqual(salida_real, base)
            self.assertTrue(base.exists())
            self.assertEqual(base.read_text(encoding="utf-8"), "previo\n")
            self.assertTrue(salida_real.exists())
            self.assertIn("matched_repos", salida_real.parts)

    def test_guardar_csv_sobrescribe_fuera_de_matched_repos(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "repos.csv"
            base.write_text("previo\n", encoding="utf-8")
            registros = [MatchRecord(nombre_repo="acme/repo", ruta_coincidente=".specify/a.md")]
            registros[0].add_path(".specify/a.md")

            salida_real = guardar_csv(registros, base)

            self.assertEqual(salida_real, base)
            self.assertTrue(base.exists())
            self.assertIn("nombre_repo", base.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
