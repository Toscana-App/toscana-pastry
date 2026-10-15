# Plan maestro — Dulces Herramientas (reimplementación)

> Fase: planificación. Este documento define arquitectura, fases iterativas y checklist técnico.
> Stack: **Next.js (frontend) + FastAPI (backend)**. Cada pantalla P1–P10 es un módulo independiente.
> Sistema de diseño: Chakra UI v3 configurado sobre los tokens de `~/.hermes/DESIGN.md`.

---

## 1. Arquitectura

### 1.1 Monorepo
```
dulcesherramientas/
├── web/                  # Next.js 15 (App Router) + Chakra UI v3
│   ├── app/              # rutas, layout, metadata, not-found, og-image, robots, sitemap
│   ├── modules/          # UN MÓDULO POR PANTALLA (independiente)
│   │   ├── auth/         # P1
│   │   ├── ingredients/  # P2
│   │   ├── products/     # P3 + P4
│   │   ├── settings/     # P5
│   │   ├── orders/       # P6
│   │   ├── budgets/      # P7 + P8
│   │   ├── pdf/          # P9
│   │   └── whatsapp/     # P10 (solo orquestación outbound + eventos)
│   ├── shared/           # design system (tema, componentes compartidos, hooks)
│   └── lib/              # cliente API tipado (generado desde OpenAPI)
├── api/                  # FastAPI
│   ├── domain/           # ENTIDADES + MOTOR DE PRECIO. Sin I/O. 100% testable.
│   ├── data/             # repositorios SQLAlchemy, Alembic, Postgres
│   ├── presentation/     # routers, esquemas Pydantic, auth, DI, middlewares
│   └── bot/              # Chat SDK (WhatsApp) — adapter + state + handlers
├── infra/                # docker-compose, Caddy/nginx (TLS), scripts de despliegue
└── .github/              # CI/CD
```

### 1.2 Reglas de capas (no negociables)
| Capa | Depende de | Contenido |
|---|---|---|
| `domain` | nada | entidades, motor de precio, reglas de negocio, validaciones puras |
| `data` | domain | repositorios, migraciones, modelos ORM, mapeo ORM↔entidad |
| `presentation` | domain + data | routers HTTP, Pydantic, auth, serialización |
| `web/modules/*` | `lib` (API tipada) | UI por pantalla; **nunca** conoce detalles de la API |

- **Contrato**: FastAPI expone OpenAPI → CI genera tipos TS para `web/lib`. Sin contratos a mano.
- **Motor de precio** (el corazón del producto) vive en `api/domain/pricing.py`: entrada (insumos, cantidades, config de tenant, margen) → salida (desglose: materiales, mano de obra, gas/energía, merma, margen, precio final, redondeado). Cero I/O, cubierto con tests de tabla.
- Fórmula verificada contra screenshots: `(costo_materials + mano_obra) × (1 + margen%) → redondear(paso)`.

### 1.3 Motor de precio (fórmula de referencia)
```
costo_materials = Σ(ingrediente.unidad_compra × precio_unidad) × (1 + merma%)
mano_obra       = horas_preparación × valor_hora
gas             = costo_materials × gas%        (si include_gas)
base            = costo_materials + mano_obra + gas
precio_final    = base × (1 + margen%)
precio_enviado  = round_up(precio_final, paso_redondeo)
```

### 1.4 Seguridad transversal (no negociable, detalle en `security.md`)
| # | Premisa |
|---|---|
| 1–3 | Secrets solo en env del backend (cero `NEXT_PUBLIC_*`); gitleaks en repo y build; Postgres en red interna con usuario dedicado y sin puerto expuesto. |
| 4–7 | **RLS** por `tenant_id` en Postgres (defensa en profundidad); auth por defecto (allow-list de 9 endpoints públicos); sin IDOR (404 anti-sondeo). |
| 8 | Campos computados (`price`, `total`, `seq`, `breakdown`) solo-escritura del servidor; Pydantic `extra="forbid"`. |
| 9–10 | Sesión en cookie `HttpOnly; Secure; SameSite=Strict` con TTL corto + rotación; v1 sin contraseñas (magic link + Google GIS), tokens ≥256 bits almacenados como hash; futuro: argon2id. |
| 11–12 | `slowapi` con límites por endpoint (tabla en `api_endpoints.md` §0); hCaptcha en entradas públicas, firma de webhook, `/docs` cerrado en producción. |
| 13–15 | Solo SQLAlchemy con bind parameters; validación Pydantic estricta (allow-lists, longitudes, bordes); contenido de usuario como texto inerte (React/ReportLab/WhatsApp). |
| 16–17 | v1 sin uploads; PDF solo autenticado o URL firmada con expiración; schemas Response mínimos — costos nunca en PDF/WhatsApp. |
| 18–20 | Headers de hardening en el edge (HSTS preload, CSP, nosniff, DENY, Referrer, Permissions); HTTPS forzado (301); `pip-audit` + `pnpm audit` + Dependabot en CI. |

---

## 2. Módulos por pantalla (mapeo)

| Pantalla | Módulo web | Endpoints API (base) | Fase |
|---|---|---|---|
| P1 Auth / Cuenta | `modules/auth` | `/auth/magic-link`, `/auth/verify`, `/auth/logout`, `/me`, `/tenant` | 0 |
| P2 Ingredientes | `modules/ingredients` | `/ingredients` (CRUD), `/ingredients/{id}/stock` | 1 |
| P3 Listado productos | `modules/products` | `/products` (list, filter) | 1 |
| P4 Detalle producto | `modules/products` | `/products/{id}` (CRUD, `/recalculate`) | 1 |
| P5 Configuración | `modules/settings` | `/tenant/settings` (GET/PUT) | 1 |
| P6 Pedidos | `modules/orders` | `/orders` (CRUD), `/orders/{id}/quote`, `/orders/{id}/status` | 2 |
| P7 Presupuesto·cliente | `modules/budgets` | `/budgets` (POST wizard), `/customers` | 3 |
| P8 Presupuesto·resumen | `modules/budgets` | `/budgets/{id}`, `/budgets/{id}/items`, `/budgets/{id}/recalculate` | 3 |
| P9 PDF | `modules/pdf` | `/budgets/{id}/pdf` (generación + download) | 3 |
| P10 WhatsApp | `modules/whatsapp` + `api/bot` | `/budgets/{id}/whatsapp-link`, webhook `/webhooks/whatsapp` | 3 |

Cada módulo web es autónomo: propios componentes, hooks y tests; comparte solo `shared/`.

---

## 3. Fases (iterativo e incremental, entregas tempranas)

### Fase 0 — Fundaciones (Semana 1) · **Entrega: staging vivo con login**
- Monorepo, CI (lint + tests + build + preview deploy), docker-compose (postgres, api, web).
- Tema Chakra v3 desde DESIGN.md (`createSystem` + tokens semánticos, dark mode automático vía `useColorMode` + semantic tokens).
- Instalar skill de Chakra en el proyecto: `npx skills add https://github.com/chakra-ui/chakra-ui/tree/main/skills` (usar `chakra-ui-builder`).
- Auth: magic link por email (P1 base), sesión JWT httpOnly, multi-tenancy (`tenant_id` en todo).
- Shell de navegación (tab bar: Inicio · Pedidos · Productos · Más), landing mínima, página 404.
- Checklist base: favicon, meta descriptions, robots.txt, sitemap, OG/preview, banner de cookies, GA4 (tras consentimiento), HTTPS/HSTS forzado.
- Seguridad base (`security.md`): Caddy con TLS + security headers (#18/#19), `slowapi` + hCaptcha en auth (#11/#12), gitleaks + secret-scan de build en CI (#1/#2), `pip-audit`/`pnpm audit` (#20), migraciones con RLS activada (#4), cookies de sesión con flags estrictos (#9).
- Login Google (GIS ID token, skill `google-signin`): `auth/google/nonce` + `auth/google/signin`, identidad por `sub` (`google_id`), enlace solo tras re-auth por magic link; GCP: OAuth client web con origins autorizados, sin client secret (paso humano).
- **Criterio de salida**: usuario se crea cuenta con magic link, entra, ve el shell. Despliegue en staging reproducible.

### Fase 1 — Motor de precio + catálogo (Semanas 2–3) · **Entrega: el negocio calcula sus costos reales**
- P5 Configuración (costos y márgenes por tenant).
- P2 Ingredientes: CRUD, stock, unidades, umbral bajo (badges "disponibles/restantes/EMPTY").
- P4 Producto con receta (tabs Información/Ingredientes/Preparación/Costos), conversiones de unidades.
- `domain/pricing.py` + tests exhaustivos (tabla de casos).
- P3 Listado con búsqueda y chips de categoría; precios derivados del motor.
- **Criterio de salida**: cargar 20 insumos + 5 productos → cada producto muestra costo y precio final correctos (verificados contra la fórmula).

### Fase 2 — Pedidos y stock (Semanas 4–5) · **Entrega: operación diaria de pedidos**
- P6 Pedidos: crear (cliente + ítems + ajustes de porción), desglose completo, margen por pedido (override), redondeo.
- CTA único "Le paso $X" (wa.me prellenado) — sin Chat SDK todavía (fase 3).
- Descuento de stock **atómico** al confirmar pedido (transacción) + `stock_movement` por cada movimiento.
- Estados de pedido (nuevo → confirmado → entregado), historial y filtros.
- **Criterio de salida**: pedido → stock descuenta, precio cuadra con la fórmula, no se permite stock negativo.

### Fase 3 — Presupuestos + PDF + WhatsApp (Semanas 6–7) · **Entrega: ciclo completo presupuesto→cliente**
- P7 Wizard paso 1 (cliente: nombre, teléfono, email, fecha de entrega, notas) + alta/reafe de clientes.
- P8 Wizard paso 2 (resumen: secuencia `#000NN`, tabla ítems con **cantidad explícita**, subtotal, costos, ganancia, total venta) — corrigiendo el bug de cantidades de la app original.
- P9 PDF server-side (ReportLab/WeasyPrint): branding del tenant, datos, ítems, totales, footer; cache invalidado al editar.
- P10 WhatsApp outbound: link `wa.me/?text=` prellenado (template con ítems + total), registro de envío.
- P10 inbound (opcional de la fase): bot del negocio con **Chat SDK** (`chat` + `@chat-adapter/whatsapp` sobre WhatsApp Business Cloud API, `createRedisState`), webhook en route handler de Next.js o de la API; handlers `onNewMention`/`onSubscribedMessage`; auto-respuesta con el último presupuesto.
- **Criterio de salida**: presupuesto desde cero → PDF descargado → enviado por WhatsApp con un toque; bot responde al cliente.

### Fase 4 — Endurecimiento y producción (Semana 8) · **Entrega: production-ready**
- Auditoría de seguridad completa contra `security.md` (20 ítems, checklist 100%): **cero keys/secrets en el bundle del frontend** (env solo backend + whitelist de `NEXT_PUBLIC_*`; check en CI que escanea el build), headers presentes en todas las rutas, matriz IDOR + tests cross-tenant de RLS, rate limits por endpoint verificados, firma de webhook, scan de dependencias sin CVE high.
- Auditoría de contraste (WCAG AA 4.5:1) — **hallazgo previo: `--fg-muted #909090` sobre `--paper-50` da 3.1:1 (fallo)**. Corregir a `#6F6F6F` (≈4.9:1) y revalidar todos los tokens.
- Responsive audit: Lighthouse mobile ≥ 90, touch targets ≥ 44px, safe-areas, test en dispositivos reales (iOS/Android).
- Imágenes: pipeline webp (next/image + sharp), fuentes self-hosted.
- Crawler de enlaces rotos en CI (lychee) + fix.
- Formularios: react-hook-form + zod (web) / Pydantic (API), errores inline con `aria-describedby`.
- Anti-spam: hCaptcha en signup/contacto, rate limiting (slowapi) en endpoints de auth y formularios, honeypot.
- GA4 completo: eventos `create_order`, `create_budget`, `pdf_download`, `whatsapp_send`, `signup` — gateados por consentimiento.
- CTA único por pantalla (auditoría UX): una sola acción primaria por vista.
- Legal: política de privacidad + términos publicados (ver `legal_*.md`), enlace en footer.
- **Criterio de salida**: Lighthouse ≥ 90 en las 4 categorías, checklist de seguridad 100%, legal publicado, sin warnings de build.

---

## 4. Checklist técnico (trazabilidad → fase)

| # | Requisito | Dónde se cubre | Fase |
|---|---|---|---|
| 1 | DESIGN.md como sistema de UI | Tema Chakra (tokens semánticos, tipografía Montserrat, radius, outlines sobre sombras, dark mode auto) | 0 |
| 2 | Chakra UI (design system) | `npx skills add …/chakra-ui-builder`; typegen de tokens | 0 |
| 3 | Buenas prácticas | TS strict, ESLint+Prettier, Vitest/pytest/ruff, contratos OpenAPI→TS, CI con preview, feature flags, Sentry | 0 |
| 4 | Capas data/domain/presentation + módulo por pantalla | Sección 1.2 | 0 |
| 5 | Política de privacidad + T&C | `legal_privacy_policy.md`, `legal_terms.md` (redactados con criterio humanizer) | 0/4 |
| 6 | Sin APIs/secrets en frontend | Env solo backend; whitelist `NEXT_PUBLIC_*`; scan de build en CI | 0/4 |
| 7 | HTTPS forzado | TLS en edge (Caddy), HSTS, redirect 301, sin mixed content | 0 |
| 8 | Banner de cookies | Chakra, persiste decisión, gatea GA4 (solo analytics tras consentimiento) | 0 |
| 9 | Meta descriptions | `metadata` por ruta + `metadataBase` | 0 |
| 10 | Web preview link | OG/Twitter tags + `app/og` (og-image dinámico) + URL canónica | 0 |
| 11 | Favicon | `app/icon.svg` + manifest | 0 |
| 12 | Sitemap + robots.txt | `app/sitemap.ts`, `app/robots.ts` | 0 |
| 13 | Imágenes webp | next/image con `sizes`, pipeline sharp → webp en assets | 1/4 |
| 14 | Contraste corregido | Hallazgo `--fg-muted` → `#6F6F6F`; auditoría AA completa | 4 |
| 15 | Mobile responsive | Base-first, breakpoints 480/640/900, `min-height:100dvh`, safe-areas | 0/4 |
| 16 | Página 404 | `app/not-found.tsx` temática | 0 |
| 17 | Enlaces rotos | Crawler CI (lychee) sobre build + sitemap | 4 |
| 18 | Validación de formularios | zod+RHF / Pydantic, errores inline, estados a11y | 1 (desde el primer form) |
| 19 | SPAM safe | hCaptcha, rate limiting, honeypot, verificación de email | 3/4 |
| 20 | GA4 | Consent-gated, eventos de negocio, dataLayer | 0/4 |
| 21 | CTA claro y único | Un primary por vista (gradient blue-400→500); audit UX | 2/4 |
| 22 | Chat SDK WhatsApp | `chat` + `@chat-adapter/whatsapp` (Cloud API) + Redis state; webhook verificado | 3 |
| 23 | **Seguridad: 20 ítems obligatorios** | `security.md` (control + implementación + verificación por ítem) + `api_endpoints.md` §0 (convenciones y límites de rate limiting) + §1.4 de este plan (premisas) | 0/4 |
| 24 | **Login Google (GIS)** | skill `google-signin`: `sub`=google_id, nonce un solo uso, `email_verified`, link tras re-auth, `GOOGLE_CLIENT_ID` público (sin client secret), CSP origins | 0 |

---

## 5. Decisiones de diseño (premisas fijadas)

1. **Billing fuera de la app** (como el original): acceso por pago único externo; la app solo aprovisiona cuenta por magic link (token de compra en el link, canjeable una vez).
2. **WhatsApp outbound = `wa.me`** (cero costo, sin Cloud API) para el envío al cliente; **inbound = Chat SDK** solo si el negocio quiere recibir mensajes (Cloud API, requiere verificación Meta).
3. **PDF server-side** (no jsPDF): control total del branding y sin costo en el cliente; cache por hash de contenido del presupuesto.
4. **Stock descuenta al confirmar**, no al crear (evita roturas con presupuestos que no se transforman en pedidos).
5. **Margen por pedido** con override explícito en el pedido (corrige la ambigüedad de la app original: el override debe ser visible en UI).
6. **Multi-tenancy estricta**: `tenant_id` en toda consulta (middleware + a nivel de repositorio).
