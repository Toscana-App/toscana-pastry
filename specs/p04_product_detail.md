# P4 — Detalle de producto (receta + costos)
Módulo: `web/modules/products` (parte detail) · Rutas: `/productos/nuevo`, `/productos/{id}` · Fase: **1**

## Contexto
La pantalla más densa del producto: datos del producto + receta (insumos con cantidad y unidad) + parámetros de preparación + desglose de costos en vivo. Tabs: **Información · Ingredientes · Preparación · Costos** (verificado en screenshot).

## User story
> Como **repostera**, quiero **definir la receta de cada producto y ver su costo real desglosado**, para **ponerle un precio que me deje la ganancia que quiero**.

**Criterios de aceptación**
- [ ] Registro: nombre, descripción, categoría, tipo, conservación, tiempo de preparación (con porciones), dificultad (1–5).
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
- **RF-P4-01**: Campos de producto: `name*`, `description`, `category*`, `type`, `storage`, `prep_time_min*` + `servings`, `difficulty` (1–5), `labor_hours*`. (UC-01)
- **RF-P4-02**: Editor de receta: lista de `recipe_item` (ingrediente, cantidad, unidad). Agregar desde autocompletado de insumos. (UC-02)
- **RF-P4-03**: Conversión de unidades (kg, g, L, ml, unidades) con exactitud decimal (sin errores de float: `Decimal` en domain). (UC-02)
- **RF-P4-04**: Recálculo en vivo del costo (endpoint `POST /products/{id}/recalculate` o cálculo local vía función espejo; latencia < 50 ms). (UC-03)
- **RF-P4-05**: Tab Costos: desglose (materiales, mano de obra, gas, merma, sub-total, margen %, precio final, redondeo aplicado) + precio por porción si `servings > 1`. (UC-03)
- **RF-P4-06**: Validación de guardado: ≥1 insumo, tiempos > 0, categoría requerida; errores inline por tab. (UC-01)
- **RF-P4-07**: Insumo sin precio en el ingrediente → precio marcado "incompleto" (badge), sin bloquear el guardado. (UC-01)
- **RF-P4-08**: Eliminar producto: soft delete si tiene pedidos históricos; advertencia con confirmación. (UC-04)

## Requerimientos no funcionales
- **RNF-P4-01**: Recálculo < 50 ms para recetas de hasta 50 insumos.
- **RNF-P4-02**: Formulario largo sin pérdida de datos: guardado local (draft) si sale de la vista (sessionStorage), confirmación si hay cambios sin guardar.
- **RNF-P4-03**: Precios con `Decimal` en todo el pipeline domain→API→UI (redondeo `ROUND_HALF_UP` al paso configurado).
- **RNF-P4-04**: A11y: tabs con teclado (arrow keys), labels por campo, errores asociados a inputs.
- **RNF-P4-05**: Mobile: tabs como pills deslizable; editor de receta como lista de rows con stepper de cantidad.

## Tareas
- [ ] API: CRUD `/products` + `GET/PUT /products/{id}` + `POST /products/{id}/recalculate`
- [ ] Domain: `product`, `recipe_item`, motor de precio (integrado a P5), validaciones
- [ ] Data: relaciones product↔recipe_item↔ingredient (cascade en soft delete)
- [ ] Web: layout de tabs (Sublime/Pills según breakpoint)
- [ ] Web: tab Información (form zod)
- [ ] Web: tab Ingredientes (autocompletado de insumos, cantidad+unidad, quitar fila)
- [ ] Web: tab Preparación (tiempo, porciones, dificultad 1–5 visual, conservación, horas de mano de obra)
- [ ] Web: tab Costos (desglose read-only con recálculo en vivo, badge "incompleto")
- [ ] Web: draft local + confirmación de salida con cambios
- [ ] Tests: pytest del motor con casos de conversión (250g harina a $2.800/kg = $700), redondeo, insumo sin precio; Vitest de tabs y editor
- [ ] GA4: `product_saved`, `recipe_updated`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Tabs.Root` (underline en desktop, pills en mobile), `Field.Root`, `InputNumber`/stepper, `Select.Root` (unidad), `Combobox` (autocompletado de insumos), `Table` (desglose en Costos), `Badge`, `Button`.
- Tab Costos: tabla con filas materiales / mano de obra / gas / merma / **precio final destacado** (text-xl, tabular-nums).
- CTA único: **Guardar producto** (sticky abajo en mobile, con safe-area).
