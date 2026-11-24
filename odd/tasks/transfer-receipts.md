# ODD — Comprobante de transferencia (payment receipt)

## Objetivo

El cliente de un pedido por transferencia adjunta el comprobante bancario
(imagen o PDF) desde el portal; el admin lo valida desde el panel antes de
marcar el pago (O4, `odd/tasks/payment-methods.md` T7).

## Fuente de verdad

- Este archivo (tabla de tareas + log); si la prosa choca con la tabla, gana
  la tabla.
- Patrón de uploads ya establecido en el codebase: spec P12
  (`docs/specs/p12_product_media.md`) + security #16
  (`docs/specs/api_endpoints.md`) — multipart, magic bytes, ≤5 MB, nombre de
  archivo por id. Implementación de referencia:
  `src/api/v1/products/router.py` (`POST /{id}/image`) +
  `src/api/v1/products/image_service.py` + `settings.MEDIA_ROOT` montado en
  `/media` (`src/main.py`).
- `python-multipart` ya está en `pyproject.toml` — cero dependencias nuevas.

## Diseño

- **Storage**: disco local en `MEDIA_ROOT` (setting existente, igual que las
  imágenes de producto), subdir `receipts/`. Nombre `{order_id}.{jpg|png|pdf}`
  — nunca el filename del usuario. Cero infra nueva; la columna guarda la URL
  relativa, así una migración futura a object storage no toca la API.
- **Upload**: `POST /api/v1/orders/{order_id}/payment/receipt` (multipart
  `file`).
  - Auth: cliente **propietario** del pedido (pedido ajeno = 404, patrón
    anti-sondeo).
  - `payment_method` debe ser `transfer` → 400 si no.
  - Solo mientras `payment_status == pending` (antes de que el admin lo
    marque pagado) → 409 `order_already_paid` si ya está pagado.
  - Un comprobante por pedido: el re-upload reemplaza (borra el archivo viejo).
  - Validación: magic bytes JPEG/PNG/PDF, ≤5 MB → 422 con `code`+`detail`
    (mismo shape que `ImageValidationError` de P12).
  - Persiste `payment_receipt_url` en `orders` (migración 0021) y escribe el
    archivo en `MEDIA_ROOT/receipts/`.
- **Visualización**: `GET /api/v1/orders/{order_id}/payment/receipt` →
  `FileResponse` con `media_type` según extensión.
  - **Ruta autenticada** (propietario o admin), NO en el `/media` público: el
    comprobante contiene datos bancarios. Security #16 se puntualiza: "PDF
    solo autenticado o URL firmada" → ruta autenticada.
  - Sin comprobante → 404.
- **Dominio** (cero lógica de negocio en SQL): `Order.attach_payment_receipt(url)`
  valida método/estado y reemplazo; los bytes y el disco viven en la capa API
  (mismo split que P12).

## Fuera de scope

- Comprobante para cash (se cobra en la entrega, no hay documento).
- Upload iniciado por el admin (lo adjunta el cliente).
- Flujo de rechazo con comentario (el admin decide marcar o no el pago; si se
  quiere comentario de rechazo, ODD aparte).
- Borrado explícito del comprobante (el re-upload reemplaza; borrar no fue
  pedido).

## Tasks

- **T1** — Este ODD
- **T2** — S1: `Order.attach_payment_receipt(url)` (guards: solo transfer, solo
  pending, paid monotónico) + tests de dominio
- **T3** — S2: migración 0021 `orders.payment_receipt_url TEXT` + repo
  (lectura/escritura del campo)
- **T4** — S3: `receipt_service` — magic bytes JPEG/PNG/PDF + límite 5 MB,
  `ReceiptValidationError(code, detail)` + tests unit
- **T5** — S4: endpoint POST (owner, transfer, pending, reemplazo, persistencia
  url + archivo) + tests de integración API
- **T6** — S5: endpoint GET autenticado (owner/admin, FileResponse, 404 si no
  hay comprobante) + tests de integración API
- **T7** — S6: frontend — cliente: botón "Adjuntar comprobante" en el pedido
  (solo transfer + pending); admin: ver comprobante en el detalle del pedido
- **T8** — S7: e2e — R1 happy path (upload → admin lo ve → marca pagado),
  R2 cash 400, R3 pagado 409, R4 pedido ajeno 404, R5 formato inválido 422;
  suite completa verde
- **T9** — S8: ruff/mypy limpios en archivos tocados vs base

## Reglas

- Las de O4: cero lógica de negocio en SQL/transacciones, cero comentarios en
  código nuevo, commit por tarea, `uvx ruff`/`uvx mypy --strict` en archivos
  tocados.
- El nombre en disco es SIEMPRE `{order_id}.{ext}`; el filename original no
  se usa en ninguna ruta.
- Baselines antes de reportar: suite backend completa + e2e (si T8 la toca).

## Log

- **L1** (T1): storage en `MEDIA_ROOT` local (S3/MinIO descartado: el volumen
  es comprobantes de unos cientos de KB a unos MB, cero infra nueva; la
  abstracción de URL deja la puerta abierta). Visualización por ruta
  autenticada en vez de `/media` público (datos bancarios). Pendiente de
  aprobación de Gaspar: (a) storage local, (b) excepción a security #16 de
  "uploads de usuario" para el comprobante con ownership de pedido.
