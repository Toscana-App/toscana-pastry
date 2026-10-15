# P9 — Exportación PDF
Módulo: `web/modules/pdf` · Ruta: `/presupuestos/{id}/pdf` (endpoint + modal de preview) · Fase: **3**

## Contexto
El cliente final recibe un documento profesional con el branding de la repostera (screenshot verificado: "Presupuesto" con logo, fecha "jueves, 06 de agosto de 2026", cliente, fecha de entrega, ítems, cargo extra, Total).
⚠️ **Hallazgo**: el logo original dice "Dúlces" (typo). Aquí el branding viene de la config del tenant (nombre del negocio + logo opcional), verificado antes de publicarse.

## User story
> Como **repostera**, quiero **que mi presupuesto se exporte a PDF con mi nombre/marca**, para **que el cliente reciba un documento profesional, no una captura de la app**.

**Criterios de aceptación**
- [ ] Toco "Descargar PDF" y en < 2 s tengo el archivo `presupuesto_00023.pdf`.
- [ ] El PDF muestra: nombre del negocio, fecha, datos del cliente, fecha de entrega, ítems con precios, totales (costos ocultos al cliente) y mi pie de página.
- [ ] **El costo y la ganancia NO aparecen en el PDF** (es un documento del cliente).
- [ ] Si edito el presupuesto, el PDF se regenera; el PDF enviado queda versionado.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Descargar PDF | Repostera | CTA en resumen → preview → descargar |
| UC-02 Compartir link del PDF | Repostera | CTA → link público temporal (72 h) |
| UC-03 Regenerar tras edición | Repostera | Editar → PDF nuevo (versión) |

## Requerimientos funcionales
- **RF-P9-01**: Generación server-side (ReportLab/WeasyPrint) desde snapshot del presupuesto: branding (nombre + logo opcional + colores), fecha en es-AR, cliente, entrega, ítems, subtotal, total, notas, footer. (UC-01)
- **RF-P9-02**: El PDF **excluye** datos internos (costos, ganancia, margen). (UC-01)
- **RF-P9-03**: Cache: el PDF se genera una vez por versión; `GET /budgets/{id}/pdf` sirve el archivo; `ETag` por hash de contenido. (UC-03)
- **RF-P9-04**: Link temporal público (token firmado, TTL 72 h) para compartir sin app. (UC-02)
- **RF-P9-05**: Preview en modal antes de descargar (render del PDF como imagen o iframe). (UC-01)
- **RF-P9-06**: Footer configurable por tenant (texto de agradecimiento + contacto). (UC-01)
- **RF-P9-07**: Logo opcional del tenant (upload validado: PNG/JPG/WebP ≤ 500 KB, ratio 4:1; si no hay logo → solo nombre del negocio). (UC-01)

## Requerimientos no funcionales
- **RNF-P9-01**: Generación < 2 s para 30 ítems; < 5 s para 100.
- **RNF-P9-02**: Tamaño del PDF < 200 KB (logo embebido optimizado).
- **RNF-P9-03**: Texto seleccionable/copy-able en el PDF (no imagen plana) — accesible para el cliente.
- **RNF-P9-04**: Seguridad: el endpoint requiere sesión del owner; el link público expira; sin PII en logs (solo budget_id).
- **RNF-P9-05**: Filename legible: `presupuesto_{tenant}_{secuencia}_{cliente_slug}.pdf`.

## Tareas
- [ ] API: `GET /budgets/{id}/pdf` (genera si no existe en versión), `POST /budgets/{id}/pdf/share` (link temporal)
- [ ] Domain: render del documento (plantilla) — puramente a partir del snapshot
- [ ] Data: tabla `documents` (budget_id, version, file, hash, created_at) en storage local/S3-compat
- [ ] API: upload de logo por tenant (validación de tamaño/formato)
- [ ] Web: modal de preview + botón de descarga + botón de compartir (copia link)
- [ ] Web: sección de branding en Configuración (logo + footer)
- [ ] Tests: pytest de contenido del PDF (parseo del texto: sin "ganancia", con cliente y total), expiración de link, ETag
- [ ] GA4: `pdf_downloaded`, `pdf_shared`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Dialog.Root` (preview), `Button`, `Toast`, `Progress` (generación), `Spinner`.
- El documento en sí sigue DESIGN.md tipográfico (Montserrat) con jerarquía: header de marca → datos → tabla → totales → footer.
- CTA único del modal: **Descargar**.
