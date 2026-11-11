# AFIP/ARCA — Facturación electrónica (monotributo)

## Objetivo

Incorporar un nuevo módulo al backend para facturación electrónica en Argentina
vía los web services de ARCA (WSAA + WSFEv1): emisión de Factura C con CAE y
PDF oficial con QR (RG 4291/2018). Módulo desacoplado, disponible únicamente
para el rol `admin`, sin credenciales en el repo y con pruebas siempre en
homologación.

- Baseline: `origin/main` @ `1f26c09` (2026-11-11)
- Rama única para todo el trabajo: `feat/afip-invoicing`
- Referencia técnica: skill `afip-facturacion` (github.com/alandaitch/afip-facturacion) —
  flujo WSAA/WSFE, formato del PDF con QR y troubleshooting.

## Investigación (pre-condición)

### Qué es ARCA

La **Agencia de Recaudación y Control Aduanero** reemplazó a la AFIP en
octubre de 2024 (Decreto 953/2024) como autoridad tributaria y aduanera de
Argentina. Administra impuestos, el monotributo, aduanas y la facturación
electrónica. Para facturar no cambió la operatoria: mismos tipos de
comprobantes (A/B/C), mismo CAE, mismos web services (WSAA, WSFEv1), mismos
certificados y puntos de venta. Los endpoints siguen en `*.afip.gov.ar`.

### Flujo de los web services (fuente: skill afip-facturacion)

1. **TRA** (`loginTicketRequest` XML, `service="wsfe"`, expiración ~10 min)
   firmado con el certificado X.509 + clave privada RSA vía PKCS#7/CMS
   (SHA-256) → base64.
2. **WSAA `loginCms(TRA)`** → `token` + `sign` + expiración (~12 h).
   - Producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL`
   - Homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL`
   - SSL: AFIP usa claves Diffie-Hellman débiles; la sesión HTTP debe bajar
     `SECLEVEL` o falla con `DH_KEY_TOO_SMALL`.
3. **WSFEv1 `FECompUltimoAutorizado(Auth, PtoVta, CbteTipo)`** → último
   comprobante autorizado; próximo número = último + 1.
   - Producción: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`
   - Homologación: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
4. **WSFEv1 `FeCAESolicitar(Auth, FeCAEReq{FeCabReq, FeDetReq})`** → CAE
   (14 dígitos), vencimiento del CAE, resultado `A`/`R` y observaciones.

Emitir un comprobante con CAE es **irreversible**: queda registrado en ARCA y
solo se anula con una nota de crédito.

### Monotributo — categorías vigentes (desde 2026-08-01, ajuste +16,8%)

Fuente: ARCA — Montos y categorías vigentes (tabla oficial). 11 categorías:

| Cat. | Tope facturación anual | Cuota mensual (servicios) | Cuota mensual (venta de bienes) |
|------|------------------------|---------------------------|---------------------------------|
| A | $12.009.410,45 | $49.527,18 | $49.527,18 |
| B | $17.595.182,74 | $56.379,08 | $56.379,08 |
| C | $24.670.494,31 | $66.020,12 | $64.530,58 |
| D | $30.628.651,43 | $84.612,93 | $82.564,81 |
| E | $36.028.231,33 | $119.811,45 | $108.267,51 |
| F | $45.151.659,41 | $150.784,21 | $129.930,65 |
| G | $53.995.798,87 | $230.312,94 | $158.815,05 |
| H | $81.924.660,37 | $522.706,68 | $317.895,01 |
| I | $91.699.761,90 | $963.747,86 | $474.992,78 |
| J | $105.012.519,20 | $1.167.299,76 | $580.793,69 |
| K | $126.610.838,75 | $1.614.446,04 | $702.103,24 |

- Escalas actualizadas semestralmente (febrero/agosto) según inflación;
  recategorización en julio (mira los 12 meses anteriores) y enero.
- Precio unitario máximo para cosas muebles: $716.840,77 (desde 2026-08-01);
  por encima no se factura dentro del monotributo.
- Un monotributista emite **Factura C a cualquier receptor**.
- Decision de diseño: la tabla NO entra al código. La categoría del emisor es
  dato que carga el admin en los settings de facturación; el módulo no calcula
  ni valida categorías.

### Tipos de comprobante (WSFE mercado interno)

| Comprobante | Código AFIP | Emisor | Receptor |
|-------------|-------------|--------|----------|
| Factura A | 001 | Resp. Inscripto | Resp. Inscripto |
| Factura B | 006 | Resp. Inscripto | Consumidor Final, Monotributo, Exento |
| Factura C | 011 | Monotributo, Exento | Cualquiera |
| Nota de Débito A / B / C | 002 / 007 / 012 | igual a su factura | — |
| Nota de Crédito A / B / C | 003 / 008 / 013 | igual a su factura | — |

- `DocTipo` del receptor: **99** = Consumidor Final (DocNro 0), **80** = CUIT,
  **86** = DNI. (El skill de referencia trae un typo: etiqueta 96 como DNI;
  96 es CUIL. Se usa la tabla oficial.)
- CAE: 14 dígitos, vencimiento ~10 días. Sin CAE el comprobante no tiene
  validez fiscal.
- QR (RG 4291/2018, RG 5228/2019): JSON base64
  `{ver, fecha, cuit, ptoVta, tipoCmp, nroCmp, importe, moneda, ctz,
  tipoDocRec, nroDocRec, tipoCodAut:"E", codAut}` → URL
  `https://www.afip.gob.ar/fe/qr/?p=<b64>`.
- Fechas: ARCA rechaza fechas fuera de ±5 días (productos) / ±10 (servicios) —
  obs. 10015.
- Monotributistas: los servicios de padrón (`ws_sr_padron_*`) están bloqueados,
  los datos del receptor se pasan por parámetro (no se autocompletan).

## Estado actual (evidencia sobre origin/main)

- No existe ninguna tabla de facturación: `backend/src/data/models.py`
  (793 líneas, 42 tablas) no tiene `invoices`/`facturas`; el PRD excluye
  facturación en v1 ("No se hace en v1: facturación/emisión de facturas").
- Tablas existentes a las que se une el módulo: `orders` (id, code, status,
  customer_name, customer_phone, date, payment_*), `order_items`
  (snapshot, unit_price String), `customers` (name, phone — sin CUIT),
  `business_settings` (business_name — sin datos fiscales).
- Money en la DB: String decimal (`unit_price`, `discount_amount`); en el borde
  de API: **integer cents** (convención del repo: `long` de centavos).
- Guards: `require_admin` en `backend/src/api/v1/dependencies.py`; matriz RBAC
  por archivo (`tests/integration/api/test_admin_rbac_matrix.py`).
- Última migración: `0010_refresh_tokens.sql` → la nueva es `0011`.
- `pdfgenerator/` (paquete aparte, FastAPI + reportlab + weasyprint + pymupdf,
  sin gate de CI) expone `POST /render/{...}` → `application/pdf`; el backend
  lo llama vía `data/pdf/client.py` (`PdfClient`, `PdfServiceError` → 503).
- `.gitignore` ya cubre `.env` y `.env.*`.
- `backend/pyproject.toml`: sin lib de SOAP ni `cryptography`.
- Frontend: detalle de pedido en `app/pedidos/[id]/page.tsx` +
  `modules/orders/components/OrderDetailPage.tsx`; patrón de módulos
  `modules/<feature>/{types,schema,service,hooks,components}`.

## Specs

### S1 — Emitir comprobante (backend)

`POST /api/v1/invoices` (admin):

```json
{
  "order_id": "uuid-del-pedido",
  "concepto": 1,
  "fch_serv_desde": "2026-11-01",
  "fch_serv_hasta": "2026-11-30",
  "doc_tipo": 99,
  "doc_nro": 0,
  "receptor_nombre": "Juan Pérez",
  "items": [
    {"descripcion": "Bizmerengue 20 porciones", "cantidad": 1, "precio_unit": "5200.00"}
  ]
}
```

- `concepto` 1=productos, 2=servicios, 3=ambos; 2/3 exigen
  `fch_serv_desde`/`fch_serv_hasta`.
- `doc_tipo`: 99 (CF, `doc_nro` 0), 80 (CUIT) o 86 (DNI).
- `items` opcional (detalle para el PDF); el **importe total es el neto del
  pedido** — el backend es la autoridad, el frontend no envía ni calcula
  montos.
- Response 201: `{id, order_id, punto_venta, tipo_cbte, numero, cae,
  cae_vto, fecha, imp_total, estado, pdf_url}`.
- Errores: 404 pedido inexistente; 409 `{existing_invoice}` si el pedido ya
  tiene comprobante (idempotencia por `unique(order_id)`); 422 validaciones
  de payload; 400 rechazo de ARCA con observaciones saneadas; 503
  `invoicing_not_configured` / `afip_unavailable` / `afip_credential_missing`.

### S2 — Registro de comprobantes

- `GET /api/v1/invoices` (filter `order_id`, `page`, 20/página) — admin.
- `GET /api/v1/invoices/{id}` — admin. Detalle con items y observaciones.

### S3 — Settings del emisor

`GET/PUT /api/v1/invoicing/settings` (admin): `cuit` (11 dígitos),
`punto_venta` (int), `razon_social`, `domicilio`, `condicion_iva`
("Responsable Monotributo"), `categoria_monotributo` (A–K),
`ingresos_brutos` ("Exento" o n°), `inicio_actividades` (DD/MM/YYYY).
Fila única; precondition para emitir (sin CUIT+PV no hay emisión → 503).

### S4 — PDF oficial con QR

`GET /api/v1/invoices/{id}/pdf` → `application/pdf`. Render en
`pdfgenerator` (endpoint nuevo `POST /render/invoice-arca`), formato oficial
ARCA (banner ORIGINAL, recuadro encabezado, letra C, datos emisor/receptor,
tabla de detalle, totales, QR RG 4291/2018, CAE + vencimiento). Solo para
comprobantes `estado=A`.

### S5 — Frontend (gestión de qué se factura + alert)

- La acción "Facturar" vive en el detalle del pedido (admin). El botón solo
  aparece para pedidos `entregado` o pagados **sin comprobante previo** — el
  frontend decide qué ventas se facturan; el backend nunca factura solo.
- Antes de enviar: **AlertDialog** advirtiendo que la emisión es una acción
  financiera irreversible (queda registrada en ARCA; no hay anulación, solo
  nota de crédito). Sin confirmación explícita no hay POST.
- Form: concepto (select 1/2/3), período de servicio (visible si 2/3),
  receptor (doc tipo + nro + nombre, default Consumidor Final), items
  pre-cargados desde el pedido (descriptivo; no editables en v1).
- Éxito: panel con número de comprobante (`PV-NNNNNNNN`), CAE, vencimiento y
  descarga del PDF.

### S6 — Seguridad (matriz de guards)

| Endpoint | Guard hoy | Dato que expone | Guard requerido |
|---|---|---|---|
| `POST /invoices` | — (nuevo) | CAE, importes, receptor | `require_admin` (403/401) + kill-switch 503 |
| `GET /invoices` | — (nuevo) | CAE, receptor (PII) | `require_admin` |
| `GET /invoices/{id}` | — (nuevo) | CAE, receptor (PII) | `require_admin` |
| `GET /invoices/{id}/pdf` | — (nuevo) | PDF fiscal completo | `require_admin` |
| `GET /invoicing/settings` | — (nuevo) | datos fiscales del emisor | `require_admin` |
| `PUT /invoicing/settings` | — (nuevo) | modifica datos fiscales | `require_admin` |

Matriz de tests permanente: `test_invoicing_rbac_matrix.py`
(anónimo → 401; `customer`/`negocio` → 403; `admin` → 2xx). Nadie —consola,
token cliente o token negocio— puede emitir ni leer comprobantes.

## Decisiones

- **D1 [PENDIENTE OK — depencias]**: backend suma `zeep` (SOAP para WSAA/
  WSFEv1, el mismo cliente que usa la referencia) y `cryptography`
  (firmado PKCS#7 del TRA). Son la única vía para hablar con los web services
  de ARCA sin reimplementar SOAP a mano.
- **D2**: el PDF con QR se renderiza en `pdfgenerator`
  (`POST /render/invoice-arca`), no en el backend: reportlab ya está ahí,
  `PdfClient` ya es el borde de render del repo y así el módulo de
  facturación queda desacoplado (HTTP boundary, 503 si el service no responde).
  Nueva dep en pdfgenerator: `qrcode` (pillow ya viene con weasyprint).
- **D3**: token WSAA con cache **en memoria** por proceso (TTL 11h50m, margen
  de 10 min sobre los ~12 h de vigencia), no en archivo: evita carreras entre
  instancias y no deja tokens en disco.
- **D4**: `AFIP_ENV` **default `homo`**. Producir exige `AFIP_ENV=prod`
  explícito y `validate_for_startup` lo exige cuando `ENVIRONMENT=prod`
  (evita desplegar prod apuntando a homologación por accidente). Las pruebas
  SIEMPRE corren contra homo (y de hecho con cliente AFIP fake: cero red).
- **D5**: money: String decimal en la DB (patrón del repo), **integer cents en
  el borde de API** (convención de todo el repo — `imp_total` y
  `items[].precio_unit` como int de centavos; el frontend ya está implementado
  así). El frontend no
  calcula importes.
- **D6**: una factura por pedido (`unique invoices.order_id`). NC/ND quedan
  fuera de scope de esta entrega (el anulación es vía contador en v1).
- **D7**: frontend v1 = flujo de facturar en el detalle de pedido. La
  pantalla de listado de comprobantes se difiere (el endpoint `GET /invoices`
  existe y el botón de "ya facturado" lo usa; no se construye la UI de lista).
- **D8**: visibilidad de la acción en el frontend (S5): solo pedidos
  `entregado` o con `payment_status` pagado y sin comprobante.
- **D9**: `DocTipo` oficial: 99 CF / 80 CUIT / 86 DNI (el skill de referencia
  trae el typo 96→DNI; se corrige).
- **D10 — sin secretos en el repo**: variables de entorno
  `AFIP_PRIVATE_KEY_PATH`, `AFIP_CERT_PATH` (o `AFIP_PRIVATE_KEY_PEM`/
  `AFIP_CERT_PEM` con el contenido base64), `AFIP_ENV`, y overrides opcionales
  `AFIP_WSAA_URL`/`AFIP_WSFE_URL`. El CUIT y el punto de venta NO son
  secretos (van a todo comprobante): viven en la tabla de settings (DB).
  `.env.example` documenta los nombres con valores vacíos; `.env` ya está
  gitignored. Ni el front ni el back llevan credenciales hardcodeadas; los
  errores 503 no filtran paths, tokens ni contenido de certificados.

## Tasks

Rama única: `feat/afip-invoicing`. Convención: commit conventional por task
(`feat(invoicing): …` / `test(invoicing): …` / `docs(invoicing): …`), un
commit por task (los archivos compartidos se integran antes de commitear).

### T0 — Docs (task file + spec)
- Archivos: `odd/tasks/afip-invoicing.md` (este), `docs/specs/p13_invoicing.md`,
  `docs/specs/api_endpoints.md` (filas + conteo), `docs/specs/security.md`
  (matriz S6), `docs/specs/master_plan.md` (fase + decisión de arquitectura).
- Status: OPEN

### T1 — Dominio (puro)
- Archivos: `backend/src/domain/invoicing.py` (entidades `Invoice`,
  `InvoiceItem`, `InvoicingSettings`; reglas: concepto 2/3 exige período,
  CAE 14 dígitos, fechas dentro de la ventana de ARCA, doc_tipo válido,
  importe > 0, un comprobante por pedido) + `backend/tests/unit/
  domain/test_invoicing.py`.
- Commits: `feat(invoicing): dominio de comprobantes ARCA con reglas puras`
  (+ tests en el mismo commit, TDD).
- Status: OPEN

### T2 — Data (ORM + migración + repositorio)
- Archivos: `backend/src/data/models.py` (`InvoiceORM`, `InvoiceItemORM`,
  `InvoicingSettingsORM`; FK `orders.id`, uniques `(order_id)`,
  `(punto_venta, tipo_cbte, numero)`),
  `backend/migrations/0011_invoicing.sql`,
  `backend/src/data/repositories/sql_invoice_repository.py` + tests.
- Commits: `feat(invoicing): tablas de comprobantes, settings y migración 0011`
- Status: OPEN

### T3 — Cliente AFIP (WSAA + WSFEv1) + config
- Archivos: `backend/src/core/config.py` (bloques `AFIP_*`),
  `backend/.env.example` (solo nombres, valores vacíos),
  `backend/src/data/invoicing/__init__.py`,
  `backend/src/data/invoicing/ssl_session.py` (SECLEVEL bajo, pattern
  `get_afip_session` de la referencia),
  `backend/src/data/invoicing/wsaa.py` (TRA + firma PKCS#7 + loginCms +
  token cache en memoria), `backend/src/data/invoicing/wsfe.py`
  (FECompUltimoAutorizado, FeCAESolicitar) + tests unitarios con transporte
  fake (cero red, cero credenciales).
- Commits: `feat(invoicing): cliente WSAA/WSFEv1 con config por entorno`
- Status: OPEN

### T4 — Use case + API + matriz RBAC
- Archivos: `backend/src/domain/use_cases/issue_invoice.py`,
  `backend/src/api/v1/invoicing/{__init__,router,dependencies,schemas}.py`
  (POST /invoices, GET /invoices, GET /invoices/{id}, GET/PUT
  /invoicing/settings), registro en `main.py`, kill-switch 503,
  `backend/tests/integration/api/test_invoices_api.py` (con cliente AFIP
  fake) + `test_invoicing_rbac_matrix.py` (401/403/2xx por endpoint).
- Commits: `feat(invoicing): endpoints de emisión y settings con guards admin`
- Status: OPEN

### T5 — PDF ARCA en pdfgenerator
- Archivos: `pdfgenerator/src/pdfgenerator/server.py` (endpoint
  `POST /render/invoice-arca`), renderer `pdfgenerator/src/pdfgenerator/
  renderers/invoice_arca.py` (formato oficial + QR RG 4291/2018),
  `pdfgenerator/pyproject.toml` (+`qrcode`), tests en `pdfgenerator/tests/`.
- Commits: `feat(pdfgenerator): render de factura ARCA con QR`
- Status: OPEN

### T6 — Endpoint de PDF del comprobante
- Archivos: extensión de `PdfClient.render_invoice_arca` + payload builder,
  `GET /invoices/{id}/pdf` en el router de invoicing, 503 con el service caído,
  tests (fake client, como `_FakePdfClient` de `tests/integration/conftest.py`).
- Commits: `feat(invoicing): descarga del PDF del comprobante`
- Status: OPEN

### T7 — Frontend
- Archivos: `frontend/src/modules/invoicing/{types.ts,schema.ts,service.ts,
  service.test.ts,schema.test.ts}`, acción "Facturar" en
  `modules/orders/components/OrderDetailPage.tsx` (AlertDialog de
  irreversibilidad + form + resultado CAE + descarga PDF).
- Commits: `feat(invoicing): acción de facturación en el detalle de pedido`
- Status: OPEN

### T8 — Verificación + entrega
- Gates: suite completa backend en CI (Postgres), suite de pdfgenerator en
  local (`uv sync` + `uv run pytest`), frontend (`npx vitest run
  src/modules/invoicing`, `npx tsc --noEmit`, `npx eslint src/modules/invoicing`,
  `npm run build`). Smoke en homologación real: pendiente de credenciales
  (`AFIP_ENV=homo` + certificado de homo vía env) — se declara en el PR.
- Commits: fixes que exijan los gates (si los hay).
- Status: OPEN

## Status

- Baseline: `origin/main` @ `1f26c09` (2026-11-11).
- Orden de delivery: T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8.
  T5 es independiente del backend (se puede paralelizar con T4).
- Pendiente de OK del usuario: **D1** (deps `zeep` + `cryptography` en
  backend; `qrcode` en pdfgenerator).

## Log

- **L1** (2026-11-11): pedido de Gaspar: pre-condición de investigar ARCA,
  niveles de monotributo y tipos de facturas; tarea de incorporar módulo de
  facturación electrónica ARCA usando su web-service con la skill
  `alandaitch/afip-facturacion` como referencia; criterios: senior-dev + TDD,
  seguridad admin-only (nadie desde consola ni con token cliente), estructura
  unida a las tablas existentes, el frontend decide qué ventas se facturan,
  pruebas siempre en homo, alert antes de emitir (irreversible), módulo
  desacoplado, variables de entorno y datos sensibles fuera de cualquier
  archivo. Output: (1) tasks en odd/tasks, (2) implementación por delegation
  sobre una misma branch, commit, push y PR.
