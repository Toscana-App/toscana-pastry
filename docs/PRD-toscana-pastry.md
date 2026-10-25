# PRD — Toscana Pastry (v1)

**Estado:** borrador 1.2 · **Fecha:** 2026-10-25 · **Fuente:** `toscana-pastry_desarrollo.md` + memoria de Engram

## 1. Resumen

Toscana Pastry es una herramienta de gestión para una pastelería local: catálogo con motor de precios, stock de ingredientes, pedidos con descuento atómico de stock y presupuestos con PDF que se envían por WhatsApp. El acceso está gobernado por un sistema de roles estricto y robusto: **administrador** (gestión interna, exclusivo de la dueña), **negocios** (revendedores que ven la lista de precios para revendedores) y **clientes particulares** (consumidor final), con separación estricta de listas de precios entre tipos de cliente. La primera versión ya construyó 8 de 10 pantallas; lo que falta es cerrar el frontend de PDF/WhatsApp, implementar el sistema de roles de tres vías con precios duales, incorporar las specs refinadas del 23/10 y formalizar el E2E.

## 2. Contactos

- **Gaspar Spalla** — Product Owner / Reviewer. Único decisor de producción.
- **La dueña de la pastelería** — Única usuaria con rol de administrador.

## 3. Background

La pastelería se gestiona hoy con un servicio externo genérico que resuelve el problema de pastelerías en general pero no las necesidades específicas de este negocio: un solo tenant, flujo de presupuesto→pedido propio, dos listas de precios (revendedores y consumidor final) que nunca deben cruzarse, y envío por WhatsApp como canal real de venta. Del 14 al 15/10 se hizo el recon del sistema de referencia y se definió la spec completa (14 artifacts, master plan de 10 semanas). Del 14 al 18/10 se desarrollaron 8 fases con TDD y PRs apilados; 7 PRs están merged en main y 8 abiertos esperando review. El 23/10 se refinaron las specs (8 tareas nuevas #25–#32, decisión de arquitectura #7: PWA), aún sin commit. El sistema de roles de tres vías con precios duales es un requisito nuevo que extiende el modelo actual (admin/cliente) y debe implementarse de forma robusta, con control en el backend y verificación E2E.

## 4. Objetivo

Que la pastelería gestione el ciclo completo —precio, stock, pedido, presupuesto, envío— dentro de una herramienta propia, con un sistema de roles estricto que separe la gestión interna de los dos tipos de clientes y sus listas de precios, garantizando que un tipo de cliente jamás vea los precios del otro.

**Key Results (v1):**
1. Cerrar el 100% de las 10 pantallas del master plan (P1–P10) con todos los gates verdes (pytest / tsc / eslint / vitest / next build) — hoy está 9 de 10 (falta P9/P10 frontend, PR #17).
2. Sistema de roles de tres vías funcional y probado: cada rol ve exactamente su ámbito y el otro es invisible, verificado con tests de RBAC en el backend (403) y E2E en el frontend (0 fugas de precios entre listas).
3. Incorporar las 8 tareas nuevas de las specs del 23/10 (#25–#32) en el repo (hoy viven sin commit en el working tree).
4. Tasa de stock insuficiente sin corrupción de datos: 0 (el descuento atómico al confirmar ya existe; se protege con el test E2E formalizado en el repo).

## 5. Segmentos de mercado

1. **Administrador (la dueña).** Único usuario con gestión interna completa: catálogo, precios, stock con movimientos trazables (compra/merma/ajuste), usuarios y cierre de ventas. Es el buyer y la única persona con este rol.
2. **Negocios** (dietéticas, kioscos y otros revendedores). Ven la lista de productos **con precios para revendedores** y gestionan todo lo relacionado a su pedido (crear, ver estado, seguimiento).
3. **Clientes particulares** (consumidor final). Ven la lista de productos **con precios para consumidor final** y gestionan todo lo relacionado a su pedido.

**Restricciones:** tenant único (no es SaaS); el rol administrador es exclusivo de la dueña y no es delegable; **separación estricta de precios: un negocio jamás ve precios de consumidor final y un cliente particular jamás ve precios de revendedores**; el administrador también es desarrollador y reviewer; el presupuesto de tiempo es acotado por la operación del local.

## 6. Propuestas de valor

### 6.1 Para el administrador (la dueña)

- **Quién:** la dueña de la pastelería, única administradora.
- **Por qué:** necesita gestionar catálogo, stock y los dos listados de precios desde un solo lugar, sin hojas de cálculo.
- **Antes:** gestión manual y un servicio externo genérico donde el precio no se derivaba de los ingredientes ni el stock se descontaba solo.
- **Cómo:** motor de precio que deriva el precio en cada lectura (nunca persistido), stock con descuento atómico al confirmar el pedido, y presupuesto con PDF listo para enviar.
- **Después:** el pedido se arma en minutos, el precio se actualiza solo cuando cambia un insumo, y no hay stock negativo ni errores de cuenta.
- **Alternativas:** el servicio externo actual, Excel, memoria. Se elige esta herramienta por el precio derivado, el descuento atómico de stock, el control de roles estricto y el envío por WhatsApp integrado.

> *Precio derivado en segundos, stock que se descuenta solo y presupuesto enviado por WhatsApp: la gestión interna de la pastelería termina en un solo lugar, bajo un solo rol.*

### 6.2 Para los negocios (revendedores)

- **Quién:** dietéticas, kioscos y otros negocios que revenden los productos.
- **Por qué:** necesitan saber el precio de reventa y el stock disponible, y gestionar sus pedidos sin llamar al local.
- **Antes:** pedido por WhatsApp o por teléfono, con precios de reventa que se comunicaban de palabra y pedidos sin trazabilidad.
- **Cómo:** ven el catálogo con **precios para revendedores** y gestionan su pedido completo: creación, estado y seguimiento, con la misma trazabilidad que un cliente particular.
- **Después:** el pedido de reventa queda registrado con su precio de lista, su stock se descuenta con las mismas reglas atómicas y el negocio sabe en qué estado está su pedido.
- **Alternativas:** WhatsApp directo con el local, precio de boca. Se eligen los precios de reventa en plataforma porque el negocio ve su lista real, no la de consumidor final, y su pedido queda gestionable.

> *El negocio ve su lista de reventa real y gestiona su pedido completo: sin llamadas, sin precios mezclados y con trazabilidad desde el pedido hasta la entrega.*

### 6.3 Para los clientes particulares

- **Quién:** el consumidor final.
- **Por qué:** quiere ver el catálogo con su precio real, pedir o recibir un presupuesto claro (con total e IVA 21%) y cerrar la compra por WhatsApp.
- **Antes:** mensaje de texto con precios a mano, fácil de malinterpretar, o visita al local.
- **Cómo:** ven el catálogo con **precios para consumidor final**, crean o reciben presupuestos con PDF, y gestionan su pedido.
- **Después:** el presupuesto es profesional, revisable y guardable; la aprobación pasa por el mismo canal (WhatsApp); el cliente ve siempre su precio, nunca el de revendedores.
- **Alternativas:** WhatsApp Business manual, PDF hecho a mano. Se elige esta porque el PDF y el mensaje se generan solos del presupuesto y el precio mostrado es el del consumidor final.

> *El cliente ve su precio, recibe el presupuesto por WhatsApp como un PDF listo y la compra se cierra en el mismo hilo.*

## 7. Solución

### 7.1 UX / Flujos clave

- **Rol y precios:** el rol del usuario determina qué lista de precios se sirve. Negocio → lista de revendedores; cliente particular → lista de consumidor final; los dos listados son vistas exclusivas una de la otra. El administrador ve y administra ambas.
- **Precio:** el formulario de producto recalcula en vivo vía `POST /pricing/preview` (sin motor espejo en cliente), para ambos listados.
- **Pedido:** crear pedido → confirmar → descuento atómico de stock; si falta, 409 `{insufficient_stock}` con lo disponible y lo faltante.
- **Presupuesto:** wizard (cliente con teléfono, sin email) → detalle → PDF + botón "Enviar por WhatsApp" (PR #17 pendiente).

### 7.2 Features de la primera versión

1. **Sistema de roles estricto (nuevo, robusto):** tres roles — `admin` (exclusivo de la dueña, gestión interna completa), `negocio` (precios de revendedores + gestión de sus pedidos) y `cliente` (precios de consumidor final + gestión de sus pedidos). Controlado en el backend (403 explícito por acceso fuera de rol) y en el frontend (rutas protegidas), con tests de RBAC y E2E que prueben que un negocio no recibe precios de consumidor final y viceversa. Extiende el modelo actual `admin`/`customer` con el rol `negocio` y el segundo listado de precios.
2. **Precios duales con markup configurable:** el precio de consumidor final es **40% más alto** que el de revendedores (precio base derivado de ingredientes × 1,40), y el porcentaje es **configurable desde el panel de admin** (setting de tenant, nunca persistido en los productos). La lista de precios es **adjuntable en CSV y PDF** por audiencia (revendedores / consumidor final), gateada por rol.
3. **P9/P10 frontend (PR #17):** preview del PDF y botón de envío por WhatsApp.
4. **Specs del 23/10 (#25–#32):** PWA (decisión #7), tags de alergias/restricciones en productos (P3/P4), order-window (P5/P6), estado de pago, domicilio de entrega, resumen semanal + export CSV, privacidad de Google Sign-In.
5. **E2E formalizado:** el test de guard de admin (hoy `~/.hermes/scripts/e2e_admin_guard.js`) se convierte en test del repo con Playwright y se extiende a la separación de precios entre roles.
6. **Debt acotado:** decisión de producción de `SECRET_KEY` y resolución del footgun del enum `role` (mayúsculas en DB vs minúsculas en API) — esta corrección es ahora **mayor**, porque el sistema de tres roles aumenta la superficie donde una confusión de rol causa fugas de precios.

### 7.3 Tecnología

Backend FastAPI + DDD (dominio puro, `data/` SQLAlchemy async + SQLite), PyJWT, weasyprint. Frontend Next.js 15/16 + Chakra UI v3 + zod + vitest. Contrato de dinero: Money como long de centavos de extremo a extremo; `Pct` y `Qty` como strings. Los precios duales viven en el dominio como dos vistas derivadas (nunca persistidas) del mismo catálogo, diferenciadas por el tipo de cliente.

### 7.4 Asumos y preguntas abiertas

- **Asumo** que la tasa de conversión presupuesto→pedido mejorará con el PDF; no hay baseline medido hoy.
- **Decidido (2026-10-25):** precio de consumidor final = precio de revendedores + 40%, configurable desde el panel de admin; lista de precios exportable en CSV y PDF (spec en `odd/tasks/roles-dual-pricing.md`, S2/S3).
- **Abierto:** si la inbound de WhatsApp (WhatsApp Business Cloud API) entra en v1 o es fase posterior (hoy está explícitamente fuera).
- **Abierto:** contrato de `GET /admin/users` (paginación/envelope) sin spec.
- **Abierto:** decisión de Gaspar sobre el borrado de las 8 branches remotas ya mergeadas.

## 8. Release

**Versión 1 (corta, ~2–3 semanas de trabajo):** PR #17 (P9/P10 frontend), el sistema de roles de tres vías con precios duales (markup configurable default 40%), export CSV/PDF de la lista de precios y su cobertura de tests RBAC/E2E, specs del 23/10 committeadas y aplicadas, E2E con Playwright en el repo, y las dos decisiones de deuda (SECRET_KEY, enum `role` — esta última antes de habilitar el tercer rol). Todo sobre las ramas ya abiertas (#9–#16) más ramas nuevas para roles/precios duales y PWA/tags/resumen.

**Luego (v1.x):** inbound de WhatsApp Business Cloud API, multi-tenant si aparece la demanda, y el contrato de `GET /admin/users`.

**No se hace en v1:** multi-tenant, SaaS, facturación/emisión de facturas, app nativa (la PWA la reemplaza), delegación del rol administrador a otros usuarios, visibilidad cruzada de listas de precios (es un non-goal por diseño), y ningún cambio del contrato de Money a otro formato.
