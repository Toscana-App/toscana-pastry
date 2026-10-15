# Seguridad — 20 ítems obligatorios (trazabilidad completa)

> Documento de referencia de seguridad del proyecto. Cada ítem: **control → implementación (stack concreto) → dónde se aplica → verificación (test/auditoría)**.
> Stack: Next.js 15 (App Router) + FastAPI + Postgres + Caddy + Docker.
> Aplicación por fase: **F0** = base (antes de cualquier endpoint de negocio) · **F1–F3** = por módulo · **F4** = auditoría final.
> Redacción: ítems y numeración según checklist de Gaspar. Este archivo + los ajustes en `master_plan.md` (§1.4) y `api_endpoints.md` (§0) forman el conjunto conforme. **Ningún ítem queda sin control.**

---

## 1. Ocultar API keys
- **Control**: ningún secreto (email transaccional, WhatsApp Cloud API, SMTP, DB, hCaptcha `secretkey`) vive en el frontend ni en el repo.
- **Implementación**:
  - Secrets solo en variables de entorno del runtime del backend (inyectadas en deploy; `env_file` fuera del repo).
  - **Cero `NEXT_PUBLIC_*` en v1** (whitelist vacía). hCaptcha: `sitekey` es pública por diseño; `secretkey` solo server-side.
  - Login Google: `GOOGLE_CLIENT_ID` es **pública por diseño** (inyectada server-side, única fuente de verdad); el `client_secret` **no se usa en el flujo GIS y no existe en la app**.
  - CI: escaneo del build de producción (`.next/static`, bundle) con `gitleaks` + patrón de claves (`sk-`, `AIza`, `xoxb`, `Bearer`, connection strings).
- **Dónde**: `infra/` (compose), `.github/workflows/ci.yml` (step `secret-scan-build`) · F0.
- **Verificación**: el step de CI **falla** si aparece algún patrón de secreto en el bundle; PR bloqueado.

## 2. Eliminar secretos de Git
- **Control**: cero secretos en el working tree y en el historial.
- **Implementación**:
  - `.gitignore`: `.env*`, `*.pem`, `*.key`, `secrets/`, `*.p12`.
  - `gitleaks` en **pre-commit** y en CI (scan completo del historial en push/PR).
  - Compose y configs con interpolación de variables, sin valores hardcoded.
  - Runbook de incidente: rotación inmediata del secreto → `git filter-repo` → force push → auditoría de acceso.
- **Dónde**: root del repo, CI step `secret-scan-repo` · F0.
- **Verificación**: `gitleaks detect` verde en cada PR; check en CI sobre la rama principal.

## 3. Key pública para DB
- **Control**: credenciales de Postgres **no públicas**, privilegio mínimo, sin superficie de red expuesta.
- **Implementación**:
  - Servicio `db` en red interna de Docker (`internal: true`), **sin puerto publicado** al host.
  - Usuario dedicado `dh_app` (no superuser, sin DDL en producción); opcional `dh_migrate` solo para Alembic.
  - Connection string únicamente en el entorno de runtime de la API.
- **Dónde**: `infra/docker-compose.yml` · F0.
- **Verificación**: en staging, `ss -lntp` no muestra 5432 fuera de la red interna; check de CI: el servicio `db` no tiene sección `ports`.

## 4. Row-Level Security
- **Control**: aislamiento de tenants **en la base de datos** (defensa en profundidad, no solo en repositorio).
- **Implementación**:
  - `ENABLE ROW LEVEL SECURITY` (+ `FORCE`) en toda tabla con `tenant_id`.
  - Política: `USING (tenant_id = current_setting('app.tenant_id')::uuid)`.
  - Dependencia FastAPI: al iniciar cada transacción `SELECT set_config('app.tenant_id', $1, true)` (local por transacción).
  - Tablas: `ingredients`, `products`, `recipe_items` (vía `product_id` + FK), `customers`, `orders`, `order_items`, `budgets`, `budget_items`, `stock_movements`, `magic_tokens` (scope por email).
  - Migración Alembic: RLS se habilita **antes** de insertar datos (o en la misma transacción con política por defecto que rechaza).
- **Dónde**: `api/data/` (migraciones + session factory) · F0 (primeras tablas) → F3 (todas).
- **Verificación**: pytest cross-tenant por tabla: sesión del tenant A hace query directa (sin repositorio) con un id del tenant B → **0 filas**.

## 5. Encriptar datos sensibles
- **Control**: en tránsito (TLS), en reposo (volumen), y a nivel de campo.
- **Implementación**:
  - Tránsito: TLS en el edge (ítem 19); Postgres solo en red interna (ítem 3).
  - **Campo**: `customer.phone` y `customer.email` con Fernet (`cryptography`); clave en env de secreto; **rotación con doble clave** (key vieja para decrypt, nueva para encrypt).
  - Tokens magic link y de compra: se almacena **solo el hash SHA-256**, nunca el plaintext (ver ítem 10).
  - ID tokens de Google: se verifican **una vez** contra JWKS de Google y **nunca se almacenan ni se loguean**; la tabla `google_nonces` guarda solo el nonce (no el token).
  - Sesión: cookie httpOnly (ítem 9); cero datos de sesión en `localStorage`.
- **Dónde**: `api/domain/crypto.py` · F2 (customers) · F0 (tokens de auth).
- **Verificación**: pytest: `SELECT` directo muestra phone/email cifrados (≠ plaintext); round-trip decrypt correcto; tabla `magic_tokens` sin tokens legibles.

## 6. Forzar la autenticación
- **Control**: autenticado por defecto; lo público es la excepción explícita.
- **Implementación**:
  - API: dependencia `get_current_user` como default del router `/api/v1`. **Allow-list público (9)**: `GET /health`, `GET /ready`, `POST /auth/magic-link`, `POST /auth/verify`, `POST /auth/purchase/redeem`, `GET /auth/google/nonce`, `POST /auth/google/signin` (login-CSRF + nonce), `POST /webhooks/whatsapp` (valida firma), `GET /webhooks/whatsapp/verify`.
  - Web: `middleware.ts` de Next.js redirige a `/auth` sin sesión; guard de rutas por pantalla.
  - Respuesta 401 genérica (sin revelar por qué falló).
- **Dónde**: `api/presentation/auth.py`, `web/middleware.ts` · F0.
- **Verificación**: pytest iterativo: cada ruta del OpenAPI no incluida en el allow-list, sin cookie → **401**.

## 7. Restringir el acceso a registros (IDOR)
- **Control**: todo objeto pertenece al tenant de la sesión; imposible leer/modificar registros de otro tenant.
- **Implementación**:
  - Repositorios filtran por `tenant_id` + RLS (ítem 4).
  - Objeto ajeno o inexistente → **404** (nunca 403, no se revela existencia).
  - Los responses no exponen `tenant_id` ni ids internos en links públicos.
- **Dónde**: todos los routers · F0 (convención) → F3 (recursos completos).
- **Verificación**: matriz IDOR en pytest por recurso (ingredient, product, customer, order, budget): usuario A + id del tenant B → 404; usuario A + id propio → 200.

## 8. Bloquear manipulación de campos
- **Control**: el cliente no puede inyectar campos que no le corresponden ni valores computados.
- **Implementación**:
  - Pydantic v2: esquemas **Create / Update / Response** separados; `model_config = ConfigDict(extra="forbid")`.
  - **Solo el servidor escribe**: `id`, `tenant_id`, `created_at`, `seq`, `price`, `costs`, `total`, `breakdown`, `final_price` (motor de precio), `stock_qty` (solo vía `POST /ingredients/{id}/stock`), `status` (solo vía endpoints de transición con máquina de estados).
  - Secuencias (`#000NN`) vía Postgres (row lock por tenant).
- **Dónde**: `api/presentation/schemas/` · F0 (convención) → F3.
- **Verificación**: pytest: payload con campos extra → **422**; pedido enviado con `total` propio del cliente → el precio final siempre sale del motor (assert numérico contra la fórmula).

## 9. Proteger Session cookies
- **Control**: sesión en cookie con flags estrictos y vida corta.
- **Implementación**:
  - `Set-Cookie: access=…; HttpOnly; Secure; SameSite=Strict; Path=/` con TTL corto (15–30 min) + rotación en cada `verify`. Strict es compatible con ambos flujos (magic link y GIS son navegaciones top-level).
  - Logout: invalidación server-side (blocklist con TTL = expiración del token).
  - Cero sesión en `localStorage` (RNF-P1-03, ya en spec de P1).
- **Dónde**: `api/presentation/auth.py` · F0.
- **Verificación**: pytest + curl: la cookie tiene `HttpOnly`, `Secure`, `SameSite=Strict`; E2E: `document.cookie` no la expone.

## 10. Hashear contraseñas
- **Control**: nada en plaintext; regla explícita para el futuro.
- **Implementación**:
  - **Decisión v1: no hay contraseñas** (auth por magic link) → no existe password de usuario que almacenar. Queda documentada como premisa.
  - Tokens magic link / compra: generación con `secrets.token_urlsafe(32)` (≥256 bits) y almacenamiento **solo como hash SHA-256** (ítem 5).
  - Regla de futuro: si se introduce auth por contraseña → **argon2id** (`argon2-cffi`), salt por usuario, comparación en tiempo constante. Prohibido MD5/SHA-1/SHA-256-sin-salt para passwords.
- **Dónde**: `api/presentation/auth.py` + `api/domain/tokens.py` · F0.
- **Verificación**: pytest: `magic_tokens` sin plaintext; entropía del token ≥256 bits; (test condicional) si existe campo password → verificación de parámetros argon2id.

## 11. Rate limiting
- **Control**: throttling por endpoint, por email/usuario/IP.
- **Implementación** (`slowapi`; tabla de límites en `api_endpoints.md` §0):
  | Endpoint | Límite |
  |---|---|
  | `POST /auth/magic-link` | 3/h por email · 10/h por IP |
  | `POST /auth/verify` | 10/h por IP |
  | `GET /auth/google/nonce` | 60/h por IP |
  | `POST /auth/google/signin` | 10/h por IP |
  | `POST /auth/purchase/redeem` | 5/h por IP |
  | `POST /contact` (si existe) | 5/h por IP |
  | `POST /ingredients/import` | 10/h por usuario |
  | Escrituras (POST/PATCH/DELETE) | 60/min por usuario |
  | Global | 300/min por IP |
  - Exceso → **429** + `Retry-After` + headers `X-RateLimit-*`.
- **Dónde**: `api/presentation/rate_limit.py` (dependency por endpoint) · F0 (auth) → F4 (todas las escrituras).
- **Verificación**: pytest (TestClient): agotar el límite → 429 con `Retry-After`; test manual en staging.

## 12. Protección contra bots
- **Control**: verificación humana en entradas públicas y autenticación de webhooks.
- **Implementación**:
  - **hCaptcha** con validación server-side (`secretkey`): `POST /auth/magic-link` (y `POST /contact` si existe).
  - **Honeypot** (campo oculto) en formularios públicos: si se completa → se descarta silenciosamente (202, sin enviar email).
  - **Login Google (GIS)**: nonce server-issued de un solo uso atado a cookie pre-auth (anti-replay) + **login-CSRF**: solo same-origin (`Sec-Fetch-Site`), fail-closed, decidido antes de verificar el token (skill `google-signin`).
  - `POST /webhooks/whatsapp`: **verificación de firma** de la Cloud API + dedupe por id de evento (anti-replay).
  - Producción: `/docs` y `/openapi.json` **desactivados o detrás de auth**; `robots.txt` sin indexar rutas sensibles.
- **Dónde**: F0 (auth) · F3 (webhook) · F4 (docs).
- **Verificación**: pytest: magic-link sin captcha válido → 403; webhook con firma inválida → 401; honeypot completado → no se dispara envío de email.

## 13. Parametrizar queries
- **Control**: ninguna SQL con concatenación de strings.
- **Implementación**:
  - SQLAlchemy Core/ORM **exclusivamente con bind parameters**.
  - Filtros dinásticos (`q`, `status`, fechas) construidos con `where()` tipado; búsqueda con `pg_trgm` (índice), no string-mangling.
  - `set_config` de RLS (ítem 4) con parámetro, nunca interpolado.
  - Prohibido `text()` con f-strings (excepción: migraciones, y solo parametrizadas).
- **Dónde**: `api/data/` · F0 → F3.
- **Verificación**: regla de ruff/grep en CI que bloquea `text(f"…")`/f-strings en `execute(`; mypy strict.

## 14. Validar inputs
- **Control**: validación tipada y acotada en toda entrada.
- **Implementación** (Pydantic v2):
  - Allow-lists: `unit ∈ {kg,g,L,ml,unidad}`, `status ∈ enum`, `reason ∈ {compra,merma,ajuste}`, `calc_mode ∈ {cost_plus,manual}`.
  - Longitudes máximas: `name ≤ 120`, `notes ≤ 2000`, `description ≤ 5000`.
  - Montos `Decimal`: `≥ 0`, máximo 9 dígitos + 2 decimales; cantidades enteras `≥ 1`; fechas válidas; email con formato (el flujo de magic link lo verifica con el uso).
  - `extra="forbid"` en todos los esquemas (ítem 8).
- **Dónde**: `api/presentation/schemas/` · F0 (primeros formularios) → F3.
- **Verificación**: pytest por schema: payload inválido → 422 con campo; bordes (longitud máxima, monto negativo, cantidad 0).

## 15. Sanitizar contenido
- **Control**: todo contenido generado por el usuario se trata como **texto inerte**, nunca como HTML/código.
- **Implementación**:
  - Web: escaping por defecto de React; **prohibido** `dangerouslySetInnerHTML` con datos de usuario.
  - PDF: inserción de texto nativa (ReportLab); si se usa WeasyPrint (HTML), el contenido de usuario pasa por `bleach` (allow-list vacía de tags).
  - WhatsApp: mensaje plain-text; el template escapea/cita los campos de usuario.
  - Prohibido `eval` / `new Function` / ejecución dinámica de contenido.
- **Dónde**: `web/modules/*`, `api/presentation/pdf.py` · F2 (pedidos) → F3 (PDF/WhatsApp).
- **Verificación**: test XSS: `name`/`notes` con `<img src=x onerror=alert(1)>` → renderiza como texto literal en UI, PDF y mensaje de WhatsApp (sin tag ejecutable).

## 16. Restringir archivos
- **Control**: acceso controlado a archivos; sin subidas arbitrarias.
- **Implementación**:
  - **v1: sin uploads de usuario** (decisión). Si se agregan en el futuro: allow-list de MIME (webp/png/pdf), tamaño ≤ 5 MB, filename hasheado, storage fuera del webroot, sin ejecución.
  - PDF: solo vía `GET /budgets/{id}/pdf` **autenticado** o mediante URL firmada (expiración ≤ 1 h, single-use). Sin directorio estático de PDFs alcanzable por path.
  - Edge: `X-Content-Type-Options: nosniff` (ítem 18); sin listing de directorios; `next.config` sin `filesystem` expuesto.
- **Dónde**: F3 (PDF) · F4 (edge).
- **Verificación**: pytest: path directo de PDF sin sesión ni URL válida → 403/404; URL firmada expirada → 410; (test condicional) upload con MIME no permitido → 415.

## 17. Devolver datos necesarios
- **Control**: exposición mínima; los datos internos nunca salen hacia el cliente final.
- **Implementación**:
  - Esquemas **Response** explícitos (solo los campos que consume la UI); sin `*` ni dumps de entidad completa.
  - `costs`, `breakdown`, `total_costos`, `margin`/`ganancia`: **solo** en responses al usuario del tenant. **Nunca** en PDF, ni en el template de WhatsApp, ni en links públicos.
  - Listados siempre paginados (ítem 3 del contrato); `GET /me` sin campos innecesarios.
- **Dónde**: `api/presentation/schemas/` · F0 → F3.
- **Verificación**: pytest: el PDF y el template de WhatsApp no contienen campos de costos/margen; los responses no incluyen campos internos no declarados.

## 18. Security headers
- **Control**: hardening de headers en todas las respuestas.
- **Implementación** (Caddy en el edge — autoridad única; `next.config` como defensa en profundidad):
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `Content-Security-Policy` adaptada a Next.js (`'self'` + nonces para inline; más `https://accounts.google.com` en `script-src`, `connect-src` y `frame-src` para el botón GSI)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` (+ `frame-ancestors 'none'` en CSP)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), camera=(), microphone=()`
- **Dónde**: `infra/Caddyfile` · F0.
- **Verificación**: script en CI: `curl -sI` sobre `/` y `/api/v1/health` asertando cada header; falta de uno = CI roja.

## 19. Forzar HTTPS
- **Control**: solo TLS en producción.
- **Implementación**:
  - Caddy con TLS automático (ACME); redirect **301** http→https; HSTS (ítem 18); sin mixed content (recursos absolutos `https://` o protocol-relative).
  - Probadores internos (`/health`) accesibles solo desde la red interna de Docker.
- **Dónde**: `infra/Caddyfile` · F0.
- **Verificación**: CI: `http://…` devuelve 301 a `https://…`; header HSTS presente; grep del bundle sin URLs `http://` absolutas.

## 20. Escanear dependencias
- **Control**: vulnerabilidades conocidas bajo control continuo.
- **Implementación**:
  - CI (cada PR + schedule semanal): `pip-audit` (API) y `pnpm audit --audit-level=high` (web).
  - Dependabot: actualizaciones semanales de dependencias npm y de GitHub Actions (`dependabot.yml`).
  - Lockfiles comprometidos (`uv.lock`/`requirements.txt` + `pnpm-lock.yaml`); CI instala **desde lockfile** (reproducibilidad).
  - Política: CI **falla** con critical/high explotables; imágenes base actualizadas trimestralmente (opcional: `docker scout`).
- **Dónde**: `.github/workflows/ci.yml`, `.github/dependabot.yml` · F0 (desde el primer PR).
- **Verificación**: step de CI rojo ante CVE high; reportes de `pip-audit`/`pnpm audit` archivados como artifacts.

---

## Matriz de trazabilidad (ítem → fase → verificación)

| # | Ítem | F0 | F1 | F2 | F3 | F4 |
|---|---|---|---|---|---|---|
| 1 | Ocultar API keys | ● | | | | ● (auditoría build) |
| 2 | Eliminar secretos de Git | ● | | | | |
| 3 | Key pública para DB | ● | | | | |
| 4 | Row-Level Security | ● (RLS activada) | ● | ● | ● | ● (tests cross-tenant) |
| 5 | Encriptar datos sensibles | ● (tokens) | | ● (Fernet phone/email) | | |
| 6 | Forzar la autenticación | ● | ● | ● | ● | |
| 7 | Restringir acceso a registros | ● (convención) | ● | ● | ● | ● (matriz IDOR) |
| 8 | Bloquear manipulación de campos | ● (convención) | ● | ● | ● | |
| 9 | Proteger Session cookies | ● | | | | ● (verificación) |
| 10 | Hashear contraseñas | ● (tokens hash; decisión sin password) | | | | |
| 11 | Rate limiting | ● (auth) | | ● (import) | | ● (todas escrituras) |
| 12 | Protección contra bots | ● (hCaptcha + GIS nonce/CSRF) | | | ● (webhook firma) | ● (docs cerrados) |
| 13 | Parametrizar queries | ● | ● | ● | ● | |
| 14 | Validar inputs | ● | ● | ● | ● | |
| 15 | Sanitizar contenido | | | ● | ● (PDF/WhatsApp) | |
| 16 | Restringir archivos | | | | ● (PDF firmado) | ● (edge) |
| 17 | Devolver datos necesarios | ● (convención) | ● | ● | ● (PDF/WhatsApp) | |
| 18 | Security headers | ● | | | | ● (verificación) |
| 19 | Forzar HTTPS | ● | | | | ● (verificación) |
| 20 | Escanear dependencias | ● (desde 1er PR) | ● | ● | ● | ● (política) |

## Checklist de conformidad (20/20)

- [x] 1. Ocultar API keys — §1 (build scan en CI, cero `NEXT_PUBLIC_*`)
- [x] 2. Eliminar secretos de Git — §2 (gitleaks pre-commit + CI + runbook)
- [x] 3. Key pública para DB — §3 (red interna, usuario dedicado, sin puerto expuesto)
- [x] 4. Row-Level Security — §4 (RLS + `set_config`, tests cross-tenant)
- [x] 5. Encriptar datos sensibles — §5 (Fernet campo, tokens solo hash)
- [x] 6. Forzar la autenticación — §6 (default auth, allow-list de 9)
- [x] 7. Restringir el acceso a registros — §7 (repo + RLS, 404 anti-sondeo)
- [x] 8. Bloquear manipulación de campos — §8 (extra=forbid, campos computados server-only)
- [x] 9. Proteger Session cookies — §9 (HttpOnly/Secure/SameSite=Strict, TTL corto + rotación)
- [x] 10. Hashear contraseñas — §10 (sin passwords en v1; tokens ≥256 bits como hash; argon2id de futuro)
- [x] 11. Rate limiting — §11 (slowapi, tabla de límites, 429 + Retry-After)
- [x] 12. Protección contra bots — §12 (hCaptcha, honeypot, GIS nonce + login-CSRF, firma de webhook, docs cerrados)
- [x] 13. Parametrizar queries — §13 (SQLAlchemy bind params, regla CI)
- [x] 14. Validar inputs — §14 (Pydantic v2: allow-lists, longitudes, bordes)
- [x] 15. Sanitizar contenido — §15 (texto inerte: React/ReportLab/WhatsApp, test XSS)
- [x] 16. Restringir archivos — §16 (sin uploads v1; PDF solo URL firmada)
- [x] 17. Devolver datos necesarios — §17 (schemas Response explícitos; costos solo al tenant)
- [x] 18. Security headers — §18 (Caddy: HSTS/CSP + origins GSI/nosniff/DENY/Referrer/Permissions)
- [x] 19. Forzar HTTPS — §19 (TLS automático, 301, HSTS preload)
- [x] 20. Escanear dependencias — §20 (pip-audit + pnpm audit + Dependabot, fail on high)
