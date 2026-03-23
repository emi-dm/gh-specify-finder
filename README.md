# gh-specify-finder

CLI pequeña en Python para buscar y procesar coincidencias de `.specify` a partir de resultados de `gh search code`.

## Qué hace

- Usa `argparse` para la interfaz de línea de comandos.
- Usa `pandas` para construir el CSV.
- Usa `rich` para mostrar un resumen legible en consola.
- Procesa resultados exportados desde `gh search code`.
- Puede usar `gh search code` como fuente de entrada de mejor esfuerzo para buscar `.specify` en repos públicos.

## Estructura

- `src/gh_specify_finder/cli.py`: comandos CLI.
- `src/gh_specify_finder/parser.py`: normalización de resultados.
- `src/gh_specify_finder/export.py`: exportación a CSV y resumen con Rich.
- `src/gh_specify_finder/gh_client.py`: invocación opcional de `gh`.
- `tests/`: pruebas básicas.
- `examples/`: ejemplo de entrada JSON.

## Instalación

Requiere Python 3.10+.

```bash
python -m pip install -e .
```

## Uso

### 1) Buscar directamente con `gh`

```bash
gh-specify-finder buscar ".specify" --salida resultados.csv
```

Opciones útiles:

- `--limite 200`: cambia el número máximo de resultados.
- `--vista-previa 20`: muestra más filas en la tabla.
- `--enriquecer-estrellas`: completa el campo de estrellas con `gh repo view` cuando falte.
- `--sin-resumen`: solo genera el CSV.

### 2) Procesar un archivo exportado desde `gh`

Si ya tienes JSON o JSONL de `gh search code`:

```bash
gh search code ".specify" --limit 100 --json repository,path,url > resultados.json
gh-specify-finder procesar resultados.json --salida resultados.csv
```

## Formato del CSV

El CSV generado incluye estas columnas:

- `nombre_repo`
- `url_repo`
- `estrellas`
- `ruta_coincidente`
- `rutas_coincidentes`
- `coincidencias`
- `origen`

## Ejemplos

```bash
# Búsqueda con salida CSV
gh-specify-finder buscar ".specify" --salida .out/specify.csv

# Procesar resultados guardados previamente
gh-specify-finder procesar ./resultados.jsonl --salida .out/specify.csv --sin-resumen
```

## Limitaciones

- `gh search code` es una fuente de entrada de mejor esfuerzo: la disponibilidad de resultados depende de GitHub, del índice y de los permisos del usuario.
- El campo de estrellas puede no venir en la salida de búsqueda; en ese caso el CSV lo deja vacío.
- Si quieres completar estrellas faltantes, usa `--enriquecer-estrellas`.
- El proyecto agrupa coincidencias por repositorio; si quieres una fila por coincidencia, habría que ajustar la estrategia de exportación.
