# P1 — Auth / Crear cuenta
Módulo: `web/modules/auth` · Rutas: `/auth` (login), `/auth/verify` (magic link), `/onboarding/tenant` (configurar negocio) · Fase: **0**

## Contexto
La usuaria paga fuera de la app y recibe un email con un link de creación de cuenta (flujo verificado en el FAQ del producto original). Primera sesión = alta de cuenta + configuración mínima del negocio.

## User story
> Como **repostera que acaba de comprar**, quiero **crear mi cuenta con el link del email sin recordar contraseñas**, para **empezar a configurar mi negocio en menos de 5 minutos**.

**Criterios de aceptación**
- [ ] Con el link del email: creo cuenta sin contraseña (magic link de un solo uso).
- [ ] Sin link: puedo iniciar sesión escribiendo mi email (me llega un nuevo magic link).
- [ ] Si el tenant no existe: me guío por onboarding de 3 campos (nombre del negocio, moneda, ciudad) y sigo a la home vacía.
- [ ] Si ya tengo sesión: el magic link me lleva directo a la home (no duplica cuenta).
- [ ] Al cerrar sesión, la sesión queda invalidada en todos los dispositivos.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Crear cuenta por compra | Compradora | Click link → canjea token → cuenta creada → onboarding tenant |
| UC-02 Ingresar por email | Usuaria | Escribe email → recibe link (15 min) → click → sesión |
| UC-03 Configurar negocio | Usuaria | Onboarding: nombre, moneda, ciudad → tenant creado |
| UC-04 Reenviar link | Usuaria | "No te llegó el link" → reenvía (máx. 3/hora) |
| UC-05 Cerrar sesión | Usuaria | Avatar → cerrar sesión → invalida tokens |
| UC-06 Entrar con Google | Usuaria existente | Botón Google → consentimiento → sesión (sin email ni contraseña) |
| UC-07 Enlazar Google | Usuaria existente | Primer login con Google → email coincide con su cuenta → confirma con magic link → enlazado |

## Requerimientos funcionales
- **RF-P1-01**: Magic link: token de un solo uso, TTL 15 min, enviado por email transaccional. (UC-01/02)
- **RF-P1-02**: Token de compra (del link de entrega) canjeable una sola vez → crea user+tenant. (UC-01)
- **RF-P1-03**: Sesión: JWT en cookie `httpOnly; Secure; SameSite=Strict`, refresh automático, logout invalida. (UC-05)
- **RF-P1-04**: Un email = una cuenta (validación de email real: doble opt-in opcional). (UC-01)
- **RF-P1-05**: Onboarding de tenant: nombre (requerido), moneda (default ARS), ciudad. (UC-03)
- **RF-P1-06**: Rate limit: 3 magic links/hora por email, 10 intentos de verify/ip. (UC-04)
- **RF-P1-07**: Reescritura de rutas: si autenticada, `/auth` → `/`.
- **RF-P1-08**: Login Google vía flujo GIS **ID token** (no authorization-code): solo resuelve "¿quién es?". Sin redirect URI y **sin client secret en la app** (UC-06).
- **RF-P1-09**: Identidad en `sub` (guardado como `google_id`), nunca en email. Nonce emitido por el servidor por cada render, de un solo uso, atado a cookie pre-auth (anti-replay) (UC-06).
- **RF-P1-10**: Exigir `email_verified=true`. **Enlace solo tras re-autenticar la cuenta local** (nuevo magic link a ese email); nunca auto-link por `email_verified` solo (UC-07).
- **RF-P1-11**: Google **no crea cuentas** (el registro es gated por compra). Sin cuenta → estado "revisá tu email de compra", nunca alta automática (UC-06).
- **RF-P1-12**: `GOOGLE_CLIENT_ID` público (env, inyectado server-side, única fuente de verdad). Si está vacío → botón oculto + respuesta "no configurado" (UC-06).

## Requerimientos no funcionales
- **RNF-P1-01**: El email llega en < 2 min (proveedor transaccional con SLA).
- **RNF-P1-02**: Tiempo total click→dentro de la app < 30 s (sin pasos intermedios).
- **RNF-P1-03**: Cero datos de sesión en localStorage (solo cookies httpOnly).
- **RNF-P1-04**: WCAG AA: labels visibles, focus visible, contraste del link en email verificable (email plano, sin layout HTML pesado).
- **RNF-P1-05**: Mobile-first: el 100% del flujo funciona a 375px con targets ≥ 44px.
- **RNF-P1-06**: Login-CSRF en el endpoint Google: solo same-origin (`Sec-Fetch-Site`), fail-closed, decidido **antes** de verificar el token.
- **RNF-P1-07**: El ID token de Google se verifica una vez (JWKS, `aud`, `iss`, `exp`) y nunca se almacena ni se loguea.
- **RNF-P1-08**: CSP permite `accounts.google.com` (script-src, connect-src, frame-src); el script GSI se carga desde Google (nunca vendored).

## Tareas
- [ ] API: `POST /auth/magic-link` (email) + `POST /auth/verify` (token)
- [ ] API: `POST /auth/purchase/redeem` (token de compra, idempotente)
- [ ] API: `POST /auth/logout`, `GET /me`
- [ ] API: `GET /auth/google/nonce` + `POST /auth/google/signin` (GIS ID token)
- [ ] Data: `users.google_id` (única) + tabla `google_nonces` (nonce, expires_at, consumed_at)
- [ ] Data: `magic_tokens.purpose += 'google_link'` (bind account + google_id)
- [ ] Web: botón GSI con nonce del servidor, retry de render (20×150 ms) y `disableAutoSelect()` en logout
- [ ] Web: estado de enlace ("confirmá tu cuenta") → magic link → enlace completado
- [ ] Tests: verificación de ID token (aud/exp/iss/nonce), replay = 401, link sin re-auth = rechaza, sin cuenta = estado no_account
- [ ] API: `POST /tenant` (onboarding) + `PUT /tenant`
- [ ] Domain: entidad `user`, `tenant`; regla de canje único de token de compra
- [ ] Data: tabla `magic_tokens` (token_hash, email, purpose, expires_at, consumed_at), índice por email
- [ ] Web: formulario de email (zod: formato), botón con estado de carga
- [ ] Web: página de verificación con estados (enviado / esperando / link inválido / expirado)
- [ ] Web: wizard de onboarding de tenant (3 campos, validación inline)
- [ ] Web: guard de rutas (no autenticada → `/auth`; autenticada → `/`)
- [ ] Email: plantillas (nuevo link, link de compra) — texto plano + HTML simple
- [ ] Tests: pytest del canje de token (doble canje = 409), rate limits; Vitest del flujo de verificación
- [ ] GA4: evento `signup_completed`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Field.Root` (email), `Button` primary (gradient blue-400→500, única acción: "Entrar"), `Text` secundario, `Tabs` no aplica.
- Botón Google (GSI, secondary, bajo el CTA primary): se renderiza con nonce del servidor + retry; si `GOOGLE_CLIENT_ID` vacío no se renderiza (degradación honesta).
- Pantalla de login = una sola tarjeta centrada: logo, "Tu negocio, más simple.", input + CTA "Entrar" + botón Google (secondary). El primary sigue siendo el CTA único de acción; Google es la vía alternativa de identidad.
- Estados de error: `Alert.Root` danger inline bajo el input, `aria-describedby`.
- Tokens: fondo `paper-50`, surface para tarjeta (outline 1px, radius 6px, sin shadow), texto `fg` / `fg-muted` (corregido a `#6F6F6F`).
