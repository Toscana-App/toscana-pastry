# QR de entrega por pedido (link temporal con UUID)

## Objetivo

Cada pedido finalizado tiene un QR que, al escanearse, abre una pagina publica
con el estado del pedido. El link vive mientras el pedido esta en curso y muere
cuando el pedido se entrega: desde ese momento el QR ya no expone el pedido y la
pagina responde **"Su pedido ha sido entregado"**.

## Fuente de verdad

- Maquina de estados del pedido: `backend/src/domain/order_states.py` (O1, PR #85).
  Terminales: `delivered`, `cancelled`.
- Transicion unica: `backend/src/domain/use_cases/transition_order_status.py`.
- Cancelacion por comprobante rechazado: `backend/src/domain/use_cases/reject_receipt.py`.
- Concatenacion publica de documentos: `backend/src/api/v1/pdf/router.py`
  (precedente de link publico con rate limit; distinto: aquel es HMAC sin estado,
  este necesita revocacion por evento).
- Base de la pagina publica en el frontend: `frontend/src/app/page.tsx` (ruta
  fuera de `PROTECTED_PREFIXES` de `frontend/src/proxy.ts`).

## Specs

- **S1 — Identidad del link.** El link publico se identifica con un `uuid4`
  (`domain/delivery.py::new_delivery_token`). Un pedido tiene **un solo** link
  activo (indice unico parcial `WHERE revoked_at IS NULL`). Pedir el link dos
  veces devuelve el mismo token: el QR ya impreso no se invalida.
- **S2 — Emision.** `GET /orders/{id}/delivery-link` (admin) materializa el link
  la primera vez y lo devuelve. La emision es idempotente y no toca el pedido.
  Un pedido en estado terminal no emite: **409 `order_not_deliverable`**.
- **S3 — QR.** `GET /orders/{id}/delivery-qr.svg` (admin) devuelve el SVG del QR
  de la URL publica. Generado con `segno` (sin estado, sin storage): el mismo
  token produce la misma imagen. Parametros: `error="q"`, `micro=False`,
  `border=4` (zona de silencio ISO), `scale=8`, `dark` = tinta del design system,
  `light` blanco.
- **S4 — Resolucion publica.** `GET /public/orders/{token}` (sin auth) devuelve
  `{state, order_code, status, status_label, message}`. **El estado se deriva del
  estado del pedido**, no de la fila del link: un pedido terminal nunca expone
  datos aunque la revocacion no se haya materializado. Token inexistente o con
  forma invalida → **404** con mensaje generico.
- **S5 — Muerte del link.** Toda transicion a `delivered` o `cancelled` revoca el
  link activo dentro de la misma transaccion (`revoked_reason` = `delivered` |
  `cancelled`, `revoked_at` seteado). Cubre los dos caminos que llegan a un
  terminal: `TransitionOrderStatus` (tomado por `patch_order_status`, `cancel`,
  `mark_delivered`) y `RejectReceipt`.
- **S6 — Estado terminal visible.** Despues de la entrega la pagina muestra
  "Su pedido ha sido entregado" con el codigo del pedido y nada mas. Pedido
  cancelado: "Su pedido fue cancelado". `EXPIRED` (link revocado con pedido no
  terminal, anomalia) no expone codigo.
- **S7 — Pagina publica.** `frontend/src/app/entrega/[token]` (fuera de los
  prefijos protegidos): sin sesion, sin datos personales, `noindex`, sin recursos
  externos.
- **S8 — Panel admin.** El detalle del pedido muestra la seccion "QR de entrega"
  con la imagen, la URL y el boton de descarga; si el pedido es terminal el
  estado del pedido ya lo dice y la seccion no se ofrece.
- **S9 — Fuera de scope.** Purga fisica de links revocados con antiguedad > N
  dias (tarea programada propia), marcado de entregado escaneando el QR desde el
  celular del admin (hoy la entrega se marca en el panel), y TTL absoluto del
  link. Documentados como deuda con trigger, no implementados.

## Seguridad (revision del flujo)

- **R1 — Entropia.** Token `uuid4`: 122 bits aleatorios, no enumerable. Se
  descarta `uuid1` (filtraria MAC/tiempo) y cualquier secuencia por pedido.
- **R2 — Token en claro: decision explicita.** Se evaluo guardar solo el hash
  (SHA-256) y se descarto: el admin necesita volver a mostrar el mismo QR ya
  impreso, y un hash no permite reconstruir la URL. El radio de exposicion de un
  dump es acotado: el link solo revela codigo de pedido + estado, sin PII ni
  montos, y muere al entregar. Contramedidas compensatorias: indice unico,
  revocacion transaccional, rate limit, respuesta sin cache.
- **R3 — Sin PII.** La respuesta publica no incluye nombre, telefono, direccion,
  email, items ni importes. Solo codigo, estado y etiqueta.
- **R4 — Anti-enumeracion.** Token con forma invalida o inexistente → 404 con el
  mismo mensaje (`Link inválido o expirado`). No se distingue "nunca existio" de
  "fue revocado".
- **R5 — Rate limit.** `SlidingWindowRateLimiter` 60/min por IP en la ruta
  publica (mismo patron que `/pdf/{token}`). Es por proceso: en multi-worker el
  limite efectivo se multiplica (documentado, no bloqueante para single-tenant).
- **R6 — No cache.** La respuesta publica viaja con `Cache-Control: no-store`,
  `X-Robots-Tag: noindex` y `Referrer-Policy: no-referrer`: el token va en la URL
  y no debe quedar en caches intermedias ni filtrarse por el header `Referer`.
- **R7 — SVG seguro.** El contenido del QR lo construye el servidor desde
  configuracion (`PUBLIC_APP_URL`) + token; no hay input del usuario en el SVG.
  Se sirve `image/svg+xml` con `X-Content-Type-Options: nosniff` y
  `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'`.
- **R8 — Autorizacion.** Los endpoints de emision y QR son `require_admin`: el
  link es material de mostrador. La ruta publica no lee cookies ni sesion.
- **R9 — Forma del token validada antes de la DB.** `normalize_token` exige UUID
  v4 valido: basura, `%00`, wildcards o strings largos mueren en el borde (404)
  sin consulta.
- **R10 — HTTPS.** La URL del QR se arma con `PUBLIC_APP_URL`; en produccion debe
  ser `https`. Un link `http` filtraria el token en texto plano.
- **R11 — Sin RLS.** La tabla nueva no lleva policies de `0018`: no guarda PII y
  su lectura publica ocurre sin contexto de usuario (bajo `toscana_app` una policy
  la haria invisible y romperia el escaneo). El aislamiento es por token, no por
  tenant.
- **R12 — Borrado del pedido.** FK `ON DELETE CASCADE`: sin pedido no hay link,
  el escaneo posterior da 404.

## Casos borde

- **B1** Pedido entregado, se escanea el QR → pagina "Su pedido ha sido entregado".
- **B2** Pedido cancelado, se escanea → "Su pedido fue cancelado" (no expone datos).
- **B3** Link revocado fuera de orden (pedido sigue activo) → `EXPIRED`, sin codigo.
- **B4** Se pide el link dos veces → mismo token (el QR impreso sigue valido).
- **B5** Dos requests concurrentes sin link → el indice unico parcial decide; el
  perdedor relee y devuelve el token ganador (nunca dos links activos).
- **B6** Pedido terminal sin link emitido → 409; no se crea un link muerto.
- **B7** Token de otro pedido (UUID editado a mano) → 404; no hay salto entre pedidos.
- **B8** Token valido pero pedido borrado → 404 (cascade).
- **B9** Entrega y escaneo simultaneos → la revocacion es transaccional: la
  lectura ve el estado previo o el terminal, nunca datos despues de la entrega.
- **B10** Pedido terminal con link que quedo activo (revocacion no materializada,
  p. ej. dato previo a esta feature) → la pagina igual muestra el mensaje terminal
  porque el estado se deriva del pedido (S4).

## Decisiones (ADR)

- **ADR-1 — Estado con revocacion en base, no token firmado.** El link del PDF es
  HMAC sin estado; aca el evento de negocio (entrega) tiene que matar el link
  antes de cualquier TTL, y la revocacion es una fila. Se descarta firmar un JWT
  con `exp` porque "entregado" no es un instante futuro conocido al emitir.
- **ADR-2 — Emision perezosa e idempotente, no al crear el pedido.** Se evita
  tocar los tres caminos de alta (portal, admin, presupuesto→pedido) y la
  migracion de pedidos historicos. El link se materializa la primera vez que se
  pide; el comportamiento observable es el mismo (todo pedido finalizado puede
  mostrar su QR).
- **ADR-3 — Estado derivado del pedido, revocacion como materializacion.** La
  verdad del link es el estado del pedido; `revoked_at` es el efecto persistido
  del evento. Asi una revocacion perdida no se convierte en fuga de datos.
- **ADR-4 — Token en claro (R2).** Recoverabilidad del QR impreso > hash del
  token, con radio de exposicion acotado y sin PII.
- **ADR-5 — QR en SVG generado al vuelo.** Sin storage ni cache de binarios:
  segno es puro Python y determinista; el SVG escala para impresion.

## Casos de prueba (autoritativos, integracion)

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| Q1 | Pedido `confirmed` | admin GET `/orders/{id}/delivery-link` | 200; `url` con `uuid4`; `state=active` |
| Q2 | Pedido con link emitido | admin GET otra vez | 200; mismo `token` |
| Q3 | Pedido `confirmed` | GET `/orders/{id}/delivery-qr.svg` | 200; `image/svg+xml`; contiene `<svg` |
| Q4 | Pedido `delivered` | GET `/orders/{id}/delivery-link` | 409 `order_not_deliverable` |
| Q5 | Pedido `new` con link | admin `PATCH /orders/{id}/status` → delivered | 200; link con `revoked_at` y `revoked_reason=delivered` |
| Q6 | Pedido `confirmed` con link | `RejectReceipt` | link revocado con `revoked_reason=cancelled` |
| Q7 | Pedido con link activo | GET `/public/orders/{token}` | 200; `state=active`; codigo + estado; sin PII |
| Q8 | Pedido entregado | GET `/public/orders/{token}` | 200; `state=delivered`; `message="Su pedido ha sido entregado"` |
| Q9 | Pedido cancelado | GET `/public/orders/{token}` | 200; `state=cancelled` |
| Q10 | Token inexistente / no-UUID | GET `/public/orders/{token}` | 404 |
| Q11 | Pedido entregado con link activo (hook perdido) | GET `/public/orders/{token}` | 200; `state=delivered`; sin datos de pedido en curso |
| Q12 | Cliente (no admin) | GET `/orders/{id}/delivery-link` | 403 |
| Q13 | Pedido de otro tenant/inexistente | GET `/orders/{id}/delivery-link` | 404 |
| Q14 | Dos emisiones concurrentes | GET simultaneo | un solo link activo; mismo token |

## Tasks

- **T1** — ODD (este archivo). ✅
- **T2** — Dominio: `domain/delivery.py` (token, estados, derivacion, errores) + tests. ✅ (`tests/unit/domain/test_delivery.py`, 24)
- **T3** — Persistencia: ORM + migracion `0022` + `SQLDeliveryLinkRepository` + indice unico parcial + tests de migracion. ✅
- **T4** — Use cases: `IssueDeliveryLink`, `ResolveDeliveryLink`; revocacion en `TransitionOrderStatus` y `RejectReceipt` + tests. ✅ (11 de use cases + revocacion asertada en los tests de transicion y rechazo)
- **T5** — API: router de entrega (link, svg, publico), rate limit, headers de seguridad, `segno` en dependencias + tests de integracion Q1-Q14. ✅ (`tests/integration/api/test_order_delivery_qr.py`, 15)
- **T6** — Frontend: pagina publica `/entrega/[token]` + seccion QR en el detalle de pedido + tests. ✅
- **T7** — Gate: suite backend (archivos auto-contenidos), `tsc`/`vitest`/`build`; PR apilado sobre `feat/transfer-receipts`. ✅ con una salvedad documentada en L7.

## Reglas

- Cero comentarios y cero docstrings en el codigo nuevo.
- Cero logica de negocio en SQL: el indice unico es invariante de persistencia;
  que estados son terminales se decide en `domain/delivery.py`.
- Un archivo se toca una sola vez por entrega; commit por tarea.
- Degradacion explicita: si `segno` no esta instalado, el endpoint responde 503
  `qr_unavailable` en vez de 500 (dependencia declarada, no opcional en runtime).

## Log

- **L1** (T1): diseno. 14 casos; 5 decisiones ADR; 12 items de seguridad; 10
  bordes. Hallazgo clave: "eliminar el link" y "mostrar 'entregado'" son
  incompatibles si se borra la fila — se resuelve con estado derivado del pedido
  (ADR-3) y purga diferida (S9).
- **L2** (T2): `domain/delivery.py` sin dependencias nuevas; el estado publico se
  deriva del pedido (`revocation_reason`) y el link revocado sin pedido terminal
  cae en `expired` sin exponer codigo.
- **L3** (T3): tabla `order_delivery_links` con `ON DELETE CASCADE` e indice unico
  parcial (`revoked_at IS NULL`), replicado en el ORM con `postgresql_where` +
  `sqlite_where` para que la suite in-memory cree el mismo invariante.
- **L4** (T4): la revocacion entra en `TransitionOrderStatus` y `RejectReceipt`
  como colaborador inyectado (no al store), asi la decision sigue en el dominio y
  participa de la transaccion del pedido. Cambio de contrato de ambos use cases:
  los tests existentes se actualizaron con un `FakeDeliveryLinks` y ahora asertan
  la revocacion en `delivered`/`cancelled`.
- **L5** (T5): `segno` 1.6.6 declarado y lockeado; QR generado al vuelo (sin
  storage) con `border=4` y `error=q`. La ruta publica valida la forma del token
  antes de tocar la DB y responde 404 generico. `create` commitea su unidad de
  trabajo; `revoke_active` participa de la transaccion del pedido (asimetria
  deliberada: emision es operacion autonoma, revocacion es efecto de otra).
- **L6** (T6): la pagina publica es server component que resuelve `params` y
  delega en un client component (`modules/delivery/delivery_status_view.tsx`):
  con `useParams` en un page cliente, Next 16 bloqueaba el prerender. El h1 es el
  `message` del backend, asi el texto "Su pedido ha sido entregado" tiene una
  sola fuente. En el panel, la seccion es un boton que abre el dialogo (no
  fetchea al montar): el detalle de pedido no gana una request por visita ni se
  rompen sus tests. El detalle admin no expone `code`, asi que el QR no se
  etiqueta con el codigo del pedido.
- **L7** (T7): gates ejecutados — backend: 53 tests de dominio + 15 de API
  (sqlite in-memory, `--noconftest`) verdes; frontend: `tsc` limpio, 622/622
  `vitest`, `next build` compila y genera las 40 rutas (la ruta nueva queda como
  parcial, igual que el resto de las dinamicas) con `export const instant = false`
  para declararla bloqueante por diseno. El build termina en
  `SecurityFatalError` por el advisory de la version de Next instalada (16.4.1):
  es un gate de entorno sobre `package.json`, previo a esta rama y comun a `main`;
  CI lo confirma o lo reproduce sin cambios de codigo.
- **L8** (T5, pendiente declarado): Q6 (rechazo de comprobante) se verifica en
  `tests/unit/domain/test_reject_receipt.py` y no en la suite de integracion
  porque ese camino exige archivo de comprobante en disco; el caso e2e equivalente
  queda para el harness `backend/e2e/` (necesita Postgres, no disponible en el
  LXC por decision de Gaspar).
- **L9** (T6, correccion por CI): el primer intento levantaba el fetch desde un
  `useCallback` que hacia `setLoading(true)` en la primera linea, y ESLint lo
  marco como `react-hooks/set-state-in-effect` (setState sincronico dentro del
  efecto = renders en cascada). Se reescribio como IIFE async: el primer setState
  ocurre despues del `await`, y el desmontaje aborta la request via
  `AbortController` (antes una respuesta tardia podia pintar sobre otro token).
  El reintento ahora es un contador de intentos en las deps del efecto, no una
  llamada directa.
- **L10** (T7, hallazgo ajeno que bloqueaba el CI): dos tests de stats de WhatsApp
  fallaban en `main` desde el 2026-11-25 por un fixture con ancla fija
  (`NOW = 2026-10-26`) contra una ventana relativa de 30 dias: al vencer el ancla,
  los fixtures caen fuera de la ventana y `stats()["total"]` da 0. No lo causaba
  esta feature ni el chain (main paso el 23/11 y no volvio a correr). Se cambia el
  ancla a relativa en los dos archivos; sin eso el PR no puede ponerse verde.
