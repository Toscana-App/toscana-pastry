# P10 — WhatsApp (envío + bot)
Módulo: `web/modules/whatsapp` + `api/bot` (Chat SDK) · Rutas: CTA en P6/P8; webhook `/webhooks/whatsapp` · Fase: **3**

## Contexto
Flujo verificado: "Con un toque se arma el mensaje solo, detallando cada producto y el total" (FAQ). Dos capas:
1. **Outbound (siempre)**: link `wa.me/?text=` prellenado — el cliente final recibe el mensaje desde el WhatsApp de la repostera. Cero costo, sin Cloud API.
2. **Inbound (opcional)**: bot del negocio con **Chat SDK** (Vercel) sobre WhatsApp Business Cloud API para que el cliente responda y el negocio sea notificado.

## User story
> Como **repostera**, quiero **enviar el presupuesto/pedido al WhatsApp de la clienta con un toque y ser notificada cuando me responda**, para **cerrar ventas sin salir de mi flujo de trabajo**.

**Criterios de aceptación**
- [ ] "Enviar por WhatsApp" abre el WhatsApp con el mensaje armado (ítems, totales, mi firma).
- [ ] El envío queda registrado (fecha + a quién).
- [ ] Si conecto mi WhatsApp Business: cuando el cliente responde, recibo una notificación en la app (y opcionalmente un reply automático con el último presupuesto).
- [ ] Sin Cloud API conectada, la app funciona 100% (wa.me) — el inbound es un toggle, no una dependencia.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Enviar presupuesto por WhatsApp | Repostera | CTA → wa.me prellenado → abierto → "enviado" marcado |
| UC-02 Enviar precio de pedido | Repostera | "Le paso $X" → wa.me → abierto |
| UC-03 Conectar WhatsApp Business | Repostera | Settings → Cloud API (token + phone number id) → webhook verificado |
| UC-04 Recibir respuesta del cliente | Bot | Webhook → Chat SDK → notificación in-app (badge en presupuesto/pedido) |
| UC-05 Reply automático | Bot | Cliente escribe → bot responde con el último presupuesto enviado (template) |

## Requerimientos funcionales
- **RF-P10-01**: Genera un link `wa.me/{phone}?text={mensaje}` con template: saludo con nombre, ítems (qty × producto — precio, + **tags de restricción** si existen), **dirección de entrega** (si está presente), total, firma del negocio; URL-encode correcto (es-AR, $, ñ). (UC-01/02)
- **RF-P10-02**: Generación de link `https://wa.me/{phone}?text=...` (teléfono normalizado a E.164, +54 default si formato local) + registro del evento (`whatsapp_sent`). (UC-01/02)
- **RF-P10-03**: Chat SDK: `new Chat({ adapters: { whatsapp: createWhatsAppAdapter() }, state: createRedisState() })`; webhook verificado (signature); handler `onSubscribedMessage` → notificación in-app al owner. (UC-04)
- **RF-P10-04**: Reply automático opcional (toggle por tenant): al recibir mensaje en un thread con presupuesto asociado, responde con el resumen de ese presupuesto. (UC-05)
- **RF-P10-05**: Conexión Cloud API: guardado de credenciales (solo backend), estado de conexión (conectado/desconectado/errores), guía de configuración. (UC-03)
- **RF-P10-06**: Rate limiting de outbound (máx. 30 links/día por tenant) para evitar abuso. (UC-01)

## Requerimientos no funcionales
- **RNF-P10-01**: **Cero tokens de WhatsApp/Cloud API en el frontend** — todo por endpoints de la API. (crítico)
- **RNF-P10-02**: Webhook idempotente (dedupe por message_id) y tolerante a reintentos de Meta.
- **RNF-P10-03**: Latencia de notificación inbound < 5 s (webhook → Redis → polling/SSE de la app).
- **RNF-P10-04**: Sin Cloud API conectada: degradación limpia (toggle deshabilitado, wa.me sigue funcionando).
- **RNF-P10-05**: Logs sin números de teléfono completos (mascarados: +54 9 11 ** ****12).

## Tareas
- [ ] API: `POST /budgets/{id}/whatsapp-link`, `POST /orders/{id}/whatsapp-link` (template + registro + rate limit)
- [ ] Domain: template de mensajes, normalización E.164, reglas de máscaras en logs
- [ ] `api/bot`: Chat SDK + `@chat-adapter/whatsapp` + `createRedisState` (verificar adapter actual en chat-sdk.dev/adapters)
- [ ] API: webhook `/webhooks/whatsapp` (verificación de firma, idempotencia, routing por thread)
- [ ] API: `GET/PUT /tenant/whatsapp` (credenciales, estado, toggles)
- [ ] Web: CTAs de envío (P6/P8) con estado "abierto → enviado"
- [ ] Web: notificaciones in-app (badge + list) para respuestas inbound
- [ ] Web: sección de conexión WhatsApp Business en Configuración (guía + estado)
- [ ] Tests: pytest de templates (encoding, acentos), normalización telefónica, idempotencia del webhook (fijo de fixtures de Meta); Vitest de CTAs
- [ ] GA4: `whatsapp_budget_sent`, `whatsapp_order_sent`, `wa_inbound_received`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Button` (CTA con ícono WhatsApp), `Alert` (estado de conexión), `Switch` (toggles), `Field.Root` (credenciales), `Badge` (notificaciones).
- El CTA de envío es el primario de la pantalla en P6/P8: "Enviar por WhatsApp" (green-only icon, no cambiar la paleta: el botón sigue blue, el ícono comunica el canal).
- Tokens: success al confirmar envío; warning si falta teléfono del cliente ("completá el teléfono del cliente para enviar").
