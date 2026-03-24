# gh-specify-finder

CLI en Python para localizar repositorios públicos que usan [Spec Kit](https://github.com/github/spec-kit): bien porque tienen la carpeta **`.specify`**, bien porque su **`.gitignore`** menciona **`.specify`**. Usa la API de búsqueda de código de GitHub a través de `gh`.

**Historial de cambios y referencia de errores** (`rate limit`, HTTP 408, tope 1000, etc.): [CHANGELOG.md](CHANGELOG.md).

## Qué hace

- **`buscar`**: por defecto ejecuta **31 consultas** a `gh api search/code` (30 sobre directorio `.specify` + 1 sobre `.gitignore`), fusiona ítems y agrupa por repositorio **sin tope de filas** salvo que indiques `--limite`:
  1. **Directorio `.specify`**: subrutas típicas (`memory`, `scripts`, `templates`, `extensions`, `commands`, `skills`), la consulta amplia `path:.specify`, y **fragmentación por lenguaje y extensión** (Python, Markdown, Shell, etc.) para obtener conjuntos distintos bajo el tope de 1000 por consulta. Luego un **filtro** en Python exige el segmento de carpeta `.specify` en la ruta.
  2. **`.gitignore`**: `filename:.gitignore ".specify"`; se **confía en la respuesta de la API** (no se descartan ítems por path), y si falta `path` en el JSON se usa el campo `name`.
- En **stderr** imprime líneas `info:` con el `total_count` que devuelve GitHub por consulta (coincidencias de código indexadas), cuántos ítems se recuperaron y cuántos pasaron el filtro; al final, cuántos **repositorios únicos** hay tras deduplicar. Si `total_count` supera 1000, se indica que la API solo permite bajar 1000 por esa consulta.
- Tras la pasada de directorio, aplica un **filtro adicional** en Python para descartar rutas que solo contienen `.specify` como parte de un nombre de archivo (p. ej. `speckit.specify.md`).
- **`procesar`**: convierte JSON o JSONL exportado manualmente desde `gh search code` en el mismo formato CSV (sin volver a lanzar las consultas fijas de `buscar`).
- **`mostrar`**: lee un CSV y lo pinta en la terminal con **Rich** (todas las columnas; opcionalmente solo las primeras **N** filas con `--filas`).
- Exporta CSV con **pandas** y muestra un resumen opcional con **rich**.
- Opcionalmente completa **estrellas** con GraphQL (`gh api graphql`).

## Falsos positivos

> **Importante:** la búsqueda de código de GitHub devuelve muchas coincidencias donde la cadena `.specify` aparece en una **ruta o en un nombre de archivo** sin que exista la carpeta Spec Kit. Eso genera **falsos positivos** típicos (por ejemplo rutas tipo `speckit.specify.md`, `specify.mk` o nombres que solo contienen “specify” como parte del fichero).

**Qué hace esta herramienta al respecto**

- En la pasada de **directorio**, las consultas usan subcadenas en `path:` (incluida una amplia `path:.specify`); después se **filtran** los resultados en Python: solo cuentan rutas donde un **segmento** del path sea exactamente `.specify`. Así se excluye la mayor parte del ruido anterior.
- En la pasada **`.gitignore`**, la consulta de GitHub ya restringe a archivos `.gitignore`; la columna `vias` del CSV indica si el repo entró por carpeta `.specify`, por `.gitignore` o por ambos.

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

### Ejecutarlo por cron a las 11:00

Si quieres ejecutarlo cada día a las **11:00** (hora local del servidor), añade una entrada como esta en `crontab`:

```bash
0 11 * * * cd /ruta/al/repositorio && uv run gh-specify-finder buscar --salida matched_repos/resultados.csv >> /ruta/al/repositorio/cron.log 2>&1
```

Notas:

- Si el archivo de salida ya existe dentro de `matched_repos`, la herramienta **no lo sobreescribe**: crea automáticamente otro CSV con sufijo de fecha/hora (por ejemplo `resultados_20260324_110000.csv`).
- Fuera de `matched_repos`, se mantiene el comportamiento habitual de sobrescritura del CSV de salida.

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
| `--limite` | Máximo de **repositorios** en el CSV (`0` = sin tope, **por defecto**). |
| `--rapido` | Solo 5 consultas de directorio (sin lenguaje/extensión); más rápido, **menos cobertura**. |
| `--sin-resumen` | No imprime la tabla en consola. |
| `--no-estrellas` | No llama a GraphQL para rellenar estrellas. |
| `mostrar` | Posicional: ruta al CSV. `--filas N`, `--titulo`, `--encoding`. |

## Grupo avanzado (`buscar`)

| Opción | Descripción |
|--------|-------------|
| `--espera` | Pausa en segundos entre **páginas** de la misma consulta. |
| `--espera-consultas` | Pausa entre **consultas distintas** (fragmentos + gitignore); por defecto 7 s para respetar el límite ~9 peticiones/min de code search. |
| `--reintentos-rate-limit` | Reintentos ante rate limit por petición paginada. |
| `--espera-rate-limit` | Segundos entre reintentos por rate limit. |
| `--reintentos-timeout` | Reintentos ante HTTP 408 / timeout de búsqueda (por petición). |
| `--espera-timeout` | Pausa entre esos reintentos. |
| `--vista-previa` | Filas máximas en la tabla resumen (por defecto 15). |

## Procesar un JSON ya descargado

```bash
gh search code "…" --limit 100 --json repository,path,url > resultados.json

uv run gh-specify-finder procesar resultados.json --salida matched_repos/resultados.csv
```

## Ver un CSV en la terminal

```bash
uv run gh-specify-finder mostrar matched_repos/resultados.csv
uv run gh-specify-finder mostrar repos.csv --filas 25
uv run gh-specify-finder mostrar repos.csv --titulo "Repos Spec Kit"
```

- `--filas N`: solo las primeras **N** filas de datos (la cabecera del CSV no cuenta como fila de datos).
- `--encoding` si el archivo no es UTF-8.

## Cómo se eliminan los duplicados

Tras juntar todos los ítems de las consultas a GitHub, la función [`normalizar_registros`](src/gh_specify_finder/parser.py) construye **como mucho una fila por repositorio** en el CSV:

1. **Clave única:** el identificador es el nombre del repo en forma `propietario/nombre` (`nameWithOwner` en la API), normalizado al campo `nombre_repo`. Cualquier coincidencia adicional del **mismo** repo no crea una segunda fila.

2. **Fusión de datos:** si el mismo repo aparece en varias consultas o archivos, se **unen** en un solo registro: se rellenan `url_repo` y `estrellas` si antes faltaban y el nuevo ítem las trae. La columna `enlace_github` se calcula siempre como `https://github.com/` + `nombre_repo`.

3. **Rutas:** cada ítem aporta una ruta de archivo (`path` o `name`). Esas rutas se acumulan en una lista **sin repetir** la misma ruta dos veces (`add_path` en [`MatchRecord`](src/gh_specify_finder/models.py)). La primera ruta define `ruta_coincidente`; el resto queda en `rutas_coincidentes` y en el contador `coincidencias`.

4. **Orden:** los repositorios se ordenan alfabéticamente por `nombre_repo` (y de forma estable por ruta principal) antes de exportar.

El mismo criterio aplica cuando usas **`procesar`** sobre un JSON/JSONL: una fila por `owner/repo`, rutas acumuladas. Si cada ítem incluye `repository.visibility` y no es `public`, esa fila **se omite**. Si el JSON no trae `visibility`, no se filtra por visibilidad en `procesar`.

## Formato del CSV

| Columna | Significado |
|---------|-------------|
| `nombre_repo` | `owner/repo` |
| `enlace_github` | URL web del repo: `https://github.com/owner/repo` |
| `url_repo` | URL del repositorio tal como viene de la API (p. ej. GraphQL) |
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

- **No existe garantía de “todos los repos de GitHub”.** La API pública `search/code` tiene techos, huecos de índice y cuotas; para un censo exhaustivo harían falta enfoques ajenos a esta CLI (p. ej. analizar [GitHub Archive](https://www.gharchive.org/) / BigQuery u otros datos masivos). Esta herramienta **maximiza lo razonable** vía muchas consultas disjuntas, pero no certifica completitud.
- **`search/code` no admite el calificador `is:public`**: si lo añades a la query, GitHub responde **0** coincidencias. El índice de búsqueda de código es en la práctica **público**; con `gh` autenticado podrían colarse repos **privados** a los que tu cuenta tiene acceso (raro en búsquedas masivas). En **`procesar`**, si el JSON trae `repository.visibility`, se descartan filas no públicas.
- **Tope duro:** como mucho **1000 coincidencias recuperables por consulta**; el `total_count` del JSON puede ser mayor. Tras agrupar por repo, el CSV tiene **menos filas** que la suma de coincidencias.
- **Modo completo (por defecto):** hasta **31** consultas × 1000 = **31 000 ítems** como techo teórico de código antes de deduplicar; en la práctica hay mucho solapamiento y el run es **largo** (decenas de minutos no es raro).
- La API de **code search** limita peticiones (~9/min autenticado); usa `--espera-consultas` / `--espera` o `--rapido` si necesitas acortar tiempo.
- **Timeout (HTTP 408):** GitHub a veces corta consultas de código “pesadas”. La herramienta **reintenta** cada petición fallida (por defecto 3 veces con 15 s entre intentos; ajusta `--reintentos-timeout` / `--espera-timeout`). Si sigue fallando, **no aborta todo el `buscar`**: guarda lo ya obtenido en esa consulta, muestra un `warning` y **continúa** con el resto. Con muchos timeouts, prueba `--rapido`, más `--espera` entre páginas o ejecuta en otro momento.
- Si aparece *rate limit*, se avisa y se conserva lo obtenido; reintenta más tarde o usa `--no-estrellas` para menos carga tras la búsqueda.
