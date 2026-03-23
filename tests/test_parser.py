from pathlib import Path
import tempfile
import unittest

from gh_specify_finder.export import registros_a_dataframe
from gh_specify_finder.parser import cargar_desde_json, normalizar_registros


class ParserTests(unittest.TestCase):
    def test_normalizar_registros_agrupa_rutas(self):
        items = [
            {"repository": {"nameWithOwner": "acme/app", "url": "https://github.com/acme/app", "stargazerCount": 10}, "path": "a/.specify"},
            {"repository": {"nameWithOwner": "acme/app", "url": "https://github.com/acme/app"}, "path": "b/.specify"},
        ]
        registros = normalizar_registros(items)
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].ruta_coincidente, "a/.specify")
        self.assertEqual(registros[0].rutas_coincidentes, ["a/.specify", "b/.specify"])
        self.assertEqual(registros[0].estrellas, 10)

    def test_cargar_desde_json_y_dataframe(self):
        contenido = '[{"repository": {"nameWithOwner": "acme/app", "url": "https://github.com/acme/app", "stargazerCount": 10}, "path": "a/.specify"}]'
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "entrada.json"
            ruta.write_text(contenido, encoding="utf-8")
            registros = cargar_desde_json(ruta)
            df = registros_a_dataframe(registros)
            self.assertEqual(df.loc[0, "nombre_repo"], "acme/app")
            self.assertEqual(df.loc[0, "estrellas"], 10)
            self.assertEqual(df.loc[0, "ruta_coincidente"], "a/.specify")


if __name__ == "__main__":
    unittest.main()
