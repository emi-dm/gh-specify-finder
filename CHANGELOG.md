# Changelog

Registro de cambios relevantes y de **cómo el programa trata los fallos** de `gh`/GitHub que fueron apareciendo en el diseño y uso del proyecto.

El formato sigue en lo esencial [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/). Las versiones siguen [SemVer](https://semver.org/lang/es/) cuando se publiquen cortes explícitos.

---

## [Sin publicar]

### Añadido

- Búsqueda fragmentada en muchas consultas `search/code` (subrutas bajo `.specify`, `language:`, `extension:`) más una consulta de `.gitignore`, para acercarse al techo de **1000 resultados por consulta** sin depender de una sola query gigante.
- Modo **`--rapido`**: menos consultas de directorio (mejor ante timeouts y rate limit; peor cobertura si `path:.specify` supera 1000 coincidencias).
- Métricas por consulta (`total_count` vs ítems recuperados y tras filtro) en stderr, para ver cuándo GitHub declara más coincidencias de las que la API permite leer.
- Subcomando **`mostrar`** para previsualizar el CSV en terminal (Rich), con opciones como `--filas` para limitar filas.
- Flags **`--reintentos-timeout`** y **`--espera-timeout`** para reintentar peticiones que fallen por timeout de búsqueda de código.
- Documentación en README: falsos positivos, deduplicación (`normalizar_registros` / rutas por repo), límites de la API, `uv run`, y troubleshooting para 408 / rate limit.

### Corregido / robustez

- **Regresión `is:public` en `search/code`:** GitHub devuelve **0** resultados si se añade `is:public` a la query de búsqueda de código (calificador no aplicable como en la búsqueda de repositorios). Se dejó de usar; el README documenta el comportamiento del índice y el caso de repos privados visibles con token.
- **HTTP 408 / “query timed out”**: antes podía abortar todo el flujo; ahora se reintenta por petición y, si persiste, se emite **advertencia** y se **conservan** los resultados ya obtenidos en esa consulta, continuando con el resto.
- **Rate limit** en `search/code`: reintentos configurables (`--reintentos-rate-limit`, `--espera-rate-limit`); si sigue fallando, advertencia y resultados parciales de esa consulta.
- **Límite de las primeras 1000 coincidencias** en una misma consulta paginada: detección en stderr, advertencia y corte de paginación sin tirar abajo las demás consultas.
- Ítems de código donde la API solo devuelve **`name`** y no `path`: `_extraer_ruta` usa `name` para no perder la ruta en normalización y filtros.
- Consulta **`.gitignore`**: no se filtra por path en cliente (criterio `None`); se confía en la query de la API para no descartar coincidencias válidas por rutas vacías o distintas formas del payload.
- Enriquecimiento de **estrellas** vía GraphQL: `subprocess` con timeout; expiración u error en un lote no bloquea el resto (las estrellas pueden quedar en blanco para esos repos).

---

## Errores y condiciones procesadas (referencia técnica)

Esta tabla resume **qué detecta el código** (principalmente en stderr de `gh` o en excepciones) y **qué hace**. Sirve para entender mensajes en consola y para ampliar detección si GitHub cambia el texto.

| Situación | Dónde se trata | Criterio de detección (resumen) | Comportamiento |
|-----------|----------------|----------------------------------|----------------|
| Rate limit de la API | `_ejecutar_consulta_paginated` | `stderr` contiene `api rate limit exceeded` o `rate limit exceeded` (sin distinguir mayúsculas) | Reintenta la misma petición hasta agotar `--reintentos-rate-limit`, esperando `--espera-rate-limit`. Si sigue fallando: **advertencia**, se deja de paginar esa consulta y se sigue con las siguientes. |
| Tope de 1000 resultados en paginación | `_ejecutar_consulta_paginated` | `stderr` con `cannot access beyond the first 1000 results` o `beyond the first 1000` | **Advertencia** explicando el límite; se interrumpe la paginación de esa consulta; el resto de consultas continúa. |
| Timeout de búsqueda (408) | `_ejecutar_consulta_paginated` | `stderr` con `this query timed out`, `query timed out`, `timeout`, `http 408` o ` 408` | Reintentos con `--reintentos-timeout` / `--espera-timeout`. Si sigue fallando: **advertencia**; resultados parciales de esa consulta; siguiente consulta. |
| Otro fallo de `gh search code` | `_ejecutar_consulta_paginated` | `returncode != 0` y no coincide con los casos anteriores | **`RuntimeError`** con el mensaje de stderr (fallo no clasificado). |
| Salida no JSON | `_ejecutar_consulta_paginated` | `json.loads` falla sobre stdout | **`RuntimeError`**: “La salida de gh no fue JSON válido.” |
| `gh` no instalado o fuera de PATH | `ejecutar_busqueda_specify_kit` | `shutil.which("gh")` es `None` | **`RuntimeError`**: “No se encontró 'gh' en PATH.” |
| Timeout al pedir estrellas (GraphQL) | `_aplicar_estrellas_batch` | `subprocess.TimeoutExpired` | Se **omite** ese lote; no se reintenta en bucle infinito; el CSV puede salir sin estrellas en algunos repos. |
| Error distinto en GraphQL de estrellas | `_aplicar_estrellas_batch` | `returncode != 0` o JSON inválido / sin datos esperados | Se **ignora** el lote y se continúa; no aborta el `buscar`. |

**Notas de contexto (no son “errores” del programa, sino límites del producto):**

- **`total_count` alto vs pocos ítems**: la API de búsqueda de código solo permite recuperar hasta **1000** coincidencias por consulta; por eso se fragmenta en muchas consultas y se informa en métricas cuando `total_count > 1000`.
- **Cobertura inferior al 100 %**: con la API pública no se garantiza enumerar todos los repositorios del planeta con `.specify`; los falsos positivos (p. ej. rutas que parecen `.specify` pero no son Spec Kit) se documentan en el README.

---

## [0.1.0]

Versión inicial publicada en `pyproject.toml`: CLI `gh-specify-finder`, búsqueda vía `gh`, exportación CSV y criterios de directorio / `.gitignore`.
