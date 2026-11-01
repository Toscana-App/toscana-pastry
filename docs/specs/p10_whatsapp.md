# P10 — WhatsApp (envío + bot)
Módulo: `web/modules/whatsapp` + `api/bot` (Chat SDK) · Rutas: CTA en P6/P8; webhook `/webhooks/whatsapp` · Fase: **3**

## Contexto
Flujo verificado: "Con un toque se arma el mensaje solo, detallando cada producto y el total" (FAQ). Dos capas:
1. **Outbound (siempre)**: link `wa.me/?text=` prellenado — el cliente final recibe el mensaje desde el WhatsApp de la repostera. Cero costo, sin Cloud API.
2. **Inbound (opcional)**: bot del negocio con **Chat SDK** (Vercel) sobre WhatsApp Business Cloud API para que el cliente responda y el negocio sea notificado.
3. **Outbound Business (upgrade opcional, RF-P10-07)**: cuando el tenant tiene Business API conectada (UC-03), el envío sale directo por la API (no requiere que la dueña abra WhatsApp) y el registro del envío gana estados de entrega/lectura. Patrón de referencia: `BroadcastsPlugin` de `toscana-demo` (Kapso/Cloud API con estados y métricas).

## User story
> Como **repostera**, quiero **enviar el presupuesto/pedido al WhatsApp de la clienta con un toque y ser notificada cuando me responda**, para **cerrar ventas sin salir de mi flujo de trabajo**.

**Criterios de aceptación**
- [ ] "Enviar por WhatsApp" abre el WhatsApp con el mensaje armado (ítems, totales, mi firma).
- [ ] El envío queda registrado (fecha + a quién).
- [ ] Si conecto mi WhatsApp Business: cuando el cliente responde, recibo una notificación en la app (y opcionalmente un reply automático con el último presupuesto).
- [ ] Sin Cloud API conectada, la app funciona 100% (wa.me) — el inbound es un toggle, no una dependencia.
- [ ] Con Business API conectada, el envío es directo (sin abrir WhatsApp) y veo su estado (enviado / entregado / leído / fallido) y puedo reintentar los fallidos.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Enviar presupuesto por WhatsApp | Repostera | CTA → wa.me prellenado → abierto → "enviado" marcado |
| UC-02 Enviar precio de pedido | Repostera | "Le paso $X" → wa.me → abierto |
| UC-03 Conectar WhatsApp Business | Repostera | Settings → Cloud API (token + phone number id) → webhook verificado |
| UC-04 Recibir respuesta del cliente | Bot | Webhook → Chat SDK → notificación in-app (badge en presupuesto/pedido) |
| UC-05 Reply automático | Bot | Cliente escribe → bot responde con el último presupuesto enviado (template) |
| UC-06 Envío directo por Business API | Repostera | CTA → la API envía el template (no wa.me) → registro con estados |
| UC-07 Ver estados y reintentar | Repostera | Lista de envíos: `sent/delivered/read/failed` → reintentar fallido |

## Requerimientos funcionales
- **RF-P10-01**: Genera un link `wa.me/{phone}?text={mensaje}` con template: saludo con nombre, ítems (qty × producto — precio, + **tags de restricción** si existen), **dirección de entrega** (si está presente), total, firma del negocio; URL-encode correcto (es-AR, $, ñ). (UC-01/02)
- **RF-P10-02**: Generación de link `https://wa.me/{phone}?text=...` (teléfono normalizado a E.164, +54 default si formato local) + registro del evento (`whatsapp_sent`). (UC-01/02)
- **RF-P10-03**: Chat SDK: `new Chat({ adapters: { whatsapp: createWhatsAppAdapter() }, state: createRedisState() })`; webhook verificado (signature); handler `onSubscribedMessage` → notificación in-app al owner. (UC-04)
- **RF-P10-04**: Reply automático opcional (toggle por tenant): al recibir mensaje en un thread con presupuesto asociado, responde con el resumen de ese presupuesto. (UC-05)
- **RF-P10-05**: Conexión Cloud API: guardado de credenciales (solo backend), estado de conexión (conectado/desconectado/errores), guía de configuración. (UC-03)
- **RF-P10-06**: Rate limiting de outbound (máx. 30 links/día por tenant) para evitar abuso. (UC-01)
- **RF-P10-07**: Upgrade de outbound a Business API (opcional por tenant, usa la conexión de UC-03): interfaz `WhatsAppProvider` con dos implementaciones — `WaMeProvider` (actual: genera link `wa.me`, estado `sent` fijo) y `BusinessApiProvider` (envía el template directo y devuelve `message_id`). Registro de envío (`whatsapp_send`): `status ∈ {sent, delivered, read, failed}` (default `sent`), `delivered_at?`, `read_at?`, `failed_reason?`; webhook inbound actualiza el estado (dedupe por `message_id`, RNF-P10-02). Sin Business API conectada → `WaMeProvider` (sin cambios, RNF-P10-04). (UC-06)
- **RF-P10-08**: Reintento de fallidos: `POST /whatsapp/sends/{id}/resend` (solo `status=failed` y `provider=business_api`; reenvía el mismo template → 409 si no es fallido); métricas por tenant en `GET /whatsapp/sends/stats` → `{total, sent, delivered, read, failed, read_rate}` (ventana 30 días); `GET /whatsapp/sends?status,from,to,page,page_size` (solo el owner). (UC-07)

## Requerimientos no funcionales
- **RNF-P10-01**: **Cero tokens de WhatsApp/Cloud API en el frontend** — todo por endpoints de la API. (crítico)
- **RNF-P10-02**: Webhook idempotente (dedupe por message_id) y tolerante a reintentos de Meta.
- **RNF-P10-03**: Latencia de notificación inbound < 5 s (webhook → Redis → polling/SSE de la app).
- **RNF-P10-04**: Sin Cloud API conectada: degradación limpia (toggle deshabilitado, wa.me sigue funcionando).
- **RNF-P10-05**: Logs sin números de teléfono completos (mascarados: +54 9 11 ** ****12).
- **RNF-P10-06**: Budget de envíos directos por Business API: máx. 500 mensajes/día por tenant (fuera de ese límite → 429 con día de reintentos sugerido); los reintentos cuentan contra el mismo budget. Sin Cloud API, no aplica (wa.me sigue bajo RF-P10-06).

## Tareas
- [ ] API: `POST /budgets/{id}/whatsapp-link`, `POST /orders/{id}/whatsapp-link` (template + registro + rate limit)
- [ ] Domain: template de mensajes, normalización E.164, reglas de máscaras en logs
- [ ] `api/bot`: Chat SDK + `@chat-adapter/whatsapp` + `createRedisState` (verificar adapter actual en chat-sdk.dev/adapters)
- [ ] API: webhook `/webhooks/whatsapp` (verificación de firma, idempotencia, routing por thread)
- [ ] API: `GET/PUT /tenant/whatsapp` (credenciales, estado, toggles)
- [ ] API: registro `whatsapp_send` con estados (`sent/delivered/read/failed`) + `GET /whatsapp/sends` + `GET /whatsapp/sends/stats` + `POST /whatsapp/sends/{id}/resend` (RF-P10-08)
- [ ] Domain: `WhatsAppProvider` (`WaMeProvider` / `BusinessApiProvider`) + transiciones de estado de envío (idempotentes)
- [ ] Web: CTAs de envío (P6/P8) con estado "abierto → enviado"
- [ ] Web: notificaciones in-app (badge + list) para respuestas inbound
- [ ] Web: sección de conexión WhatsApp Business en Configuración (guía + estado)
- [ ] Tests: pytest de templates (encoding, acentos), normalización telefónica, idempotencia del webhook (fijo de fixtures de Meta); Vitest de CTAs
- [ ] GA4: `whatsapp_budget_sent`, `whatsapp_order_sent`, `wa_inbound_received`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Button` (CTA con ícono WhatsApp), `Alert` (estado de conexión), `Switch` (toggles), `Field.Root` (credenciales), `Badge` (notificaciones).
- El CTA de envío es el primario de la pantalla en P6/P8: "Enviar por WhatsApp" (green-only icon, no cambiar la paleta: el botón sigue blue, el ícono comunica el canal).
- Tokens: success al confirmar envío; warning si falta teléfono del cliente ("completá el teléfono del cliente para enviar").
- Envíos (P6/P8, solo con Business API): badge de estado por envío (`Enviado` neutral / `Entregado` info / `Leído` success / `Fallido` danger + motivo) + CTA secundario "Reintentar" solo sobre `failed`.
