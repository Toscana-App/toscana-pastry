# Endpoints API — FastAPI (plan por fases P1–P10)

> Documento de **planificación** de la superficie REST. Cada endpoint queda con método, ruta, propósito, payload/respuesta, auth, códigos y notas.
> Stack: FastAPI + SQLAlchemy (async) + Postgres + Pydantic v2. Contratos generados a TS en CI (OpenAPI).
> Fuente: `master_plan.md` §2 (mapeo) + tareas de cada `pXX_*.md`.
> Estado: **propuesta** — pendiente de revisión por Gaspar antes de Fase 0.

---

## 0. Convenciones transversales (se aplican a TODOS los endpoints)

| Aspecto | Regla |
|---|---|
| Versionado | Prefijo `/api/v1`. Rompes → `/api/v2`. |
| Base | `https://<host>/api/v1` (TLS forzado, HSTS). |
| Multi-tenancy | `tenant_id` **inyectado por dependencia** desde la sesión. NUNCA lo acepta el cliente en body/query. Middleware + repositorio verifican el scope. |
| Auth | JWT en cookie `httpOnly; Secure; SameSite=Strict`. Dependencia `get_current_user` → `(user, tenant)`. Endpoints públicos marcados explícitamente. |
| Paginación | `?page` (1-based) + `?page_size` (default 50, max 200). Respuesta envuelta: `{ "items": [...], "total": N, "page": n, "page_size": n }`. |
| Filtros | Query params (`q`, `status`, `category`, `from`, `to`). Búsqueda `q` case/acento-insensitive (pg_trgm). |
| Errores | Envelope `application/problem+json`: `{ "type", "title", "status", "detail", "errors": [ {field, msg} ] }`. 422 para validación de schema (FastAPI), 409 para conflictos de negocio. |
| Idempotencia | Header `Idempotency-Key` obligatorio en: `purchase/redeem`, `orders/{id}/status` (confirmar), `budgets/{id}/send`. Re-intento con misma key = mismo resultado. |
| Rate limiting | `slowapi`: `auth/*` y formularios públicos con tope por IP+email (ver §F0/F4). |
| Anti-spam | hCaptcha en `auth/magic-link` (público) y contacto. Honeypot oculto. |
| Login Google | Flujo GIS **ID token** (no authorization-code): `sub` → `google_id` (identidad, nunca email); nonce server-issued de un solo uso; `email_verified`; **link solo tras re-auth** (`magic-link` → `verify` con `purpose=google_link`); Google no crea cuentas. `GOOGLE_CLIENT_ID` público; client secret inexistente en la app. (skill `google-signin`) |
| Decimal | Todo monto con `Decimal` (serializado como string en JSON) + `ROUND_HALF_UP` al paso configurado. |
| OpenAPI | `GET /openapi.json` + docs `/docs` (FastAPI) — **fuente** de los tipos TS de `web/lib`. En producción: cerrados o detrás de auth (security #12). |
| RLS | Postgres **Row-Level Security** en toda tabla de tenant; `set_config('app.tenant_id')` por transacción. Objeto de otro tenant → 404 (security #4, #7). |
| Queries | Solo SQLAlchemy con **bind parameters**; prohibido SQL concatenado (security #13). |
| Validación | Pydantic v2 estricto: allow-lists (`unit`, `status`, `reason`), longitudes máximas, bordes de montos; `extra="forbid"` en todos los esquemas (security #8, #14). |
| Campos computados | `price`, `total`, `breakdown`, `seq`, `stock_qty`, `status` = **solo-escritura del servidor** (motor de precio + secuencias Postgres). Nunca llegan del cliente (security #8). |
| Cifrado | Fernet en `customer.phone`/`customer.email` (rotación doble clave); tokens de auth **solo como hash SHA-256**, ≥256 bits (security #5, #10). |
| Sesión | JWT httpOnly con **TTL corto (15–30 min) + rotación** en verify; logout invalida server-side (security #9). |
| Datos devueltos | Schemas **Response** explícitos; `costs`/`breakdown`/margen **solo** al usuario del tenant — nunca en PDF ni WhatsApp (security #17). |
| Archivos | v1 **sin uploads de usuario**; PDF solo autenticado o URL firmada (expiración ≤ 1 h, single-use) (security #16). |
| Headers / HTTPS | Edge (Caddy): HSTS preload, CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`; TLS con redirect 301 (security #18, #19). |
| Secrets | Cero `NEXT_PUBLIC_*`; Postgres en red interna con usuario dedicado (sin puerto expuesto); `gitleaks` en repo y en el build (security #1–3). |
| Dependencias | `pip-audit` + `pnpm audit` en CI (fail on high) + Dependabot; lockfiles comprometidos (security #20). |

### Rate limiting por endpoint (`slowapi` — security #11)
| Endpoint | Límite | Exceso |
|---|---|---|
| `POST /auth/magic-link` | 3/h por email · 10/h por IP | 429 + `Retry-After` |
| `POST /auth/verify` | 10/h por IP | 429 |
| `GET /auth/google/nonce` | 60/h por IP | 429 |
| `POST /auth/google/signin` | 10/h por IP | 429 |
| `POST /auth/purchase/redeem` | 5/h por IP | 429 |
| `POST /contact` (si existe) | 5/h por IP | 429 |
| `POST /ingredients/import` | 10/h por usuario | 429 |
| Todas las escrituras (POST/PATCH/DELETE) | 60/min por usuario | 429 |
| Global (todas las rutas) | 300/min por IP | 429 |

Headers en cada respuesta: `X-RateLimit-Limit`, `X-RateLimit-Remaining`; en 429 agrega `Retry-After`.
Protección contra bots (security #12): hCaptcha server-side en `magic-link` (y contacto) + honeypot oculto; webhook de WhatsApp con verificación de firma y dedupe.

### Estructura de routers (un `APIRouter` por módulo)
```
api/presentation/routers/
├── system.py      # health/ready
├── auth.py        # F0
├── tenant.py      # F0 (info) + F1 (settings)
├── ingredients.py # F1
├── products.py    # F1
├── customers.py   # F2
├── orders.py      # F2
├── budgets.py     # F3
├── pdf.py         # F3
└── webhooks.py    # F3/F4 (whatsapp)
```

---

## FASE 0 — Fundaciones
> Objetivo: staging vivo con login. 10 endpoints core.

### System
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/health` | Liveness (sin dependencias). | — → `{"status":"ok"}` | 200 | Sin auth. Para probe de contenedor. |
| GET | `/api/v1/ready` | Readiness (chequea DB). | — → `{"status":"ready","db":true}` | 200/503 | 503 si DB caído. Sin auth. |

### Auth (P1)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| POST | `/api/v1/auth/magic-link` | Solicita magic link por email. | `{email, captcha?}` → `{"sent":true}` | 202 | **Siempre 202** (evita enumeración). TTL 15 min. Rate: 3/hora por email. hCaptcha. |
| POST | `/api/v1/auth/verify` | Verifica token del link → sesión. | `{token}` → `{user, redirect}` + cookie httpOnly | 200 / 400 | Token un solo uso. Si cuenta nueva → `redirect=/onboarding/tenant`. Si ya hay sesión → `redirect=/`. Si `purpose=google_link` → completa el enlace Google y emite sesión. Rate: 10/ip. |
| GET | `/api/v1/auth/google/nonce` | Nonce GIS pre-auth para el botón Google. | — → `{nonce}` + cookie pre-auth httpOnly | 200 | Público. Nonce server-issued, TTL ≈ 5 min, **un solo uso**. Rate: 60/ip. |
| POST | `/api/v1/auth/google/signin` | Login GIS: verifica ID token y resuelve identidad/enlace. | `{credential}` → `{user?, state?}` + cookie sesión | 200 / 401 | Público (login-CSRF: `Sec-Fetch-Site` same-origin, fail-closed, **antes** de verificar). Verifica JWKS, `aud`, `iss`, `exp`, `email_verified`, nonce == cookie (pop, un solo uso). Estados: `no_account` (no crea — registro gated por compra) / `needs_reauth` (link pendiente vía `magic-link` + `verify`) / sesión. Rate: 10/ip. |
| POST | `/api/v1/auth/purchase/redeem` | Canjea token de compra (idempotente). | `{token}` → `{user, tenant}` | 201 / 409 | Crea user+tenant. Doble canje = 409. Header `Idempotency-Key`. |
| POST | `/api/v1/auth/logout` | Invalida la sesión. | — → `204` | 204 | Borra/invalidate token (todos los dispositivos). |
| GET | `/api/v1/me` | Perfil del usuario actual. | — → `{user, tenant_id}` | 200 / 401 | |
| PATCH | `/api/v1/me` | (opcional) actualiza perfil. | `{display_name?}` → `{user}` | 200 | |

### Tenant (onboarding P1)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| POST | `/api/v1/tenant` | Alta de negocio (onboarding 3 campos). | `{name*, currency(=ARS), city?}` → `{tenant}` | 201 | Si ya existe para el usuario → 409. |
| GET | `/api/v1/tenant` | Info del tenant. | — → `{tenant}` | 200 / 404 | |
| PUT | `/api/v1/tenant` | Actualiza nombre/moneda/ciudad. | `{name?, currency?, city?}` → `{tenant}` | 200 | Los costos/márgenes van por `/settings` (F1). |

**Criterio de salida F0**: con `magic-link` + `verify` + `tenant` el usuario entra al shell; el botón Google funciona como vía alternativa cuando `GOOGLE_CLIENT_ID` está configurado (de lo contrario, oculto).

---

## FASE 1 — Motor de precio + catálogo
> Objetivo: el negocio calcula costos reales. ~16 endpoints.

### Settings / costos (P5)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/tenant/settings` | Config de costos por defecto. | — → `{hourly_rate, margin_pct, round_step, include_labor, include_gas, gas_pct, include_waste, waste_pct, urgent_surcharge_pct}` | 200 | Defaults del motor de precio. |
| PUT | `/api/v1/tenant/settings` | Actualiza config. | `{...settings}` → `{settings, affected_products: N}` | 200 | Dispara **recálculo global** (derivado). `affected_products` = precios re-derivados. |
| POST | `/api/v1/tenant/settings/recalculate` | Fuerza recálculo global (idempotente). | — → `{recalculated: N}` | 200 | (opcional) Task asíncrona si catálogo grande. |
| GET | `/api/v1/tenant/order-window` | Ventana de pedidos (corte). | — → `{open, reopens_at?, message?}` | 200 | Auth. Alimenta el banner de P6. (RF-P5-07) |
| PATCH | `/api/v1/tenant/order-window` | Abre/cierra pedidos. | `{open*, reopens_at?, message?}` → `{order_window}` | 200 / 422 | Cerrar sin `reopens_at` → 422 con sugerencia. `message` ≤ 200 chars. (RF-P5-07) |

### Ingredientes (P2)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/ingredients` | Lista con búsqueda/paginación. | `?q,page,page_size,status?` → `{items,total,...}` | 200 | Item: `id,name,unit,price_per_unit,stock_qty,low_stock_threshold,status(OK/LOW/EMPTY)`. pg_trgm. |
| POST | `/api/v1/ingredients` | Crea ingrediente. | `{name*,unit,price_per_unit,stock_qty?,low_stock_threshold?}` → `{ingredient}` | 201 | `unit ∈ {kg,g,L,ml,unidad}`. |
| GET | `/api/v1/ingredients/{id}` | Detalle. | — → `{ingredient, movements?}` | 200 / 404 | |
| PATCH | `/api/v1/ingredients/{id}` | Edita (nombre/unidad/precio/umbral). | `{...}` → `{ingredient}` | 200 | Cambia precio → marca productos "incompleto/obsoleto". |
| DELETE | `/api/v1/ingredients/{id}` | Elimina. | — → `204` | 204 / 409 | Si participa en recetas activas → 409 + `{impacted_recipes:N}`. Sin recetas → soft delete + undo. |
| POST | `/api/v1/ingredients/import` | Import por lista (carga rápida). | `{lines:["harina 0000, 5, 2800",...]}` → `{created:N, errors:[{line,msg}]}` | 201 | (RF-P2-07). Parsing tolerante; reporta filas en error. |
| POST | `/api/v1/ingredients/{id}/stock` | Ajuste de stock (+/−). | `{delta, reason(compra/merma/ajuste), ref?}` → `{stock_qty, movement}` | 200 / 400 | Registra `stock_movement`. No negativo (400). |
| GET | `/api/v1/ingredients/{id}/movements` | Historial de movimientos. | `?page,page_size` → `{items,total,...}` | 200 | `{qty_delta, reason, ref, created_at}`. |

### Productos (P3 listado + P4 detalle)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/products` | Listado con filtros. | `?q,category,tags,page,page_size` → `{items,total,...}` | 200 | Item: `id,name,category,tags[],price(final, derived)`. `tags` = lista (AND). Precios del motor. |
| GET | `/api/v1/products/categories` | Chips de categoría. | — → `{categories:[{name,count}]}` | 200 | Distinct por tenant. |
| GET | `/api/v1/products/tags` | Chips de tags (restricciones). | — → `{tags:[{name,count}]}` | 200 | Distinct por tenant (allow-list sugerida + libres). |
| POST | `/api/v1/products` | Crea producto + receta. | `{name*,description?,category*,type?,storage?,prep_time_min*,servings?,difficulty?,labor_hours*,tags[]?,recipe_items:[{ingredient_id,qty,unit}]}` → `{product, costs}` | 201 | Validación ≥1 insumo; `tags[]` 0–10, ≤ 30 chars c/u. Devuelve desglose del motor. |
| GET | `/api/v1/products/{id}` | Detalle con receta + costos. | — → `{product, recipe_items, costs_breakdown}` | 200 / 404 | `costs_breakdown`: materials, labor, gas, waste, base, margin_pct, final, rounded. |
| PATCH | `/api/v1/products/{id}` | Edita (cualquier tab). | `{...campos, tags[], recipe_items?}` → `{product, costs}` | 200 | Receta editada → recálculo automático. |
| DELETE | `/api/v1/products/{id}` | Elimina. | — → `204` | 204 / 409 | Soft delete si tiene pedidos históricos. |
| POST | `/api/v1/products/{id}/recalculate` | Recalcula desglose (en vivo). | — → `{costs_breakdown}` | 200 | < 50 ms hasta 50 insumos. (RF-P4-04) |

**Criterio de salida F1**: 20 insumos + 5 productos → cada producto muestra costo y precio final correctos (verificados contra la fórmula).

---

## FASE 2 — Pedidos y stock
> Objetivo: operación diaria de pedidos. ~13 endpoints.

### Clientes (necesario para pedidos)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/customers` | Lista de clientes. | `?q,page,page_size` → `{items,total,...}` | 200 | `{id,name,phone,email}`. |
| POST | `/api/v1/customers` | Crea cliente. | `{name*, phone?, email?, delivery_address?}` → `{customer}` | 201 / 409 | **Sin duplicados exactos** por (name+phone) → 409. (RF-P6-08) |
| GET | `/api/v1/customers/{id}` | Detalle. | — → `{customer, orders?}` | 200 / 404 | |
| PATCH | `/api/v1/customers/{id}` | Edita. | `{...}` → `{customer}` | 200 | |
| DELETE | `/api/v1/customers/{id}` | Elimina. | — → `204` | 204 / 409 | 409 si tiene pedidos. |

### Pedidos (P6)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/orders` | Lista con filtros. | `?customer,status,paid,from,to,q,page,page_size` → `{items,total,...}` | 200 | Item: `id,customer,status,paid,final_price,date`. |
| POST | `/api/v1/orders` | Crea pedido. | `{customer_id*, date?, margin_pct?(override), items:[{product_id,qty,portion_note?}]}` → `{order, breakdown}` | 201 / 409 | **No descuenta stock** (descuenta al confirmar). Snapshot de precios. Si `order_window_open=false` → 409 `order_window_closed` + mensaje (RF-P6-09). |
| GET | `/api/v1/orders/{id}` | Detalle con desglose. | — → `{order, items, breakdown}` | 200 / 404 | `breakdown`: materiales (por insumo), labor, gas, margin_pct, gain, final, rounded. Inmutable (snapshot). |
| PATCH | `/api/v1/orders/{id}` | Edita ítems / margen override. | `{items?, margin_pct?}` → `{order, breakdown}` | 200 | Solo si `status=nuevo`. Recalcula. |
| PATCH | `/api/v1/orders/{id}/status` | Transición de estado. | `{status}` → `{order}` | 200 / 409 | `nuevo→confirmado` = **descuento atómico** de stock (`SELECT…FOR UPDATE`); si falta → 409 + insumo faltante, sin cambios. `→entregado`. `→cancelado` (desde confirmado) = re-pozo de stock. Header `Idempotency-Key` en confirmar. |
| DELETE | `/api/v1/orders/{id}` | Elimina. | — → `204` | 204 / 409 | Solo `nuevo` (o `cancelado`). |
| POST | `/api/v1/orders/{id}/whatsapp-link` | Genera + registra `wa.me`. | — → `{url, sent_at}` | 200 | Template: saludo + ítems con precios + total. (CTA "Le paso $X"). |
| PATCH | `/api/v1/orders/{id}/paid` | Marca pago (independiente del estado). | `{paid: bool}` → `{order}` | 200 / 404 | Campo server-managed; no toca estado ni stock. (RF-P6-10) |
| GET | `/api/v1/orders/weekly` | Resumen de la semana. | `?week?` → `{week:{from,to}, items, totals:{amount,paid,unpaid}}` | 200 | Semana natural Lun–Dom; pedidos `confirmado`/`entregado`. (RF-P6-11) |
| GET | `/api/v1/orders/export` | Export CSV. | `?from,to,status,paid` → `text/csv` | 200 | Columnas: id, cliente, fecha, ítems, total, estado, pago. Streaming. (RF-P6-11) |
| GET | `/api/v1/orders/{id}/quote` | (opcional) preview/recalcula cotización. | — → `{breakdown}` | 200 | |

**Criterio de salida F2**: pedido → stock descuenta, precio cuadra con la fórmula, no se permite stock negativo (concurrency: 2 confirmaciones simultáneas → 1 gana, 1 → 409).

---

## FASE 3 — Presupuestos + PDF + WhatsApp
> Objetivo: ciclo completo presupuesto→cliente. ~14 endpoints.

### Presupuestos (P7 wizard + P8 resumen)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| POST | `/api/v1/budgets` | Crea presupuesto (wizard completo). | `{customer:{...}o customer_id (con delivery_address?), delivery_date?, notes?, items:[{product_id,qty,unit_price?(override manual)}], margin_pct?(override), calc_mode(cost_plus/manual)}` → `{budget, seq, summary}` | 201 | Asigna `seq` `#000NN` por tenant (row lock, gap permitido). Snapshot de cálculo. |
| GET | `/api/v1/budgets` | Lista de presupuestos. | `?q,from,to,status,page,page_size` → `{items,total,...}` | 200 | Item: `seq,customer,final, status(borrador/enviado), date`. |
| GET | `/api/v1/budgets/{id}` | Detalle con ítems + cálculo. | — → `{budget, items, summary}` | 200 / 404 | `summary`: subtotal, total_costos, gain_pct, gain_amount, total_venta. Consistente (invariantes). |
| PUT | `/api/v1/budgets/{id}` | Actualiza presupuesto. | `{...campos, items?}` → `{budget, summary}` | 200 | Solo `borrador`. Reenviar tras editar genera **nueva versión**. |
| PATCH | `/api/v1/budgets/{id}/items` | Ajusta cantidades/ítems. | `{items:[{product_id,qty,unit_price?}]}` → `{summary}` | 200 | Recalcula < 50 ms. (RF-P8-02) |
| DELETE | `/api/v1/budgets/{id}` | Elimina. | — → `204` | 204 | **No toca stock ni pedidos**. |
| POST | `/api/v1/budgets/{id}/recalculate` | Recalcula resumen. | — → `{summary}` | 200 | Modo cost-plus o manual (explícito en UI). |
| POST | `/api/v1/budgets/{id}/convert-to-order` | Convierte en pedido. | — → `{order}` | 201 | Crea pedido con mismos ítems (F2). |
| POST | `/api/v1/budgets/{id}/send` | Marca enviado (congela versión). | — → `{budget, sent_at}` | 200 / 409 | `borrador→enviado`; snapshot inmutable por versión (auditoría). Header `Idempotency-Key`. |

### PDF (P9)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/budgets/{id}/pdf` | Devuelve/genera PDF. | — → `application/pdf` (stream) | 200 / 404 | Server-side (ReportLab/WeasyPrint). Branding del tenant, **sin costos internos**. Cache por hash de contenido; invalidado al editar. |
| POST | `/api/v1/budgets/{id}/pdf` | (opcional) genera + devuelve link temporal firmado. | — → `{url, expires_at}` | 200 | Link temporal con expiración (no expone el file estático). |
| GET | `/api/v1/budgets/export` | Export CSV de presupuestos. | `?from,to,status` → `text/csv` | 200 | Columnas: seq, cliente, fecha, entrega, total venta, estado. (RF-P6-11) |

### WhatsApp (P10)
| Método | Ruta | Descripción | Payload → Respuesta | Códigos | Notas |
|---|---|---|---|---|---|
| GET | `/api/v1/budgets/{id}/whatsapp-link` | Genera + registra `wa.me` (outbound). | — → `{url, sent_at}` | 200 | `wa.me/?text=` (ítems + total). Gratis, sin Cloud API. (CTA "Enviar por WhatsApp"). |
| POST | `/api/v1/webhooks/whatsapp` | Webhook inbound (Chat SDK, opcional). | payload Cloud API → `200 {"ok":true}` | 200 | **Verifica firma** (X-Hub-Signature / Cloud API). Handler `onNewMention`/`onSubscribedMessage`. State en Redis (`createRedisState`). |
| GET | `/api/v1/webhooks/whatsapp/verify` | Handshake de verificación Cloud API. | `?hub.mode, hub.verify_token, hub.challenge` → `challenge` (text) | 200 | Solo si se habilita inbound. Confirma ownership del webhook. |

**Criterio de salida F3**: presupuesto desde cero → PDF descargado → enviado por WhatsApp con un toque; (opcional) bot responde al cliente.

---

## FASE 4 — Endurecimiento y producción
> No agrega endpoints de negocio. Endurece los existentes + cross-cutting.

| Área | Qué toca en la API |
|---|---|
| Seguridad | Cero secrets en bundle frontend (env solo backend, whitelist `NEXT_PUBLIC_*`). Rate limiting reforzado en `auth/*` y formularios. HSTS. |
| Anti-spam | hCaptcha verificado en `auth/magic-link` (+ contacto si existe). Honeypot. |
| Idempotencia | Claves obligatorias validadas en `purchase/redeem`, `orders/{id}/status`, `budgets/{id}/send`. |
| Webhook | Verificación de firma estricta + replay (dedupe por `entry.id` / timestamp). |
| Observabilidad | Request logging estructurado + tracing (Sentry) en todos los endpoints. |
| Legal | Páginas `privacy`/`terms` = estáticas de Next.js (sin API). |
| (opcional) Contacto | `POST /api/v1/contact` `{name,email,message,captcha}` → 202, con hCaptcha + rate limit. Solo si hay página de contacto. |

**Criterio de salida F4**: Lighthouse ≥ 90 (4 categorías), checklist de seguridad 100%, legal publicado, sin warnings de build.

---

## Resumen (conteo por fase)

| Fase | Endpoints core | Routers |
|---|---|---|
| F0 Fundaciones | 12 | system, auth, auth-google, tenant |
| F1 Motor + catálogo | 18 | tenant(settings+order-window), ingredients, products |
| F2 Pedidos y stock | 16 | customers, orders |
| F3 Presupuestos + PDF + WhatsApp | 15 | budgets, pdf, webhooks |
| F4 Endurecimiento | 0 nuevos (+1 opcional contacto) | cross-cutting |
| **Total** | **~61** | 10 routers |

### Endpoints aún por confirmar con Gaspar
1. `/tenant/settings/recalculate` (F1): ¿recálculo global síncrono o task asíncrona? (impacta UX si catálogo grande).
2. `budgets` (F3): ¿el wizard hace 1 `POST /budgets` con todo, o endpoints por paso (crear borrador → añadir ítems → enviar)? Aquí puse 1 POST + `PATCH items`.
3. `orders/{id}/quote` (F2): ¿se necesita como endpoint separado o basta con `PATCH` + `GET`?
4. Contacto: ¿existe página de contacto en el producto? (define si entra `POST /contact`).
5. Inbound WhatsApp (F3/F4): ¿se habilita en la v1 o se deja out-of-scope? (define si `webhooks/whatsapp` es obligatorio o opcional de fase).
6. `tenant/order-window` (F1): GET autenticado (decisión actual: v1 no tiene catálogo público, el banner solo aparece dentro de la app). Si aparece un catálogo público, el GET pasa a la allow-list de `security.md` #6.

---

## Seguridad — conformidad con los 20 ítems obligatorios
Cada endpoint de este documento cumple `security.md` (20 ítems, **sin excepción**):
- **Auth por defecto** con allow-list de 9 endpoints públicos (#6) · **RLS** por tenant + 404 anti-sondeo (#4, #7) · login Google GIS con nonce un solo uso + login-CSRF (#9, #11, #12).
- **`extra="forbid"`** + campos computados solo-escritura del servidor (#8) · validación Pydantic estricta (#14) · queries parametrizadas (#13).
- **Rate limiting** por endpoint (tabla §0) (#11) · hCaptcha en entradas públicas + firma de webhook (#12).
- Sesión en cookie estricta con TTL corto (#9) · tokens ≥256 bits como hash, sin contraseñas en v1 (#10) · Fernet en phone/email (#5).
- Schemas Response mínimos; costos/margen nunca en PDF ni WhatsApp (#17) · PDF solo URL firmada (#16).
- Headers de hardening + HTTPS forzado en el edge (#18, #19) · cero secrets en repo/build, DB no expuesta (#1–3) · scan de dependencias en CI (#20).
Verificación ítem por ítem: `security.md` → **matriz de trazabilidad** + **checklist de conformidad (20/20)**.
