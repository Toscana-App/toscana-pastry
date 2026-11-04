# Importación de datos con CSV — plan de implementación (2026-11)

**Spec de origen:** `docs/specs/csv-import.md` (documento del usuario, 2026-11-03).
**Estado actual (origin/main `74ce7a2`):**
- Existe un import **por texto pegado** para insumos: `POST /api/v1/ingredients/import` con
  `{lines: [...]}` (máx. 500), parsing tolerante en `backend/src/domain/ingredients_import.py`
  (decimales con coma, punto como miles, convención argentina). Escribe **inmediatamente**,
  sin staging ni confirmación. Respuesta `{created, errors:[{line, message}]}`.
- Frontend: `frontend/src/modules/ingredients/components/ImportDialog.tsx` (textarea, sin dropzone).
- **No hay** `UploadFile`/multipart en el backend, ni `react-dropzone` ni `papaparse` en el frontend.

## Decisión de arquitectura (de la spec)

- **Buffer = tabla de staging en PostgreSQL** (`import_rows` + sesión de import). NO
  memoria/`BytesIO` (se pierde al reiniciar y falla con varias instancias) ni Redis (solo
  serviría para buffer temporal con vencimiento, no consultable).
- **El backend es la fuente de verdad**: la validación se hace fila por fila con Pydantic;
  el frontend (PapaParse) solo previsualiza.
- **Plantilla y validación del mismo esquema**: `GET /imports/template?entity=...` genera el
  CSV desde el modelo Pydantic que valida. Nunca se desincronizan.
- **Dos pasos**: upload+validación → staging con estado por fila → el usuario revisa →
  confirmación en **una transacción** a las tablas finales.
- **v1 síncrono** con tope de filas; procesamiento en segundo plano (Celery/RQ) solo si en
  producción el proceso supera el timeout de la request (~50k–100k filas).
- Fuera de scope v1: `react-spreadsheet-import` (mapeo de columnas tipo planilla),
  flatfile/OneSchema (solo si llegan muchos formatos de clientes externos).

## Requerimientos

### RF (funcionales)

| ID | Requerimiento |
|----|---------------|
| RF-CSV-01 | Plantilla por entidad: `GET /imports/template?entity=ingredients\|products\|customers` → CSV con encabezados + 2 filas de ejemplo, generado desde el mismo modelo Pydantic que valida (RNF-CSV-09). |
| RF-CSV-02 | Upload: `POST /imports` (multipart: `file` + `entity`) → crea `import_id`, parsea el CSV, valida fila por fila con Pydantic y guarda cada fila en staging con `status` (valid/error) y `errors` (fila, columna, mensaje). Devuelve resumen `{total, valid, errors}` + primeros N errores. **Contrato de columnas estricto**: el set de encabezados debe coincidir exactamente con la plantilla (orden irrelevante); columna desconocida o faltante → **422 rechazando el archivo completo** (sin `import_id`, sin staging) con el listado de las columnas en falta. |
| RF-CSV-03 | Los errores no abortan el lote: las filas válidas quedan en staging; las filas en error se reportan con número de fila y columna, y no se confirman. |
| RF-CSV-04 | Revisión: `GET /imports/{import_id}/rows?status=&page=` → filas de staging paginadas con estado y errores, para la UI de revisión. |
| RF-CSV-05 | Confirmación: `POST /imports/{import_id}/confirm` → una transacción única pasa las filas válidas a la tabla final y marca la import como confirmada (atómica: todo o nada, RNF-CSV-05). |
| RF-CSV-06 | Descarte: `DELETE /imports/{import_id}` → borra el staging antes de confirmar. |
| RF-CSV-07 | Duplicados en confirmación: filas que violan la clave única de la entidad se reportan como `skipped` con motivo (no error de validación); la regla por entidad define skip vs update (v1: skip, RNF-CSV-06). |
| RF-CSV-08 | Entidad 1: **insumos** (adapter CSV que reutiliza el parsing tolerante de `ingredients_import.py`). El endpoint viejo por texto pegado sigue funcionando. |
| RF-CSV-09 | Entidad 2: **productos** (nombre, categoría, unidad, costo unitario, precio venta, stock inicial). |
| RF-CSV-10 | Entidad 3: **clientes** (nombre, teléfono, email, dirección de entrega opcional). |
| RF-CSV-11 | Frontend: dropzone (`react-dropzone`) con botón "Subir archivo" (file picker) + sección para arrastrar el archivo; **validación client-side antes de subir** (PapaParse: set de columnas estricto contra la plantilla + chequeos básicos de datos por fila); flujo upload → revisión (tabla con estados) → confirmar/descartar. Con columnas ajenas a la plantilla o datos inválidos: error visible y **no se permite subir ni confirmar hasta corregir** (el usuario corrige el archivo y vuelve a subirlo). |
| RF-CSV-12 | Frontend: botón "Descargar plantilla" que llama a RF-CSV-01 y descarga el archivo (el usuario completa esa plantilla con los datos). |
| RF-CSV-13 | Doble validación: el frontend valida set de columnas (estricto, derivado de la plantilla descargada) y datos básicos por fila antes de enviar; el backend revalida todo (fuente autoritativa) y rechaza el archivo con 422 si las columnas no coinciden. El botón "Confirmar" queda **deshabilitado mientras existan filas en error** en staging. |

### RNF (no funcionales)

| ID | Requerimiento |
|----|---------------|
| RNF-CSV-01 | Buffer persistente: tabla de staging en Postgres. Sobrevive reinicios y varias instancias. |
| RNF-CSV-02 | Encoding: UTF-8 (con y sin BOM) y Latin-1 (Excel). Separador `,` y `;` (regional argentino) detectado automáticamente de la primera línea. |
| RNF-CSV-03 | Límites: tamaño máximo de archivo (v1: 5 MB) y filas máximas por import (v1: 10.000). Superar → 413/422 con mensaje de sugerencia ("dividí en lotes"). |
| RNF-CSV-04 | Procesamiento síncrono en v1. Background (Celery/RQ) solo si un caso real supera el timeout de la request; no se construye por anticipado. |
| RNF-CSV-05 | Atomicidad: la confirmación no deja escrituras parciales en tablas finales. |
| RNF-CSV-06 | Errores aptos para el usuario: número de fila + columna + mensaje en español sin jerga técnica (misma vara que el import actual: "La línea 12 no se pudo parsear"). |
| RNF-CSV-07 | Higiene: filas de staging confirmadas o descartadas se limpian (TTL 7 días para las que quedaron a medio camino). |
| RNF-CSV-08 | Auth: `require_admin` en todos los endpoints de import (igual que el import actual). |
| RNF-CSV-09 | Plantilla ↔ validación: test que descarga la plantilla de cada entidad y la importa de vuelta como valid (round-trip). |
| RNF-CSV-10 | Decimales argentinos en campos numéricos: coma decimal y punto de miles ("1.000,5"), reutilizando las convenciones de `domain/ingredients_import.py`. |
| RNF-CSV-11 | El backend es la autoridad única de validación: los chequeos del frontend son un gate de feedback temprano, no contrato. Si frontend y backend discrepan, manda el backend. |

## Estructura propuesta

```
backend/src/
  domain/imports.py            # ImportSession, ImportRow, estado (valid/error/skipped/confirmed), pure
  api/v1/imports/
    router.py                  # /imports/template, /imports, /imports/{id}/rows, /{id}/confirm, /{id} DELETE
    schemas.py                 # ImportUploadResponse, RowView, ConfirmResponse
    dependencies.py
    parsers.py                 # detección encoding/separador, lectura (csv.DictReader)
  data/repositories/sql_import_repository.py
  data/models.py               # ImportSessionORM, ImportRowORM (tabla staging)
  api/v1/imports/adapters/
    ingredients_adapter.py     # Pydantic model → template + validación fila (reusa parse_import_line)
    products_adapter.py
    customers_adapter.py
frontend/src/modules/imports/
  service.ts                   # template, upload, rows, confirm, discard (multipart)
  components/ImportDialogV2.tsx# dropzone + preview + revisión + confirmar
```

**Deps nuevas:** backend: ninguna (csv stdlib). Frontend: `react-dropzone`, `papaparse` (+types).

## Tasks

### T-CSV-1 — Motor de import (staging)
- Modelos ORM `ImportSessionORM` (id, entity, filename, created_at, confirmed_at, totals) y
  `ImportRowORM` (id, import_id, row_number, data JSONB, status, errors JSONB, created_at) +
  migration: SQL plano en `backend/migrations/` (existen 0001–0006, sin alembic); la nueva es
  **`0008_import_staging.sql`** (0007 reservado para `customer_delivery_address` de PR #44,
  pendiente de merge).
- `domain/imports.py` puro: estados, resumen de totales, reglas de TTL.
- Repo: `create_session`, `bulk_insert_rows` (chunked), `list_rows` (paginado + filtro status),
  `mark_confirmed` (borra filas de staging tras confirmar), `purge_expired`.
- Tests: unit del domain + integration del repo (sin Postgres acá: escritos, no ejecutados).
- **RF:** — · **RNF:** RNF-CSV-01, RNF-CSV-07 · **Commits:** `feat(imports): staging de importaciones (sesión + filas)` · **Riesgo:** bajo. **Depende de:** nada.

### T-CSV-2 — Plantillas por entidad
- `GET /imports/template?entity=` → CSV generado desde el modelo Pydantic del adapter
  (encabezados + 2 filas de ejemplo). Entity desconocido → 422 con la lista de entidades.
- Test round-trip (RNF-CSV-09): la plantilla parseada pasa la validación del adapter.
- **RF:** RF-CSV-01 · **RNF:** RNF-CSV-09, RNF-CSV-10 · **Commits:** `feat(imports): plantillas CSV por entidad` · **Riesgo:** bajo. **Depende de:** T-CSV-3 (los adapters existen primero; o al revés: el adapter de ingredients de T-CSV-3 se escribe junto).

### T-CSV-3 — Upload + validación
- `POST /imports` multipart (`UploadFile` + `entity`): detección de encoding (BOM → UTF-8;
  fallback Latin-1) y separador (`;` vs `,` en la primera línea, RNF-CSV-02); límites de
  tamaño/filas (RNF-CSV-03); validación fila por fila con el Pydantic model del adapter;
  staging con status + errores (fila, columna, mensaje).
- Respuesta 201: `{import_id, total, valid, errors, first_errors: [...]}`.
- Tests: parser (encoding/separador/decimales) — **ejecutables sin DB** (función pura);
  endpoint (sin Postgres: escrito, no ejecutado).
- **RF:** RF-CSV-02, RF-CSV-03 · **RNF:** RNF-CSV-02, -03, -06, -08, -10 · **Commits:** `feat(imports): upload CSV con validación fila a fila` · **Riesgo:** medio (detección de encoding). **Depende de:** T-CSV-1.

### T-CSV-4 — Revisión + confirmación + descarte
- `GET /imports/{id}/rows` (paginado, filtro status), `POST /imports/{id}/confirm`
  (transacción única: INSERT batch a la tabla final del adapter + `confirmed_at` + limpieza
  de staging; duplicados → `skipped` reportados, RF-CSV-07), `DELETE /imports/{id}`.
- Confirmar ya confirmada → 409. Import inexistente → 404.
- Tests: atomicidad (fallback a mitad de batch → nada escrito), duplicados, 409.
- **RF:** RF-CSV-04, RF-CSV-05, RF-CSV-06, RF-CSV-07 · **RNF:** RNF-CSV-05 · **Commits:** `feat(imports): confirmación atómica + descarte` · **Riesgo:** medio (transacción). **Depende de:** T-CSV-3.

### T-CSV-5 — Adapter de insumos (entidad 1)
- Pydantic model `IngredientRow` (nombre, cantidad, unidad, precio) + template; reutiliza
  `parse_import_line`/convenciones de `ingredients_import.py` (RNF-CSV-10).
- Confirmación: crea `Ingredient` + `StockMovement` inicial (misma lógica del import actual).
- El endpoint viejo `POST /ingredients/import` no se toca (RF-P2-07 sigue vigente).
- Tests: validación (decimales, unidades, errores por columna), confirmación.
- **RF:** RF-CSV-08 · **RNF:** RNF-CSV-06, -10 · **Commits:** `feat(imports): adapter de insumos` · **Riesgo:** bajo. **Depende de:** T-CSV-4.

### T-CSV-6 — Adapter de productos (entidad 2)
- `ProductRow`: nombre, categoría, unidad, costo unitario, precio venta, stock inicial.
- Regla de duplicado: mismo nombre → skip con motivo (v1).
- **RF:** RF-CSV-09 · **Commits:** `feat(imports): adapter de productos` · **Riesgo:** bajo. **Depende de:** T-CSV-5 (patrón establecido).

### T-CSV-7 — Adapter de clientes (entidad 3)
- `CustomerRow`: nombre, teléfono, email, dirección de entrega (opcional).
- Duplicado por nombre+teléfono (misma convención que el wizard) → skip.
- **RF:** RF-CSV-10 · **Commits:** `feat(imports): adapter de clientes` · **Riesgo:** bajo. **Depende de:** T-CSV-5.
- ⚠️ Nota: si la branch de Fases 7/8 (`feat/fase78-budgets`, `delivery_address` en clientes)
  mergea primero, el adapter usa el campo ya existente; si mergea después, se resuelve el
  conflicto en el merge (el campo lo agrega esa branch).

### T-CSV-8 — Frontend: ImportDialog v2
- Deps: `react-dropzone`, `papaparse` (+ `@types/papaparse`).
- `modules/imports/service.ts`: `template(entity)` (devuelve el texto CSV: se parsea con
  PapaParse para extraer el set de columnas), `upload(file, entity)` (FormData/multipart
  — chequear que `apiFetch` lo soporta o agregarlo), `rows(importId, {status, page})`,
  `confirm(importId)`, `discard(importId)`.
- `ImportDialogV2.tsx`: botón "Subir archivo" (file picker) + sección drag&drop en la misma
  dropzone (`react-dropzone`) → **validación client-side**: set de columnas estricto contra
  la plantilla (columna ajena/faltante → bloquear el envío y mostrar las columnas en falta)
  + chequeos básicos por fila (requeridos, numéricos con coma decimal) → preview PapaParse
  (primeras 50 filas, separador/encoding detectado) → upload → tabla de revisión (badge por
  fila: válido/en error/skipped + mensaje) → confirmar (deshabilitado mientras `errors > 0`,
  con contador "X de Y válidos") / descartar.
- vitest: service (URLs, FormData) + componente (flujo happy path y con errores).
- **RF:** RF-CSV-11, RF-CSV-12 · **Commits:** `feat(imports-fe): dropzone + revisión + confirmación` · **Riesgo:** bajo. **Depende de:** T-CSV-4 (contratos de API).

### T-CSV-9 — Frontend: wiring en páginas
- Botón "Importar CSV" + "Descargar plantilla" en las páginas de insumos, productos y clientes.
  El CSV es el flujo principal de insumos: el botón del ImportDialog por textarea queda
  **oculto** (componente y endpoint vivos — deprecación de UI, decisión 2026-11-04).
- GA4: `import_started`, `import_confirmed` (gateados por consentimiento, como el resto).
- **RF:** RF-CSV-12 · **Commits:** `feat(imports-fe): wiring en insumos, productos y clientes` · **Riesgo:** bajo. **Depende de:** T-CSV-5/6/7 (entidades disponibles) + T-CSV-8.

## Orden de delivery

`T-CSV-3+T-CSV-2 (junto) → T-CSV-1 → ...` — mejor: **T-CSV-1 → T-CSV-2+T-CSV-3 (misma branch,
el adapter de ingredients nace con el motor) → T-CSV-4 → T-CSV-5 → T-CSV-6+T-CSV-7 → T-CSV-8 → T-CSV-9**.
Cada task = un commit (o par de commits backend+frontend); una sola branch
`feat/csv-import` con PR único (la feature es un solo flujo; separar por entidad fragmenta la
revisión).

## Decisiones tomadas (Gaspar, 2026-11-04)

1. **Entidades de v1**: insumos + productos + clientes — aprobado.
2. **Duplicados en confirmación**: skip con reporte (no update) — aprobado.
3. **Límites v1**: 5 MB / 10.000 filas — aprobado.
4. **Import por texto pegado**: deprecar la UI (botón oculto, endpoint vivo) — aprobado.

## Flujo refinado (Gaspar, 2026-11-04)

1. El backend proporciona la plantilla CSV con las columnas exactas (`GET /imports/template?entity=`);
   el usuario la descarga y la completa con sus datos.
2. El usuario la sube con el botón "Subir archivo" (abre el selector de la PC) o arrastrando el
   archivo a la sección de dropzone.
3. Validación del formato de columnas y de los datos **en frontend y en backend**: si existe una
   columna que no forma parte de la plantilla original, o datos incorrectos → se indica el error
   al usuario y **no se permite guardar** hasta que lo resuelva (corrige el archivo y lo vuelve a subir).
4. Objetivo: que el backend reciba la información de manera correcta — la validación del backend
   es la autoritativa (RNF-CSV-11); la del frontend es un gate de feedback temprano (RF-CSV-13).
