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

## Uso simple

Si prefieres no instalar el comando globalmente, puedes usar:

```bash
uv run gh-specify-finder buscar ".specify" --salida matched_repos/resultados.csv
```

### 1) Buscar repositorios que coincidan con `.specify`

```bash
gh-specify-finder buscar ".specify" --salida matched_repos/resultados.csv
```

Esto crea el CSV dentro del directorio `matched_repos/` y agrupa los resultados por repositorio.

Por defecto, la herramienta intenta recuperar hasta 10000 resultados usando paginación de `gh api`, hace una pequeña pausa entre páginas y prueba varias variantes de búsqueda (`consulta`, `consulta in:file`, `consulta in:path`). Así no se queda solo con la primera tanda de coincidencias ni dispara tantas solicitudes seguidas.

Las estrellas se enriquecen automáticamente cuando es posible, con tiempo límite por lote para evitar bloqueos largos.

Si GitHub responde con rate limit, la herramienta te avisará y guardará los resultados parciales que haya podido obtener hasta ese punto.

Si GitHub devuelve el límite de 1000 resultados para una consulta concreta, la herramienta también lo tratará como advertencia y seguirá con otras variantes de búsqueda.

### 2) Ocultar el resumen en consola

Si solo quieres guardar el CSV y no ver la tabla resumen:

```bash
gh-specify-finder buscar ".specify" --salida matched_repos/resultados.csv --sin-resumen
```

`--sin-resumen` significa que la herramienta no imprime la tabla visual en terminal, pero sí genera el archivo.

Si no quieres que consulte estrellas, añade `--sin-enriquecer-estrellas`.

### 3) Procesar un archivo exportado desde `gh`

Si ya tienes JSON o JSONL de `gh search code`:

```bash
gh search code ".specify" --limit 100 --json repository,path,url > resultados.json
gh-specify-finder procesar resultados.json --salida matched_repos/resultados.csv
```

## Opciones útiles

- `--limite 200`: cambia el número máximo de resultados que se guardan en el CSV.
- `--espera 2`: cambia la pausa entre páginas de GitHub en segundos.
- `--reintentos-rate-limit 10`: número de reintentos cuando GitHub devuelve rate limit.
- `--espera-rate-limit 60`: segundos de espera entre reintentos por rate limit.
- `--vista-previa 20`: muestra más filas en la tabla.
- `--enriquecer-estrellas`: completa automáticamente el campo de estrellas cuando falte.
- `--sin-enriquecer-estrellas`: desactiva la consulta de estrellas.
- `--sin-resumen`: solo genera el CSV.
- Si aparece un `rate limit`, ejecuta la búsqueda más tarde o reduce la consulta con `--limite`.

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
gh-specify-finder buscar ".specify" --salida matched_repos/specify.csv

# Procesar resultados guardados previamente
gh-specify-finder procesar ./resultados.jsonl --salida matched_repos/specify.csv --sin-resumen
```

## Limitaciones

- `gh search code` es una fuente de entrada de mejor esfuerzo: la disponibilidad de resultados depende de GitHub, del índice y de los permisos del usuario.
- El campo de estrellas puede no venir en la salida de búsqueda; en ese caso el CSV lo deja vacío.
- Si quieres completar estrellas faltantes, usa `--enriquecer-estrellas`.
- El proyecto agrupa coincidencias por repositorio; si quieres una fila por coincidencia, habría que ajustar la estrategia de exportación.
