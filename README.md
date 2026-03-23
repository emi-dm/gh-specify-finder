# gh-specify-finder

CLI en Python para localizar repositorios públicos que usan [Spec Kit](https://github.com/github/spec-kit): bien porque tienen la carpeta **`.specify`**, bien porque su **`.gitignore`** menciona **`.specify`**. Usa la API de búsqueda de código de GitHub a través de `gh`.

## Qué hace

- **`buscar`**: ejecuta **varias consultas** a `gh api search/code`, las fusiona y agrupa por repositorio:
  1. **Directorio `.specify`**: varias consultas fragmentadas (`path:.specify/memory`, `scripts`, `templates`, `extensions` y `path:.specify` amplia) para sortear el tope de **1000 coincidencias por consulta**; luego un **filtro** en Python exige el segmento de carpeta `.specify` en la ruta.
  2. **`.gitignore`**: archivos `.gitignore` que contienen la cadena `.specify`.
- En **stderr** imprime líneas `info:` con el `total_count` que devuelve GitHub por consulta (coincidencias de código indexadas), cuántos ítems se recuperaron y cuántos pasaron el filtro; al final, cuántos **repositorios únicos** hay tras deduplicar. Si `total_count` supera 1000, se indica que la API solo permite bajar 1000 por esa consulta.
- Tras la pasada de directorio, aplica un **filtro adicional** en Python para descartar rutas que solo contienen `.specify` como parte de un nombre de archivo (p. ej. `speckit.specify.md`).
- **`procesar`**: convierte JSON o JSONL exportado manualmente desde `gh search code` en el mismo formato CSV (sin volver a lanzar las consultas fijas de `buscar`).
- **`mostrar`**: lee un CSV y lo pinta **entero** en la terminal como tabla con **Rich** (todas las filas y columnas).
- Exporta CSV con **pandas** y muestra un resumen opcional con **rich**.
- Opcionalmente completa **estrellas** con GraphQL (`gh api graphql`).

## Falsos positivos

> **Importante:** la búsqueda de código de GitHub devuelve muchas coincidencias donde la cadena `.specify` aparece en una **ruta o en un nombre de archivo** sin que exista la carpeta Spec Kit. Eso genera **falsos positivos** típicos (por ejemplo rutas tipo `speckit.specify.md`, `specify.mk` o nombres que solo contienen “specify” como parte del fichero).

**Qué hace esta herramienta al respecto**

- En la pasada de **directorio**, las consultas usan subcadenas en `path:` (incluida una amplia `path:.specify`); después se **filtran** los resultados en Python: solo cuentan rutas donde un **segmento** del path sea exactamente `.specify`. Así se excluye la mayor parte del ruido anterior.
- En la pasada **`.gitignore`**, solo se consideran archivos cuyo nombre es `.gitignore` y que coinciden con la búsqueda de contenido configurada; la columna `vias` del CSV indica si el repo entró por carpeta, por `.gitignore` o por ambos.

**Si usas `procesar` con JSON propio**, ese archivo puede traer coincidencias laxas según la consulta que usaste con `gh`; el CSV seguirá reflejando esas rutas. Para el criterio estricto de directorio + `.gitignore`, conviene usar el subcomando **`buscar`**.

## Requisitos

- Python 3.10+
- [GitHub CLI](https://cli.github.com/) (`gh`) instalado y autenticado.

## Instalación

```bash
python -m pip install -e .
# o, con uv:
uv sync
```

## Uso rápido

```bash
uv run gh-specify-finder buscar --salida matched_repos/resultados.csv
```

Sin instalar el script global:

```bash
uv run python -m gh_specify_finder.cli buscar --salida salida.csv
```

Comprueba la ayuda integrada (recomendado con `uv` desde el clon del proyecto):

```bash
uv run gh-specify-finder --help
uv run gh-specify-finder buscar --help
uv run gh-specify-finder procesar --help
```

Si el comando quedó instalado en tu entorno global o virtual (`pip install -e .`), usa `gh-specify-finder` sin el prefijo `uv run`.

## Opciones principales (`buscar`, `procesar` y `mostrar`)

| Opción | Descripción |
|--------|-------------|
| `--salida` | Ruta del CSV (por defecto `salida.csv`). |
| `--limite` | Máximo de **repositorios** en el CSV (`buscar` solo). |
| `--sin-resumen` | No imprime la tabla en consola. |
| `--no-estrellas` | No llama a GraphQL para rellenar estrellas. |
| `mostrar` | Argumento posicional: ruta al CSV. Flags: `--titulo`, `--encoding`. |

## Grupo avanzado (`buscar`)

| Opción | Descripción |
|--------|-------------|
| `--espera` | Pausa en segundos entre **páginas** de la misma consulta. |
| `--espera-consultas` | Pausa entre **consultas distintas** (fragmentos + gitignore); por defecto 7 s para respetar el límite ~9 peticiones/min de code search. |
| `--reintentos-rate-limit` | Reintentos ante rate limit por petición paginada. |
| `--espera-rate-limit` | Segundos entre reintentos por rate limit. |
| `--vista-previa` | Filas máximas en la tabla resumen (por defecto 15). |

## Procesar un JSON ya descargado

```bash
gh search code "…" --limit 100 --json repository,path,url > resultados.json

uv run gh-specify-finder procesar resultados.json --salida matched_repos/resultados.csv
```

## Ver un CSV en la terminal

```bash
uv run gh-specify-finder mostrar matched_repos/resultados.csv
uv run gh-specify-finder mostrar repos.csv --titulo "Repos Spec Kit"
```

Opcional: `--encoding` si el archivo no es UTF-8.

## Formato del CSV

| Columna | Significado |
|---------|-------------|
| `nombre_repo` | `owner/repo` |
| `url_repo` | URL del repositorio |
| `estrellas` | Estrellas (API de búsqueda o GraphQL si no se usa `--no-estrellas`) |
| `ruta_coincidente` | Primera ruta de coincidencia |
| `rutas_coincidentes` | Todas las rutas, separadas por `; ` |
| `coincidencias` | Número de rutas |
| `vias` | `directorio`, `gitignore` o `directorio;gitignore` (inferido por rutas) |
| `origen` | p. ej. `gh search code` o ruta del archivo procesado |

## Estructura del código

- [`src/gh_specify_finder/cli.py`](src/gh_specify_finder/cli.py): argumentos y flujo de comandos.
- [`src/gh_specify_finder/gh_client.py`](src/gh_specify_finder/gh_client.py): llamadas a `gh api search/code` y enriquecimiento de estrellas.
- [`src/gh_specify_finder/criteria.py`](src/gh_specify_finder/criteria.py): reglas de directorio `.specify` y detección de vías.
- [`src/gh_specify_finder/parser.py`](src/gh_specify_finder/parser.py): normalización de JSON/JSONL.
- [`src/gh_specify_finder/export.py`](src/gh_specify_finder/export.py): CSV, resumen y `mostrar_tabla_csv` (Rich).
- [`tests/`](tests/): pruebas unitarias.

## Limitaciones

- La búsqueda de código de GitHub es **mejor esfuerzo**: índice, permisos y cuotas afectan los resultados.
- **Tope duro de la API:** como mucho **1000 coincidencias de código recuperables por consulta**, aunque el JSON indique un `total_count` mayor (p. ej. varios miles). Ese número es de **coincidencias en el índice**, no de repositorios únicos; al agrupar por repo el CSV suele tener **menos filas** que la suma de `total_count` de cada consulta.
- **Fragmentación:** varias consultas (`memory`, `scripts`, … + `gitignore`) suman hasta **6000 ítems** recuperables en el mejor caso (6 consultas × 1000), con solapamiento y deduplicación por repo; aun así puede haber repos fuera del índice o sin coincidencias en esas rutas.
- La API de **code search** limita las peticiones (~9/min autenticado); muchas consultas y páginas hacen el `buscar` lento salvo que ajustes `--espera` / `--espera-consultas`.
- Si aparece *rate limit*, el programa avisa y conserva lo ya obtenido; puedes reintentar más tarde o usar `--no-estrellas` para reducir llamadas extra.
