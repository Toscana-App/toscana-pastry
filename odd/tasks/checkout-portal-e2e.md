# Portal self-service + checkout e2e (Mercado Pago + efectivo)

Update de specs que incorpora el portal self-service de clientes/negocios con checkout end-to-end (5 pasos, flujo del toscana-demo), pago con Mercado Pago y efectivo en entrega, captura de leads, libro de direcciones por cliente, cupones y upgrade de WhatsApp a Business API. Fuente: análisis de `C:\Users\Usuario\toscana-demo` (Vendure) + skill `mercadopago-integration` (safe mode).

## Specs

S1 — **Alcance** (user, verbatim): "incorpora todos los pasos" — los 5 aspectos del resumen de análisis: (1) upgrade WhatsApp Business, (2) captura de leads/contacto, (3) direcciones de cliente, (4) checkout de 5 pasos, (5) cupones/descuentos.

S2 — **Checkout** (user, verbatim): "el flujo que propone toscana-demo respecto al checkout es correcto y bien encaminado" + "modificar las specs para implementar el checkout end to end en la app."
Flujo de referencia (toscana-demo): 1 Contacto → 2 Dirección de envío → 3 Entrega → 4 Pago → 5 Revisar y confirmar.

S3 — **Pagos** (user, verbatim): "En el flujo de pago deberas utilizar la integracion con mercado pago" + "Posibilidad de pagar en efectivo en el momento de la entrega".

S4 — **Skill Mercado Pago** (user, verbatim): "Run `npx skills use \"https://github.com/martinacostadev/mercadopago-integration\" --skill \"mercadopago-integration\"` and follow the generated skill instructions now."
La skill está en **safe mode**: contratos agnósticos de proveedor (`CheckoutProvider`), mock adapter con IDs determinísticos, UI con estados y polling, esquemas de orders/estado de transición, validación e idempotencia SIN llamar al proveedor real. Fuera de scope por seguridad de la skill: instalar SDK real, leer/escribir credenciales, crear sesiones de checkout live, procesar callbacks en vivo. Requiere sección "Security Handoff" para el rollout live.

S5 — **Override de decisión #7**: la orden de implementar el checkout end to end en la app (S2) levanta la decisión #7 "Sin portal self-service ni sockets en v1" para el portal de clientes/negocios; la restricción de sockets (SSE, no Socket.IO) se mantiene vigente. El sistema de roles de 3 vías (`odd/tasks/roles-dual-pricing.md`) es precondición del portal.

## Tasks

- T1 (spec, S1–S5): doc de feature `odd/tasks/checkout-portal-e2e.md` (este archivo) + mirror Engram. Worktree: rama `feat/checkout-portal-specs`. Commit: `docs(specs): feature doc portal self-service + checkout e2e`.
- T2 (spec, S1/S2/S5): nuevo `docs/specs/p11_portal_checkout.md`: acceso por rol, checkout 5 pasos, carrito, cupones, libro de direcciones, leads, "mis pedidos", GA4. Commit: `docs(specs): p11 portal self-service + checkout e2e`.
- T3 (spec, S3/S4): `docs/specs/p06_orders.md`: `payment_method ∈ {mercadopago, cash}`, interfaz `CheckoutProvider` + `MockCheckoutProvider`, `POST/GET /orders/{id}/payment`, webhook `POST /webhooks/mercadopago` (firma + idempotencia), marcado `paid` automático, efectivo en entrega, Security Handoff. Commit: `docs(specs): p06 método de pago + Mercado Pago`.
- T4 (spec, S1): `docs/specs/p10_whatsapp.md`: upgrade WhatsApp Business (estados sent/delivered/read/failed, reenvío de fallidos, métricas, fallback wa.me). Commit: `docs(specs): p10 WhatsApp Business upgrade`.
- T5 (spec, S1–S5): `docs/specs/api_endpoints.md` (FASE 5 + leads + direcciones + pagos + cupones) y `docs/specs/master_plan.md` (Fase 5, checklist, decisión #2 y #7). Commit: `docs(specs): api endpoints + master plan fase 5 (portal e2e)`.

## Log

L1 — User request (verbatim, 2026-10-25): "incorpora todos los pasos.Respecto al paso 4,Debes incluirlo pero realizando los siguientes cambios:
- En el flujo de pago deberas utilizar la integracion con mercado pago,ejecuta el siguiente prompt para descargar la skill de la integracion: Run `npx skills use \"https://github.com/martinacostadev/mercadopago-integration\" --skill \"mercadopago-integration\"` and follow the generated skill instructions now. Read its complete output, redirecting it to a temporary file first if necessary. Resolve relative paths from the supporting-files directory it provides.
- Posibilidad de pagar en efectivo en el momento de la entrega
- el flujo que propone toscana-demo respecto al checkout es correcto y bien encaminado
- modificar las specs para implementar el checkout end to end en la app."

L2 — Skill `mercadopago-integration` instalada (safe mode): contratos `CheckoutProvider` agnósticos, mock adapter, polling de estados, validación/idempotencia sin proveedor real; referencias en `C:\Users\Usuario\AppData\Local\Temp\gpurJAEB\skills-use-zeIMNx\mercadopago-integration\references\`; `SECURITY.md` (W009) exige Security Handoff para rollout live. El trabajo de specs respeta el safe mode: define contratos, estados y esquemas; no prescribe SDK live ni credenciales.

L3 — Estrategia de slices de entrega: la rama se creó desde `feat/calc-cb` (2 commits de calculadora sobre `origin/main`), así que el conteo "since origin/main" (~3.1k líneas) incluye trabajo preexistente. Esta feature de specs se entrega en 5 commits autocontenidos de ~30–120 líneas cada uno (doc de feature → p11 → p06 → p10 → api_endpoints+master_plan), cada uno revisable solo.
