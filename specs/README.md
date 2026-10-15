# Dulces Herramientas — Spec de reimplementación (P1–P10)

> Generado a partir de la exploración (`REPORTE_dulcesherramientas.md`) + `~/.hermes/DESIGN.md` + docs Chakra UI v3 + guía de Chat SDK de Vercel.
> Stack: **Next.js 15 (App Router) + FastAPI + Postgres + Chakra UI v3**. Capas: `data` / `domain` / `presentation`. Cada pantalla = módulo independiente.

## Índice

| Archivo | Contenido |
|---|---|
| `master_plan.md` | Arquitectura, fórmula del motor, fases 0–4 con criterios de salida, checklist de requisitos técnicos |
| `p01_auth.md` | Auth: magic link, onboarding de tenant |
| `p02_ingredients.md` | Ingredientes: CRUD, stock, badges, movimientos |
| `p03_products_list.md` | Productos: listado, búsqueda, categorías |
| `p04_product_detail.md` | Detalle: receta (4 tabs), conversiones, costos en vivo |
| `p05_settings.md` | Configuración: costos, márgenes, recálculo global |
| `p06_orders.md` | Pedidos: desglose, margen por pedido, CTA "Le paso $X", descuento atómico de stock |
| `p07_budget_client.md` | Presupuesto paso 1: cliente |
| `p08_budget_summary.md` | Presupuesto pasos 2–3: ítems, resumen, secuencia, conversión a pedido |
| `p09_pdf.md` | PDF server-side: branding, sin costos internos, link temporal |
| `p10_whatsapp.md` | WhatsApp: wa.me outbound + bot inbound con Chat SDK |
| `api_endpoints.md` | Endpoints FastAPI por fases (método, ruta, payload, códigos, rate limits por endpoint) |
| `security.md` | Seguridad: 20 ítems obligatorios (control, implementación, verificación, matriz de trazabilidad) |
| `legal_privacy_policy.md` | Política de privacidad (lenguaje plano) |
| `legal_terms_and_conditions.md` | Términos y condiciones (lenguaje plano) |

## Formato de cada pantalla

1. **Contexto** — qué se vio en la app original (evidencia de screenshots/OCR).
2. **User story + criterios de aceptación** (checkboxes).
3. **Casos de uso** (UC-XX, actor, flujo).
4. **RF** (requerimientos funcionales, mapeados a UC) y **RNF** (no funcionales: rendimiento, a11y, seguridad, mobile).
5. **Tareas** — checklist granular por capa (API, domain, data, web, tests, GA4).
6. **UI (Chakra v3 + DESIGN.md)** — componentes concretos, layout, CTA único, tokens.

## Hallazgos de la app original corregidos en este spec

| Hallazgo (original) | Corrección | Dónde |
|---|---|---|
| Billing ajeno a la app (Shopify + email) | Se mantiene: acceso por magic link, canje único de token de compra | P1 |
| Números del resumen de presupuesto que no cuadran (cantidad no visible) | Cantidad explícita por línea + invariantes de cálculo testeadas | P8 |
| Typo "Dúlces" en el PDF | Branding desde config del tenant, validado antes de publicarse | P9 |
| Margen sin override visible | Override de margen explícito por pedido/presupuesto, visible en UI | P6/P8 |
| Contraste `#909090` sobre `#FCFCF9` (3.1:1, falla AA) | Corregir a `#6F6F6F` (≈4.9:1) + auditoría de todos los tokens | master §4.14 |

## Notas de proceso

- **Chakra UI v3**: instalar la skill del proyecto con `npx skills add https://github.com/chakra-ui/chakra-ui/tree/main/skills` y seguir `chakra-ui-builder`; tokens de DESIGN.md a `createSystem()` (fuentes Montserrat, paleta blue-400/500, radius 4/6/8, outline sobre sombras, dark mode automático vía semantic tokens).
- **Chat SDK**: verificar el adapter WhatsApp actual en `chat-sdk.dev/adapters` (el `@chat-adapter/whatsapp` sobre Cloud API; el nombre del paquete puede haber cambiado).
- **Legal**: `/humanizer` no está disponible en este entorno; se aplicaron sus principios y los textos quedaron marcados como listos para revisión legal local.
- **Sin secretos en frontend**: regla de CI que escanea el build (master §4.6); tokens de WhatsApp y de email solo en backend.
