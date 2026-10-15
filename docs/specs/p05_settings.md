# P5 — Configuración (costos y márgenes)
Módulo: `web/modules/settings` · Ruta: `/configuracion` · Fase: **1**

## Contexto
Reglas de precio por defecto del negocio (verificado en screenshot): "Tus costos y márgenes". Es la configuración de tenant que alimenta el motor de precio de todos los productos.

## User story
> Como **repostera**, quiero **definir mis costos y márgenes una sola vez**, para **que todos mis productos se precien con mis reglas sin tocarlos uno por uno**.

**Criterios de aceptación**
- [ ] Configuro: valor de mi hora, margen %, redondeo, e incluir/sin incluir mano de obra, gas/energía (%) y merma (%).
- [ ] Guardo y veo confirmación; los precios de productos se recalculan.
- [ ] Si mi margen es 30% y cambio a 40%, veo cuántos productos se ven afectados (contador de recálculo).
- [ ] Valores inválidos (margen > 100, hora negativa) no se guardan: error inline.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver mi configuración | Repostera | Abre Configuración → valores actuales |
| UC-02 Editar márgenes | Repostera | Cambia campos → guardar → recálculo global |
| UC-03 Ver opciones de recargo urgencia | Repostera | Ve el recargo sugerido % (usado en P6) |
| UC-04 Restaurar valores por defecto | Repostera | "Restaurar" → valores default del sistema |

## Requerimientos funcionales
- **RF-P5-01**: Campos: `hourly_rate*`, `margin_pct` (0–100), `round_step` (> 0), `include_labor` (bool), `include_gas` (bool), `gas_pct` (0–100, requiere include_gas), `include_waste` (bool), `waste_pct` (0–100, requiere include_waste), `urgent_surcharge_pct`. (UC-01/02)
- **RF-P5-02**: Guardado atómico: toda la config o nada; validación completa antes de persistir. (UC-02)
- **RF-P5-03**: Al guardar, dispara recálculo asíncrono de todos los productos afectados y expone progreso/contador. (UC-02)
- **RF-P5-04**: Valores por defecto del sistema (hora $3.000, margen 30%, redondeo 100, toggles ON, gas 3%, merma 3%, urgencia 20%). (UC-04)
- **RF-P5-05**: "Restaurar por defecto" (sin borrar datos: solo reconfigura). (UC-04)
- **RF-P5-06**: Los toggles deshabilitan visualmente su % asociado (campo inactivo). (UC-01)

## Requerimientos no funcionales
- **RNF-P5-01**: Recálculo global de hasta 500 productos en < 10 s (tarea en cola, con notificación de finalización).
- **RNF-P5-02**: La página carga < 500 ms (1 solo endpoint GET).
- **RNF-P5-03**: A11y: toggles con `aria-pressed`, labels asociados, grupos con `fieldset/legend`.
- **RNF-P5-04**: Mobile: secciones apiladas; sticky CTA "Guardar".

## Tareas
- [ ] API: `GET /tenant/settings`, `PUT /tenant/settings` (validación Pydantic completa)
- [ ] API: job de recálculo (cola) + `GET /tenant/recalculation-status`
- [ ] Domain: entidad `tenant_settings`, validaciones de rangos
- [ ] Web: form con secciones (Horas y margen / Redondeo / Componentes opcionales / Urgencia)
- [ ] Web: toggles con campos dependientes deshabilitados
- [ ] Web: estado de recálculo en curso (badge/contador) y toast de finalización
- [ ] Tests: pytest de validaciones (margen 101 → 422, toggle OFF con % → 422); Vitest de dependencias de toggles
- [ ] GA4: `settings_saved`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Field.Root`, `InputNumber`, `Switch` (toggles), `NumberInput`, `Button`, `Stack`, `Alert` (confirmación).
- Layout: secciones con headings H3 (medium 500) + párrafos de ayuda (muted); grupos con `Fieldset`.
- CTA único: **Guardar cambios** (sticky, safe-area).
- Tokens: estados success al guardar (toast), warning para "recalculando…".
