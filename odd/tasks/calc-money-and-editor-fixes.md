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
- L2. Decisión: no migrar datos — con M1 las respuestas `unit_cost` de
  materiales ya están en ctvs; solo la escala de entrada del MaterialForm
  cambia (×100). Los materiales ya creados con 1500 ctvs ($15) deben
  re-editarse por la usuaria (documentar en el changelog del fix).
