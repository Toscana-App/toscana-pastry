# P6 — Pedidos
Módulo: `web/modules/orders` · Rutas: `/pedidos`, `/pedidos/nuevo`, `/pedidos/{id}` · Fase: **2**

## Contexto
Gestión de pedidos de clientes. Screenshot verificado: "Pedido Sofía Molina" con ítems (torta 20 porciones, alfajores), desglose de insumos con costos, "Total gastos $31.500 · Trabajo $28.000 · Ganancia 35%: $20.825 · Precio final $80.325" y CTA **"Le paso $81.000"** (redondeo + envío por WhatsApp).

## User story
> Como **repostera**, quiero **registrar cada pedido con su costo real y enviarle el precio a la clienta por WhatsApp con un toque**, para **no perder pedidos ni calcular a mano**.

**Criterios de aceptación**
- [ ] Creo un pedido: cliente (nuevo o existente), productos con cantidad y ajuste de porciones.
- [ ] Veo el desglose completo: insumos unitarios, total de gastos, mano de obra, ganancia (con margen por pedido editable) y precio final redondeado.
- [ ] "Le paso $X" abre WhatsApp con el mensaje armado (ítems + total).
- [ ] Al confirmar el pedido, el stock se descuenta y queda registrado.
- [ ] Veo historial con estados (nuevo / confirmado / entregado) y busco por cliente.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver pedidos | Repostera | Lista con estado + búsqueda por cliente/fecha |
| UC-02 Crear pedido | Repostera | Cliente → ítems (productos + cantidad) → desglose en vivo → guardar |
| UC-03 Ajustar margen del pedido | Repostera | Cambia el % (override del default) → precio se recalcula |
| UC-04 Enviar precio por WhatsApp | Repostera | CTA "Le paso $X" → wa.me prellenado → marca enviado |
| UC-05 Confirmar pedido | Repostera | Estado → confirmado → stock descuenta (movimiento) |
| UC-06 Ver desglose | Repostera | Detalle: cada insumo, su cantidad y costo |

## Requerimientos funcionales
- **RF-P6-01**: CRUD de pedidos: `customer*`, `date`, `items[]` (producto, cantidad, nota de porción/tamaño), `status`. (UC-02)
- **RF-P6-02**: Desglose calculado por el motor: insumos (conversión según cantidad de porciones), total de gastos, mano de obra, margen % (default del tenant, **override visible por pedido**), ganancia, precio final, redondeo. (UC-02/03)
- **RF-P6-03**: Estados: `nuevo → confirmado → entregado` (+ `cancelado` desde confirmado, con re-pozo de stock). Transiciones validadas. (UC-05/06)
- **RF-P6-04**: Descuento de stock **atómico** al confirmar (transacción; si falta stock → error claro por insumo, sin confirmar). (UC-05)
- **RF-P6-05**: `stock_movement` por cada descuento (referencia al pedido). (UC-05)
- **RF-P6-06**: CTA WhatsApp: genera link `wa.me/?text=` con template (saludo, ítems con precios, total) y registra el evento. (UC-04)
- **RF-P6-07**: Búsqueda/filtro: por cliente, estado, rango de fechas. (UC-01)
- **RF-P6-08**: Reutilizar cliente: clientes se crean/reusan de una lista (sin duplicados exactos por nombre+teléfono). (UC-02)

## Requerimientos no funcionales
- **RNF-P6-01**: Crear pedido con 10 ítems < 1 s (desglose calculado en la misma transacción).
- **RNF-P6-02**: Concurrency: dos confirmaciones simultáneas del mismo insumo → nunca stock negativo (row-level locking).
- **RNF-P6-03**: Historial inmutable: el desglose guardado en el pedido no cambia si después edito la receta (snapshot de precios).
- **RNF-P6-04**: A11y: tabla de desglose con `scope` en headers; estados con texto (no solo color).
- **RNF-P6-05**: Mobile: wizard de creación en pasos (Cliente → Productos → Resumen) para no tener scroll infinito.

## Tareas
- [ ] API: CRUD `/orders` (list con filtros; create; update; `PATCH /orders/{id}/status`)
- [ ] API: `POST /orders/{id}/whatsapp-link` (genera + registra)
- [ ] Domain: `order`, `order_item`, snapshot de precios, máquina de estados, reglas de descuento atómico
- [ ] Data: transacción con `SELECT … FOR UPDATE` en stock; tabla de snapshot de desglose
- [ ] Web: lista de pedidos (estado, cliente, total, fecha) con búsqueda
- [ ] Web: wizard de creación (3 pasos, reutiliza wizard de presupuesto en componentes)
- [ ] Web: detalle de pedido con desglose (tabla insumos + bloques de cálculo)
- [ ] Web: control de margen override (input % con "usar default" para resetear)
- [ ] Web: CTA "Le paso $X" (wa.me) + toast "Enviado"
- [ ] Web: botones de transición de estado (confirmar/entregar/cancelar)
- [ ] Tests: pytest de descuento atómico (caso: stock insuficiente → 409 + sin cambios), snapshot inmutable, máquina de estados; Vitest del wizard
- [ ] GA4: `order_created`, `order_confirmed`, `whatsapp_price_sent`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Tabs` (wizard pasos), `Card` (item de pedido con stepper de cantidad), `Table` (desglose), `Badge` (estados), `Button` (CTA primary "Le paso $X"), `Field.Root`.
- Detalle: bloques de cálculo como filas de tabla destacadas: Total gastos / Trabajo / Ganancia (X%) / **Precio final**.
- CTA único por estado: nuevo → "Le paso $X"; confirmado → "Marcar entregado"; entregado → (sin CTA).
- Tokens: estado nuevo = neutral, confirmado = success, entregado = muted, cancelado = danger.
