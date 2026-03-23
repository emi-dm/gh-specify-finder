import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gh_specify_finder.export import mostrar_tabla_csv


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


if __name__ == "__main__":
    unittest.main()
