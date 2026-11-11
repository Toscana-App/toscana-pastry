# P13 — Facturación electrónica ARCA (monotributo)
Módulo: `backend/src/api/v1/invoicing` + `backend/src/data/invoicing` + `pdfgenerator` (render) + `frontend/src/modules/invoicing` · Rutas: `/api/v1/invoices`, `/api/v1/invoicing/settings` · Fase: **facturación**

## Contexto
Pastelería Toscana factura electrónicamente en Argentina vía los web services de ARCA (ex AFIP, Decreto 953/2024): autenticación **WSAA** (TRA firmado PKCS#7 → token + sign ~12 h) y emisión por **WSFEv1** (`FECompUltimoAutorizado` + `FeCAESolicitar` → CAE 14 dígitos). El emisor es monotributista: siempre emite **Factura C** (tipo 011) con condición "Responsable Monotributo". La referencia técnica es el skill `afip-facturacion` (github.com/alandaitch/afip-facturacion), validado contra estos mismos web services.

Investigación de soporte (ARCA, categorías de monotributo vigentes, tipos de comprobante y su matriz de emisión): `odd/tasks/afip-invoicing.md` → sección Investigación. Resumen operativo:
- Comprobantes: Factura C = 011, ND C = 012, NC C = 013. `DocTipo` receptor: 99 Consumidor Final (nro 0), 80 CUIT, 86 DNI.
- CAE: 14 dígitos, vencimiento ~10 días. Sin CAE no hay validez fiscal. Emisión irreversible (anulación solo con NC).
- Monotributo: 11 categorías A–K (topes y cuotas desde 2026-08-01); la categoría del emisor es dato de settings, no se calcula en el sistema.
- QR del PDF (RG 4291/2018): JSON base64 `{ver, fecha, cuit, ptoVta, tipoCmp, nroCmp, importe, moneda, ctz, tipoDocRec, nroDocRec, tipoCodAut:"E", codAut}` → `https://www.afip.gob.ar/fe/qr/?p=<b64>`.
- Fechas: fuera de ±5 días (productos) / ±10 (servicios) ARCA rechaza (obs 10015).
- Patrón SSL: AFIP exige `SECLEVEL` bajo en la sesión HTTP (`DH_KEY_TOO_SMALL`).

## User story
> Como **admin del negocio**, quiero **emitir la Factura C con CAE de los pedidos que yo elija, ver el PDF oficial y descargarlo**, para **cumplir la obligación fiscal sin salir de la app**.

**Criterios de aceptación**
- [ ] Solo el rol `admin` emite o lee comprobantes: cliente y negocio → 403, anónimo → 401.
- [ ] Elijo en la app qué pedido facturar (el botón solo aparece en pedidos entregados/pagados sin comprobante); el backend nunca factura por su cuenta.
- [ ] Antes de emitir veo un alert explícito de que la acción es irreversible; sin confirmación no se emite nada.
- [ ] Emito contra homologación por defecto; producción exige configuración explícita.
- [ ] Recibo número de comprobante + CAE + vencimiento y descargo el PDF oficial con QR.
- [ ] Un pedido se factura una sola vez (reintento → 409 con el comprobante existente).
- [ ] Ninguna credencial (certificado, clave, token) aparece en el repo, en el frontend o en los logs/errores.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Configurar emisor | Admin | Settings de facturación: CUIT, punto de venta, razón social, domicilio, condición, categoría monotributo, IB, inicio de actividades |
| UC-02 Facturar un pedido | Admin | Detalle de pedido → "Facturar" → alert de irreversibilidad → form (concepto, período, receptor, items) → confirmación → CAE + PDF |
| UC-03 Ver comprobantes | Admin | `GET /invoices` (filtro por pedido, paginación) + detalle |
| UC-04 Descargar PDF | Admin | `GET /invoices/{id}/pdf` → PDF oficial con QR (solo `estado=A`) |

## Requerimientos funcionales
- **RF-P13-01**: `POST /api/v1/invoices` (admin): emite Factura C contra un pedido. Payload: `order_id`, `concepto` (1 productos / 2 servicios / 3 ambos), `fch_serv_desde`/`fch_serv_hasta` (obligatorios para 2/3), `doc_tipo` (99/80/86), `doc_nro`, `receptor_nombre`, `items[]` opcional (descripción/cantidad/precio unit para el PDF). El **importe total es el neto del pedido** (autoridad del backend). Response 201: `id, order_id, punto_venta, tipo_cbte, numero, cae, cae_vto, fecha, imp_total, estado, pdf_url`. (UC-02)
- **RF-P13-02**: Emisión: `FECompUltimoAutorizado` → próximo número correlativo por `(punto_venta, tipo_cbte)` → `FeCAESolicitar` → persistir comprobante (`cae`, `cae_vto`, `estado A`, observaciones) + items. (UC-02)
- **RF-P13-03**: Idempotencia por pedido: `unique(invoices.order_id)`; pedido ya facturado → 409 `{existing_invoice}`. (UC-02)
- **RF-P13-04**: `GET /api/v1/invoices` (filter `order_id`, `page`, 20/página) y `GET /api/v1/invoices/{id}` (detalle con items y observaciones) — admin. (UC-03)
- **RF-P13-05**: `GET/PUT /api/v1/invoicing/settings` (admin): fila única con `cuit` (11 dígitos), `punto_venta`, `razon_social`, `domicilio`, `condicion_iva`, `categoria_monotributo` (A–K), `ingresos_brutos`, `inicio_actividades`. Precondition para emitir. (UC-01)
- **RF-P13-06**: `GET /api/v1/invoices/{id}/pdf` (admin): PDF formato oficial ARCA con QR RG 4291/2018, renderizado por `pdfgenerator` (`POST /render/invoice-arca`). Solo comprobantes `estado=A`; rechazados → 409. (UC-04)
- **RF-P13-07**: Frontend: botón "Facturar" en el detalle del pedido (admin) solo para pedidos `entregado` o pagados sin comprobante; AlertDialog de irreversibilidad antes del POST; form con items pre-cargados desde el pedido; resultado con número `PV-NNNNNNNN`, CAE, vencimiento y descarga de PDF. (UC-02/04)

## Requerimientos no funcionales
- **RNF-P13-01**: **Guard admin en los 6 endpoints** (matriz en `odd/tasks/afip-invoicing.md` S6): `require_admin` → cliente/negocio 403, anónimo 401. Matriz de tests permanente `test_invoicing_rbac_matrix.py`. Nadie desde consola ni con token de sesión cliente puede usar el módulo. (crítico)
- **RNF-P13-02**: **Cero secretos en el repo**: certificado/clave vía variables de entorno (`AFIP_PRIVATE_KEY_PATH`/`AFIP_CERT_PATH` o contenido PEM), `AFIP_ENV`, overrides opcionales `AFIP_WSAA_URL`/`AFIP_WSFE_URL`. `.env` gitignored; `.env.example` con valores vacíos. CUIT/punto de venta en la DB (datos públicos de comprobante, no secretos). (crítico)
- **RNF-P13-03**: **Siempre homologación**: `AFIP_ENV` default `homo`; producción exige `AFIP_ENV=prod` explícito y la validación de arranque en `ENVIRONMENT=prod` lo requiere. La suite de tests nunca toca la red AFIP (cliente fake).
- **RNF-P13-04**: **Desacople**: el módulo `invoicing` no importa módulos de otras features (solo dependencias compartidas); el render va por HTTP a `pdfgenerator` (`PdfClient`); la firma/token se aíslan en `data/invoicing/`.
- **RNF-P13-05**: **Degradación limpia**: sin settings (sin CUIT/PV) → 503 `invoicing_not_configured`; sin certificados legibles → 503 `afip_credential_missing`; ARCA caído → 503 `afip_unavailable`; pdfgenerator caído → 503. Ningún 500 con stack trace ni filtrado de paths/tokens/certificados en responses o logs.
- **RNF-P13-06**: **Integridad**: CAE validado a 14 dígitos; `unique (punto_venta, tipo_cbte, numero)`; `ImpTotal` derivado del pedido, nunca del payload; fechas dentro de la ventana de ARCA.
- **RNF-P13-07**: **TDD**: tests antes de cada implementación; suite backend verde en CI (Postgres), suite de pdfgenerator verde en local, gate del frontend (vitest + tsc + eslint + build) verde.
- **RNF-P13-08**: **Auditoría**: log por emisión (usuario, pedido, comprobante, CAE, timestamp) con datos saneados (sin token/sign/contenido de certificado).

## Tareas
- [ ] Backend: dominio `domain/invoicing.py` (entidades + reglas puras) — T1
- [ ] Backend: `InvoiceORM`/`InvoiceItemORM`/`InvoicingSettingsORM` + `migrations/0011_invoicing.sql` + repository — T2
- [ ] Backend: cliente WSAA/WSFEv1 (`data/invoicing/`) + config `AFIP_*` + `.env.example` — T3
- [ ] Backend: use case `issue_invoice` + router `/invoices` + `/invoicing/settings` + matriz RBAC — T4
- [ ] pdfgenerator: `POST /render/invoice-arca` (formato oficial + QR) — T5
- [ ] Backend: `GET /invoices/{id}/pdf` vía `PdfClient` — T6
- [ ] Frontend: `modules/invoicing` + acción "Facturar" en el detalle de pedido con AlertDialog — T7
- [ ] Verificación completa + PR (estado real de cada gate) — T8

## UI (Chakra v3 + DESIGN.md)
- Botón "Facturar" en el detalle del pedido (sección admin): secundario, visible solo cuando el pedido es facturable (entregado/pagado, sin comprobante).
- AlertDialog (patrón destructivo: acción irreversible) con el resumen (pedido, total, receptor) y el aviso "La emisión queda registrada en ARCA y no puede revertirse; solo se anula con nota de crédito". Confirmación explícita.
- Form: select de concepto (Productos/Servicios/Ambos), inputs de fecha de servicio (solo si concepto 2/3), receptor (select doc tipo + número + nombre, default Consumidor Final), tabla de items pre-cargada (solo lectura en v1).
- Resultado: panel success con `PV-NNNNNNNN`, CAE, vencimiento del CAE y botón "Descargar PDF". Error: Alert danger con las observaciones de ARCA (texto saneado).
