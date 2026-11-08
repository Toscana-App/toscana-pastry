# P4 — Detalle de producto (receta + costos)
Módulo: `web/modules/products` (parte detail) · Rutas: `/productos/nuevo`, `/productos/{id}` · Fase: **1**

## Contexto
La pantalla más densa del producto: datos del producto + receta (insumos con cantidad y unidad) + parámetros de preparación + desglose de costos en vivo + **imagen del producto** (upload multipart, P12) + **switch de publicación** hacia la tienda del portal. Tabs: **Información · Ingredientes · Preparación · Costos** (verificado en screenshot).

## User story
> Como **repostera**, quiero **definir la receta de cada producto y ver su costo real desglosado**, para **ponerle un precio que me deje la ganancia que quiero**.

**Criterios de aceptación**
- [ ] Registro: nombre, descripción, categoría, tipo, conservación, tiempo de preparación (con porciones), dificultad (1–5).
- [ ] Marco tags de restricción (sin gluten, sin lácteos, …); los chips aparecen luego en el listado (P3), en el presupuesto (P8), en el PDF (P9) y en el mensaje de WhatsApp (P10).
- [ ] Armo la receta agregando insumos con cantidad y unidad; el sistema convierte unidades (kg→g, L→ml).
- [ ] Al cambiar cualquier insumo o parámetro, el desglose de costos se recalcula solo, sin guardar.
- [ ] En "Costos" veo: materiales, mano de obra, gas/energía, merma, margen y precio final (redondeado).
- [ ] No puedo guardar una receta sin al menos un insumo.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Crear producto | Repostera | Tabs Información → Ingredientes → Preparación → Costos → guardar |
| UC-02 Editar receta | Repostera | Agrega/quita/cambia insumos → recálculo en vivo |
| UC-03 Ver desglose de costos | Repostera | Tab Costos: desglose línea a línea + precio final |
| UC-04 Eliminar producto | Repostera | Advertencia (afecta pedidos históricos? no: solo lo futuro) |

## Requerimientos funcionales
- **RF-P4-01**: Registro completo: `name*`, `description?`, `category*`, `type?`, `storage?`, `prep_time_min*` (con `servings?` para porción), `difficulty` (1–5), `labor_hours*`, `tags[]` (0–10; allow-list sugerida de restricciones: sin gluten, sin lácteos, sin azúcar, sin lactosa, frutos secos, vegano, + texto libre ≤ 30 chars). (UC-01)
- **RF-P4-02**: Editor de receta: lista de `recipe_item` (ingrediente, cantidad, unidad). Agregar desde autocompletado de insumos. (UC-02)
- **RF-P4-03**: Conversión de unidades (kg, g, L, ml, unidades) con exactitud decimal (sin errores de float: `Decimal` en domain). (UC-02)
- **RF-P4-04**: Recálculo en vivo del costo (endpoint `POST /products/{id}/recalculate` o cálculo local vía función espejo; latencia < 50 ms). (UC-03)
- **RF-P4-05**: Tab Costos: desglose (materiales, mano de obra, gas, merma, sub-total, margen %, precio final, redondeo aplicado) + precio por porción si `servings > 1`. (UC-03)
- **RF-P4-06**: Validación de guardado: ≥1 insumo, tiempos > 0, categoría requerida; errores inline por tab. (UC-01)
- **RF-P4-07**: Insumo sin precio en el ingrediente → precio marcado "incompleto" (badge), sin bloquear el guardado. (UC-01)
- **RF-P4-08**: Eliminar producto: soft delete si tiene pedidos históricos; advertencia con confirmación. (UC-04)
- **RF-P4-09**: **Switch de publicación**: `available` (bool, default `false`). `PATCH /products/{id} {available: true}` publica el producto en la tienda del portal (P11); `false` lo retira. Cambiar otros campos no toca la disponibilidad. Publicar un producto incompleto (insumo sin precio) → 409 `{detail: missing_ingredients, missing: [...]}` — la tienda nunca muestra un producto sin precio. Retirar no toca pedidos ni presupuestos históricos. (P12)
- **RF-P4-10**: **Imagen del producto** (P12): `POST /products/{id}/image` (multipart, admin) / `DELETE /products/{id}/image`; las respuestas de producto incluyen `image_url` (string | null). Contrato completo en `p12_product_media.md`.
- **RF-P4-11**: **Detalle de tienda** (contrato dual del mismo recurso): `GET /products/{id}?audience=revendedores|consumidor_final` devuelve solo `{id, name, category, description, image_url, price, servings?, prep_time_min}` — sin receta, costos ni margen (security #17). Sin `audience` sigue siendo el detalle admin con desglose completo.

## Requerimientos no funcionales
- **RNF-P4-01**: Recálculo < 50 ms para recetas de hasta 50 insumos.
- **RNF-P4-02**: Formulario largo sin pérdida de datos: guardado local (draft) si sale de la vista (sessionStorage), confirmación si hay cambios sin guardar.
- **RNF-P4-03**: Precios con `Decimal` en todo el pipeline domain→API→UI (redondeo `ROUND_HALF_UP` al paso configurado).
- **RNF-P4-04**: A11y: tabs con teclado (arrow keys), labels por campo, errores asociados a inputs.
- **RNF-P4-05**: Mobile: tabs como pills deslizable; editor de receta como lista de rows con stepper de cantidad.

## Tareas
- [ ] API: CRUD `/products` + `GET/PUT /products/{id}` + `POST /products/{id}/recalculate`
- [ ] Domain: `product`, `recipe_item`, motor de precio (integrado a P5), validaciones
- [ ] Data: relaciones product↔recipe_item↔ingredient (cascade en soft delete) + `product.tags` (ARRAY/JSONB con índice GIN)
- [ ] Web: layout de tabs (Sublime/Pills según breakpoint)
- [ ] Web: tab Información (form zod) — incluye `tags[]` (multi-select con sugerencias)
- [ ] Web: tab Ingredientes (autocompletado de insumos, cantidad+unidad, quitar fila)
- [ ] Web: tab Preparación (tiempo, porciones, dificultad 1–5 visual, conservación, horas de mano de obra)
- [ ] Web: tab Costos (desglose read-only con recálculo en vivo, badge "incompleto")
- [ ] Web: draft local + confirmación de salida con cambios
- [ ] Tests: pytest del motor con casos de conversión (250g harina a $2.800/kg = $700), redondeo, insumo sin precio; Vitest de tabs y editor
- [ ] GA4: `product_saved`, `recipe_updated`
- [ ] API P12: `available` en Create/Update/Detail + 409 al publicar incompleto; `POST|DELETE /products/{id}/image` (multipart); detalle de tienda `?audience=`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Tabs.Root` (underline en desktop, pills en mobile), `Field.Root`, `InputNumber`/stepper, `Select.Root` (unidad), `Combobox` (autocompletado de insumos + multi-select de tags), `Table` (desglose en Costos), `Badge`, `Button`.
- Tab Costos: tabla con filas materiales / mano de obra / gas / merma / **precio final destacado** (text-xl, tabular-nums).
- CTA único: **Guardar producto** (sticky abajo en mobile, con safe-area).

---

# P4-CC — Editor de producto y motor de precio de la calculadora (rol administrador)

> Módulo de la calculadora refactorizada desde `E:/toscana/calculadora-costos-toscana` (`src/lib/pricing.js`, `ProductEditor`, `ProductDetail`). **Alcance exclusivo del rol administrador.** El motor es DIFERENTE al legacy: margen sobre precio final + descuento + impuesto + redondeo comercial.

## User story
> Como **administrador**, quiero **armar cada producto con sus materiales, mano de obra y costos extra, y ver su precio final con mi margen, descuento e impuesto**, para **publicar una lista de precios real**.

## Requerimientos funcionales
- **RF-P4CC-01**: `calc_product`: `name*` (1–120), `sku?` (≤40, único), `category_id?`, `description?` (≤500), `notes?` (≤500), `margin_percent` (0–100, default de settings), `discount_percent` (0–100), `tax_percent` (0–100), `status` (`draft | active | archived`, default `draft`).
- **RF-P4CC-02**: Líneas del producto (guardadas con **snapshot** de precio del material en el momento): `calc_product_material {material_id, material_name, quantity_used, unit_of_measure_snapshot, unit_cost_snapshot, line_total_cost, sort_order}`; `calc_product_labor {activity_name, hourly_rate, minutes_required, line_total_cost, sort_order}`; `calc_product_extra_cost {concept_name, unit_cost, quantity, line_total_cost, sort_order}`. El guardado reemplaza el set completo de líneas (transacción única).
- **RF-P4CC-03** (motor, paridad con `pricing.js` de la app de origen — fórmula exacta que debe mantenerse):
  - `line_material = quantity_used × unit_cost` · `line_labor = hourly_rate × (minutes_required / 60)` · `line_extra = unit_cost × quantity`
  - `cost_total = materials + labor + extra`
  - `price_before_discount = cost_total / (1 − margin)` con margin ∈ [0, 100); si margin ≥ 100% → `price_before_discount = cost_total` (evita división por cero)
  - `profit = price_before_discount − cost_total` · `discount_amount = −(cost_total + profit) × discount`
  - `adjusted_profit = profit + discount_amount` · `tax_amount = (cost_total + adjusted_profit) × tax`
  - `final_sale_price = cost_total + adjusted_profit + tax_amount`, luego redondeado según `rounding_mode` del producto/settings.
- **RF-P4CC-04**: Modos de redondeo: `none` (sin redondear), `integer` (redondeo entero), `multiple_10` (múltiplo de 10), `commercial_99` (p. ej. 4999, 3499: `ceil(value/100)×100 − 1`).
- **RF-P4CC-05**: Precios derivados (`product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price, last_recalculated_at`) son **solo-escritura del servidor** (security #8). Todo con `Decimal` + `ROUND_HALF_UP` (RNF-P4-03 aplica también aquí).
- **RF-P4CC-06**: `POST /api/v1/calc/products/{id}/recalculate` recalcula y devuelve el desglose completo `{product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price}`.
- **RF-P4CC-07**: **Historial de versiones**: cada recálculo con cambio de `final_sale_price` guarda `{version_number, product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price, changed_at}`; `GET /api/v1/calc/products/{id}/versions` paginado.
- **RF-P4CC-08**: Detalle: `GET /api/v1/calc/products/{id}` → producto + 3 listas de líneas + desglose + versiones (opcional `?include_versions`).

## API — ver `api_endpoints.md` §FASE CC
- `POST /api/v1/calc/products`, `GET|PATCH|DELETE /api/v1/calc/products/{id}`, `POST /api/v1/calc/products/{id}/recalculate`, `GET /api/v1/calc/products/{id}/versions`

## Tareas
- [ ] Ver `odd/tasks/cost-calculator.md` (tareas atómicas B12–B13, F6–F7).
