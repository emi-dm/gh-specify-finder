from pathlib import Path
import tempfile
import unittest

from gh_specify_finder.criteria import (
    es_ruta_archivo_gitignore,
    es_ruta_directorio_specify,
    inferir_vias_deteccion,
)
from gh_specify_finder.export import registros_a_dataframe
from gh_specify_finder.parser import _extraer_ruta, cargar_desde_json, normalizar_registros


class CriteriaTests(unittest.TestCase):
    def test_directorio_specify_positivos(self):
        self.assertTrue(es_ruta_directorio_specify(".specify/README.md"))
        self.assertTrue(es_ruta_directorio_specify("apps/foo/.specify/bar.md"))
        self.assertTrue(es_ruta_directorio_specify("a\\.specify\\x"))  # normaliza

    def test_directorio_specify_negativos(self):
        self.assertFalse(es_ruta_directorio_specify(".claude/commands/speckit.specify.md"))
        self.assertFalse(es_ruta_directorio_specify("common/mk/specify.mk"))
        self.assertFalse(es_ruta_directorio_specify(""))
        self.assertFalse(es_ruta_directorio_specify("   "))

    def test_gitignore_y_vias(self):
        self.assertTrue(es_ruta_archivo_gitignore(".gitignore"))
        self.assertTrue(es_ruta_archivo_gitignore("pkg/.gitignore"))
        self.assertFalse(es_ruta_archivo_gitignore("foo.txt"))
        self.assertEqual(inferir_vias_deteccion([".specify/x"]), "directorio")
        self.assertEqual(inferir_vias_deteccion([".gitignore"]), "gitignore")
        self.assertEqual(
            inferir_vias_deteccion([".specify/a", ".gitignore"]),
            "directorio;gitignore",
        )


class ParserTests(unittest.TestCase):
    def test_extraer_ruta_usa_name_si_path_vacio(self):
        self.assertEqual(_extraer_ruta({"name": ".gitignore", "path": ""}), ".gitignore")
        self.assertEqual(_extraer_ruta({"name": ".gitignore"}), ".gitignore")

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
            self.assertEqual(df.loc[0, "vias"], "directorio")


if __name__ == "__main__":
    unittest.main()
