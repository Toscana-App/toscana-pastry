# P8 — Presupuesto · Paso 3 (Resumen y cálculo)
Módulo: `web/modules/budgets` (wizard steps 2–3) · Rutas: `/presupuestos/nuevo` (pasos 2–3), `/presupuestos/{id}` · Fase: **3**

## Contexto
Paso 2 agrega productos; paso 3 es el resumen (screenshot verificado: "Presupuesto #00023", cliente Ana Gómez, tabla Producto/Precio/Total, Subtotal $70.600, "Total costos $35.740 · Ganancia (40%) $23.696 · Total venta $59.436", footer de marca, CTAs "Descargar PDF" y "Enviar por WhatsApp").
⚠️ **Hallazgo de la app original**: los precios de línea no cuadran con la cantidad (cantidad no visible) y el Subtotal ≠ Total venta. Aquí se corrige: **cantidad explícita por línea** y consistencia contable.

## User story
> Como **repostera**, quiero **ver mi presupuesto con su cálculo claro (costos, ganancia, total) y editarlo antes de enviarlo**, para **estar segura de que los números son correctos antes de que los vea el cliente**.

**Criterios de aceptación**
- [ ] Veo el número de secuencia (#000NN), los datos del cliente (con dirección de entrega, si está presente) y la tabla de ítems con **cantidad, precio unitario y total** (con tags de restricción por ítem, si existen).
- [ ] Añado/quito/ modifico cantidades en el resumen; el cálculo se actualiza.
- [ ] Veo: subtotal de venta, total de costos, ganancia (%) y total de venta — siempre consistentes entre sí.
- [ ] Guardo el presupuesto (queda en mi listado) y lo abro de nuevo para editarlo o enviarlo.
- [ ] Los CTAs finales: "Descargar PDF" y "Enviar por WhatsApp".

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Armar ítems | Repostera | Paso 2: elige productos + cantidad |
| UC-02 Revisar y editar resumen | Repostera | Paso 3: ajusta cantidades → recálculo |
| UC-03 Guardar presupuesto | Repostera | "Guardar" → secuencia asignada → listado |
| UC-04 Reabrir y editar | Repostera | Desde listado → edita antes de enviar |
| UC-05 Enviar (PDF/WhatsApp) | Repostera | CTAs finales → P9 / P10 |
| UC-06 Eliminar presupuesto | Repostera | Borrado con confirmación (no afecta stock ni pedidos) |

## Requerimientos funcionales
- **RF-P8-01**: Wizard paso 2: selección de productos con stepper de cantidad (mín. 1), filtro opcional por tag de restricción (chips, del catálogo P3); precio unitario por producto (motor) o precio manual opcional (override, marcado como manual). (UC-01)
- **RF-P8-02**: Cálculo del resumen: `subtotal = Σ qty × precio_unit`, `total_costos` (motor), `ganancia = (total_venta_base − total_costos)` con `margen_pct` (default tenant, override visible), `total_venta = total_costos × (1+margen)` — **o** modo manual (subtotal) con ganancia implícita; el modo activo es explícito en UI. (UC-02)
- **RF-P8-03**: Secuencia `#000NN` por tenant (re-secuenciación al eliminar no reutiliza números; gap permitido). (UC-03)
- **RF-P8-04**: Persistencia: `budget` + `budget_items` + snapshot de cálculo; editable mientras no esté marcado enviado. (UC-03/04)
- **RF-P8-05**: Estados: `borrador → enviado` (enviar marca enviado; se puede "reenviar" tras editar, generando nueva versión). (UC-05)
- **RF-P8-06**: Listado de presupuestos (secuencia, cliente, total, estado, fecha) con búsqueda. (UC-04)
- **RF-P8-07**: Eliminar presupuesto (borrador o enviado): confirmación; no toca stock. (UC-06)
- **RF-P8-08**: Conversión presupuesto → pedido (botón "Convertir en pedido") crea el pedido con los mismos ítems. (UC-05) Reglas: (a) los precios manuales del presupuesto se conservan en el pedido; (b) solo se convierten presupuestos en estado `enviado`; (c) el presupuesto guarda el `order_id` del pedido creado y una segunda conversión responde 409 `already_converted`.

## Requerimientos no funcionales
- **RNF-P8-01**: Recálculo < 50 ms al cambiar cantidades.
- **RNF-P8-02**: Consistencia: invariantes de cálculo testeadas (subtotal, costos, ganancia, total) con propiedades: ningún total < 0; ganancia = total − costos.
- **RNF-P8-03**: Snapshot inmutable por versión: al reenviar, la versión enviada queda congelada (auditoría).
- **RNF-P8-04**: A11y: tabla con `scope`, totales con `tabular-nums`, cambio de modo de cálculo anunciado con `aria-live=polite`.
- **RNF-P8-05**: Mobile: tabla de ítems en rows compactas (producto + qty + total); bloques de cálculo apilados.

## Tareas
- [ ] API: `POST /budgets` (wizard completo), `GET/PUT /budgets/{id}`, `PATCH /budgets/{id}/items`, `DELETE /budgets/{id}`
- [ ] API: `POST /budgets/{id}/recalculate`, `POST /budgets/{id}/convert-to-order`, `GET /budgets` (list)
- [ ] Domain: `budget`, `budget_item`, cálculo con dos modos (cost-plus / manual), secuencia, máquina de estados
- [ ] Data: tabla de secuencias (row lock por tenant), snapshots de versión
- [ ] Web: paso 2 (selección de productos + cantidades + chips de tags de restricción)
- [ ] Web: paso 3 (resumen editable: tabla de ítems + bloques de cálculo + selector de modo)
- [ ] Web: listado de presupuestos
- [ ] Web: CTAs finales (Descargar PDF → P9, Enviar por WhatsApp → P10, Convertir en pedido)
- [ ] Tests: pytest de invariantes de cálculo (propiedades), secuencia, estados, conversión a pedido; Vitest del wizard completo
- [ ] GA4: `budget_created`, `budget_updated`, `budget_converted_to_order`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Table` (ítems), `NumberInput`/stepper (cantidades), `Tabs` (pasos), `Badge` (estado), `Button` (primarios), `Switch`/`RadioGroup` (modo de cálculo), `Drawer` (detalle de cálculo).
- Bloques de cálculo: filas tipo ticket: Total costos / Ganancia (X%) / **Total venta** (text-xl medium, tabular-nums).
- Footer de marca (configurable en tenant: "Gracias por confiar en nosotros…").
- CTA único del paso 3 (después de guardar): **Enviar por WhatsApp** (primario); "Descargar PDF" y "Convertir en pedido" como secondary (no compiten con el primario).
