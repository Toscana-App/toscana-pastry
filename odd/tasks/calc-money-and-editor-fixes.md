# Cost Calculator: contrato de dinero + editor de producto (Torta corazón)

Hijo de `odd/tasks/cost-calculator.md`. Verificado en vivo (2026-10-31) simulando el
flujo completo "Torta corazón" en ego-browser contra backend FastAPI + Postgres 16:
settings → categorías → 7 materiales (Ingredientes/Empaque) → producto con
materiales + trabajo + costo extra "Gas y luz" → guardar → lista → recalcular →
editar → dashboard.

**Veredicto: el flujo NO satisface el requerimiento de negocio** — el costo se
calcula con unidades mezcladas y el editor no deja ver ni corregir las líneas.
Cifras reales del incidente (producto `83db6568-88f8-438b-9719-f34c05226f8c`):

| Concepto | Entrado (pesos) | Costo esperado | Costo real API |
|---|---|---|---|
| Materiales (7 líneas) | 10 080 | 1 008 000 ctvs | 10 080 (×100 menor) |
| Trabajo 3000/h × 120 min | 6 000 | 600 000 ctvs | 600 000 ✓ |
| Gas y luz 800 × 1 | 800 | 80 000 ctvs | 80 000 ✓ |
| **Total** | 16 880 | **1 688 000 ctvs ($16 880)** | **690 080 ($6 900,80)** |
| Precio final (30% margen, 21% IVA) | — | $29 178,29 | $11 928,53 |

## Root causes (evidencia)

1. **`Money` dual-semantics** (`backend/src/api/v1/money.py`): `int` se interpreta
   como centavos; `str/float` como PESOS y se multiplica ×100 ("legacy migration
   branch"). El frontend envía ambos formatos en el mismo endpoint family:
   - `MaterialForm.tsx:91` → `payload.purchase_total_price = Number(price)` → int
     → el backend lee 1500 como **1500 centavos = $15,00** (el usuario pensaba $1500).
   - `ProductLines.tsx:127,190` → `hourly_rate: rate.toString()`, `unit_cost:
     cost.toString()` → str → ×100 → pesos correctos.
   Resultado: líneas de material ×100 más baratas que trabajo/extras; el motor
   (`domain/calc_product.py`, todo en Decimal "centavos") suma unidades mezcladas.
2. **Ninguna capa de conversión pesos↔centavos en el módulo `calc` frontend**.
   Existe `pesosToCents`/`centsToPesos` solo en `modules/settings` (fuera del
   módulo). Todo el módulo calc muestra los enteros crudos: lista "690080",
   dashboard "Costo Promedio 690.080", materiales "1500", editor "1500".
3. **Editor no hidrata líneas en modo edición**: `ProductEditor.tsx` lee
   `productData.product_lines.materials`, pero `GET /calc/products/{id}` devuelve
   `materials/labor/extra_costs` a nivel superior (sin `product_lines`). Tablas
   vacías en edición; un "Actualizar" sin líneas borraría el costo del producto.
4. **Vista previa inexistente**: `ProductLines.tsx` hardcodea `line_total_cost:
   '0.00'` y `<Table.Cell>0.00</Table.Cell>` (trabajo/extras); la prop
   `showPreview` del toggle "Mostrar Vista Previa" nunca se destructurea.
5. **Editor incompleto vs brief F3**: porcentajes sin defaults de settings,
   sin botón "Recalcular", post-save `router.back()` (caí en `/materiales`),
   `fetching` nunca `true` (spinner muerto).
6. **Navegación**: la sección Calculadora no está en el nav admin (páginas
   in-discoverables, solo por URL); "Ver detalles" abre pestaña nueva.

## Specs

- S1. **Unidad canónica**: toda la API `calc` es integer centavos (Money) en
  payload y respuesta. El frontend convierte: pesos del usuario → ×100 al enviar;
  centavos → pesos + formato ARS es-AR al mostrar (`$ 16.880,00`).
- S2. Un solo lugar de conversión por módulo: helper compartido
  `frontend/src/lib/calcMoney.ts` (`pesosToCents`, `centsToPesos`,
  `formatCalcMoney`), mismo patrón que `modules/settings`.
- S3. `Money` deja de adivinar: el branch str/float-×100 de `money.py` se
  restringe (solo el endpoint legacy que lo necesita, documentado) o se elimina y
  422 en calc. El motor de cálculo nunca recibe dos escalas distintas en el
  mismo producto.
- S4. Editor de producto: las líneas (materiales/trabajo/extras) se hidratan y
  muestran con sus costos de línea; la vista previa calcula en vivo fila a fila
  y el total (material+trabajo+extras, margen, impuesto, precio final) con los
  mismos factores que el motor B9 (`lib` local espejo de `calc_product.py`).
- S5. Edición de un producto existente nunca puede vaciar líneas por bug de
  hydratación (regresión bloqueante).

## Estado (verificación 2026-11-02)

- **M1-core: DONE** — `money.py` ya rechaza str/float (int centavos canónico) y el
  router calc fue migrado a centavos (b19b616 + fixes `eeae3ff`/`82fbe50`/`075b00b`).
  Falta solo el fixture de aceptación "Torta corazón" (M1-acceptance).
- **F2-backend: NO DONE (corrección 2026-11-02)** — `GET /calc/products/{id}`
  sigue devolviendo `materials/labor/extra_costs` a nivel superior (router.py
  `get_product`); solo POST/PATCH/recalculate usan `ProductWithLinesResponse`
  (con `product_lines`). El frontend debe mapear el shape top-level (F2).
- **F1-parcial: DONE** — `pesosToCents`/`formatCents` en `lib/format.ts`;
  `calcMaterialsService` + `calcSettingsService` convierten en el borde (ccf6c5a).
- **M1-acceptance + M2: DONE** — `test_calc_money_acceptance.py` (16c8fbe).
- **F1 (products/display): DONE (2026-11-03)** — `types/calc.ts` Money → `number`
  (ctvs) + `ProductDetail` (shape real del GET, líneas a nivel superior);
  `calcProductsService.toApiPayload()` convierte labor/extra a ctvs en el borde;
  `ProductList`/`Dashboard` muestran con `formatCents`. Tests:
  `calcProductsService.test.ts` (4 casos).
- **F2: DONE (2026-11-03)** — `ProductLines` ahora es componente controlado
  (`materialLines` por prop, sin estado interno duplicado) + `computeLinePreviews`
  + preview vivo (total por fila y "Total estimado" en pesos, con toggle);
  `ProductEditor` hidrata desde el shape top-level del GET con ctvs→pesos en los
  inputs (antes leía `product_lines.*`, que el GET no envía → tabla vacía).
  Tests: `ProductLines.test.tsx` (6 casos).
- **F3: DONE (2026-11-03)** — post-crear el editor queda en modo edición con el
  id nuevo; post-actualizar, toast con botón "Ver"; botón "Recalcular" con
  spinner; panel de costos del motor con `formatCents`.
- **F4: DONE (2026-11-03)** — link "Calculadora" en `AdminNav` (antes solo
  alcanzable por URL).

## Tasks

- M1 [backend, S3, S5] **Unificar semántica `Money` en el endpoint family calc.**
  Tests: payload int → centavos; payload str/float en calc → 422 (o whitelist
  explícita por endpoint legacy con test que fije la escala). Fixture "Torta
  corazón": materiales+trabajo+extras todos en pesos → `costs.product_total_cost
  == 1688000` y `final_sale_price == 2917829` (21% IVA, 30% margen, sin
  descuento). No se toca el motor; solo la frontera.
- M2 [backend, S1] **Fixture de integración paridad de escala** (pytest, DB real):
  crear materiales con `purchase_total_price` en ctvs, producto con las 3
  familias de líneas, y assert que `unit_cost_snapshot`, `hourly_rate`,
  `unit_cost` (extras) quedan todos en la misma escala y que `recalculate`
  reproduce el total. Evita que una sola familia de líneas cambie de escala.
- F1 [frontend, S1, S2] **`calcMoney.ts` + conversión en todos los flujos calc.**
  `MaterialForm` (send ×100, display /100+format), `MaterialsAbm` (tabla y
  dialog de costo histórico), `ProductLines` (send ×100), `ProductList`,
  `Dashboard`, price list (Costo/Precio Final/Margen), editor. Tests vitest:
  round-trip, formato es-AR, campos vacíos/null. Regresión: "Torta corazón"
  muestra Costo `$ 16.880,00` y Precio final `$ 29.178,29` en lista y dashboard.
- F2 [frontend, S4] **Editor: hydratación de líneas + preview vivo.**
  Mapear `GET /calc/products/{id}` (top-level `materials/labor/extra_costs`) a
  estado de líneas; preview por fila (qty × costo unitario, tarifa × min/60,
  costo × qty) y resumen (costo total, margen, impuesto, precio final) en la
  vista previa activada por el toggle existente. Defaults de porcentaje desde
  settings (GET /calc/settings). Tests RTL: editar producto con 7 líneas las
  muestra; agregar/quitar línea actualiza totales; toggle muestra/oculta resumen.
- F3 [frontend, S4, S5] **UX de guardado y navegación del editor.**
  Post-save → `/admin/calculadora/productos` (o `/productos/{id}`) en la misma
  pestaña; botón "Recalcular" en el editor (POST recalculate + toast con el
  costo actual); spinner real mientras hidrata; "Ver detalles" en lista abre en
  la misma pestaña.
- F4 [frontend, S4] **Link "Calculadora" en el nav admin** (`components/admin/`
  nav): entra a `/admin/calculadora/configuracion` (o `productos`); accesible
  solo para admin.

## Log

- L1. Verificación en vivo (ego-browser, 2026-10-31): flujo completo de "Torta
  corazón" ejecutado; hallazgos 1-6 documentados arriba con URL/IDs de
  evidencia. `POST /products/{id}/recalculate` funciona (200) pero hereda el
  total contaminado.
- L3. Verificación 2026-11-02 (codegraph + lectura): M1-core y F1-parcial ya
  quedaron cubiertos por commits previos; el plan se ejecuta sobre branch
  `feat/calc-money-fixes` (base `feat/dark-theme`). Tareas activas:
  M1-acceptance, M2, F1 (products/display), F2 (frontend), F3, F4.
- L4. 2026-11-02: M1-acceptance + M2 DONE (test
  `tests/integration/api/test_calc_money_acceptance.py`, 4 tests green:
  "Torta corazón" 1.688.000 ctvs -> 2.917.829 ctvs con 21% IVA/30% margen;
  paridad de escala de las 3 familias; str en Money -> 422). Nota: el GET de
  detalle NO envuelve las líneas en `product_lines` (solo POST/PATCH/\
  recalculate), corregido el estado de F2-backend. Advisory (fuera de
  alcance): `sql_calc_material_repository.py:273` — el método `list()` de la
  clase `SQLCalcMaterialRepository` shadowea el builtin `list` en el class
  body y la anotation `tuple[list[CalcMaterialCostHistory], int]` falla al
  importar en Python 3.12/3.13 (eval inmediato); solo pasa en 3.14 (PEP 649).
  La suite corre con el Python 3.14 del sistema (baseline histórica).
- L5. 2026-11-02 (corrección de L3): F2-backend NO estaba hecho; `product_lines`
  solo existe en POST/PATCH/recalculate (`ProductWithLinesResponse`), el GET
  de detalle sigue devolviendo las líneas a nivel superior.
- L6. 2026-11-03: F1 (products/display), F2, F3 y F4 DONE en frontend. Gates:
  tsc limpio, eslint limpio, vitest 392/392 (39 archivos; 6 tests nuevos de
  preview + 4 del borde del service), `next build` OK. Notas: `pesosToCents`
  trunca el tercer decimal (comportamiento existente del helper compartido;
  el ODD no manda half-up, no se tocó). `centsToPesos` devuelve `number` — la
  conversión a string para los inputs del editor vive en `mapDetailLines`
  (ProductEditor).
- L7. 2026-11-03 (verificación en vivo, ego-browser): app levantada
  (uvicorn :8000 con Python 3.14 + `PYTHONPATH=src`, next dev :3000, postgres
  docker). Sesión admin inyectada (user `admin@toscana.dev` + JWT dev en
  cookie `auth_token`, legible por JS). Hallazgos:
  1. F4 OK: link "Calculadora" visible en AdminNav y con highlight.
  2. F1 OK: listado muestra "ARS 16.880" / "ARS 29.178,29" (formatCents).
  3. F2 OK: editor hidrata las 7 líneas de materiales + trabajo + extra
     (antes tabla vacía); con toggle, el preview vivo por fila coincide con
     el motor (Total estimado: 16.880).
  4. F3 OK: "Recalcular" muestra toast "Precios recalculados"; al crear
     (producto de prueba) el editor queda en modo edición (botón
     "Actualizar Producto") con panel de costos (500 + 30% + 21% =
     864,29 ✔). Producto de prueba eliminado.
  5. Migración de datos dev: los 7 materiales live estaban en escala legacy
     (pesos, p.ej. Harina=15) — se multiplicó por 100 en `calc_materials`
     (documentado en L2) y se recalculó "Torta corazón".
  Evidencia: `odd/evidence/calc-product-list.png`,
  `calc-product-editor.png`, `calc-editor-preview.png`,
  `calc-editor-after-create.png`, `calc-product-list-updated.png`.

- L2. Decisión: no migrar datos — con M1 las respuestas `unit_cost` de
  materiales ya están en ctvs; solo la escala de entrada del MaterialForm
  cambia (×100). Los materiales ya creados con 1500 ctvs ($15) deben
  re-editarse por la usuaria (documentar en el changelog del fix).
