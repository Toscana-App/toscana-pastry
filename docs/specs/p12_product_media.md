# P12 — Medios del producto: imagen (upload multipart)

Módulo: `web/modules/products` + `web/components/catalog` · Rutas: `/productos/{id}` (admin), `/(portal)` (tienda) · Fase: **5 (P12)**

## Contexto
Cada producto de la tienda (budines, tortas, pasta frola, …) lleva una imagen. El envío es **multipart/form-data** hacia FastAPI (`UploadFile = File(...)`), admin only. La tienda del portal (P11, `odd/tasks/products-storefront.md`) vende **productos** con precio por audiencia; la imagen es parte del contrato de catálogo (`image_url`) y del detalle de tienda (P4 RF-P4-11).

## User story
> Como **administradora**, quiero **subir la foto de cada producto**, para **que el cliente la vea en la tienda antes de pedir**.

**Criterios de aceptación**
- [ ] Subo una imagen (JPEG/PNG/WebP ≤ 5 MB) desde el detalle de producto; veo preview, estado de carga y error con motivo.
- [ ] Al reemplazar, la imagen anterior desaparece de la tienda y del disco.
- [ ] Puedo quitar la imagen (DELETE → 204); `image_url` queda `null`.
- [ ] Un token de `cliente`/`negocio` no puede subir ni borrar (403).
- [ ] Tipo o tamaño inválido → 422 con motivo; el archivo nunca toca el disco.

## Requerimientos funcionales
- **RF-P12-01**: `POST /api/v1/products/{id}/image` — `multipart/form-data`, campo `file`, **admin only** (403 para `negocio`/`cliente`; 401 sin sesión). Validaciones, en este orden: producto existe (404) → tipo real por **magic bytes** (JPEG/PNG/WebP; el `Content-Type` enviado por el cliente no confunde la validación) → tamaño ≤ 5 MB (422 `image_too_large`) → dimensiones mínimas 200×200 px (422 `image_too_small`). Reemplazo: borra el archivo anterior y guarda el nuevo (una imagen por producto). (UC upload)
- **RF-P12-02**: `DELETE /api/v1/products/{id}/image` — **admin only** → 204; borra el archivo y limpia `image_url` a `null`. Producto sin imagen → 404.
- **RF-P12-03**: Almacenamiento: `backend/media/products/<product_id>.<ext>` (ext según el tipo real detectado: `jpg|png|webp`). La DB guarda la ruta relativa en `products.image_url` (string | null), **nunca** el binario. El directorio vive fuera del bundle y queda gitignoreado (`.gitkeep` + `backend/media/products/*` en `.gitignore`).
- **RF-P12-04**: Servicio: `StaticFiles` montado en `/media` en `main.py`. Las respuestas de producto (list, detail, catálogo de audiencia, detalle de tienda) incluyen `image_url` como ruta relativa al origin (`/media/products/<id>.<ext>`); sin imagen → `null`.
- **RF-P12-05**: `POST|PATCH /products` **no** acepta imagen en el body JSON (multipart no compite con `extra="forbid"`): la imagen siempre va por su endpoint propio.
- **RF-P12-06**: Límite de tamaño en el request: si el upload excede 5 MB + margen, el request se corta con 413 antes de tocar el disco (slowapi/edge o `Request` size-check en la dependencia).

## Requerimientos no funcionales
- **RNF-P12-01**: Cero ejecución: `/media` solo sirve archivos estáticos (sin listing de directorio, sin intérprete); `nosniff` del edge aplica (security #16/#18). La imagen no es dato sensible: `/media` es público (igual que el catálogo), sin auth.
- **RNF-P12-02**: El nombre de archivo nunca usa el nombre subido por el cliente (solo `<product_id>.<ext>`): sin colisiones ni path traversal.
- **RNF-P12-03**: En prod, `/media` requiere **volumen persistente** en el contenedor del backend (documentar en el PR de deploy); al reemplazar se borra el archivo viejo (sin crecimiento sin límite).

## API (resumen — detalle en `api_endpoints.md` §FASE 1)
| Método | Ruta | Respuesta | Códigos |
|---|---|---|---|
| POST | `/api/v1/products/{id}/image` | `{image_url}` | 201 / 401 / 403 / 404 / 422 / 413 |
| DELETE | `/api/v1/products/{id}/image` | — | 204 / 401 / 403 / 404 |

## Tareas
- [ ] Backend: `image_url` en `ProductORM` (migración `0009` junto con `available`); validación de magic bytes (lectura de los primeros bytes — sin dependencia extra); endpoints admin; mount `StaticFiles` en `main.py`; `backend/media/.gitkeep` + `.gitignore`.
- [ ] Frontend: uploader en `modules/products` (FormData vía `apiFetch` — ya soporta FormData sin `Content-Type` explícito, `src/lib/api.ts`; preview local, reemplazo, borrado con confirmación); `image_url` en `types.ts`; card del portal con imagen (o placeholder).
- [ ] Tests: 201 + archivo escrito en disco y `image_url` persistida; 422 tipo inválido (GIF y binario con `Content-Type` falsificado); 422 > 5 MB; 422 dimensiones < 200×200; 403 con token de `cliente`; reemplazo borra el archivo anterior; DELETE limpia `image_url` y el archivo.

## UI (Chakra v3 + DESIGN.md)
- Zona de imagen sobre los tabs: frame 4:3, placeholder "Sin imagen", overlay con acciones "Cambiar" / "Quitar" (quitar con diálogo de confirmación, es irreversible); input `file` oculto con `accept="image/jpeg,image/png,image/webp"` y `aria-label`.
- Estados: spinner de carga sobre el frame; error inline con motivo ("Solo JPEG, PNG o WebP · máx. 5 MB") + CTA "Reintentar"; éxito: preview + badge "Actualizada".
- En la tienda: `next/image` con `aspectRatio 4/3`, `loading="lazy"`, placeholder de marca si `image_url` es null.
