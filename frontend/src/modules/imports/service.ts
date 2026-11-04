import { apiFetch, apiFetchText } from "@/lib/api";
import type {
  ConfirmResponse,
  DiscardResponse,
  ImportEntity,
  ImportRowOut,
  ImportRowsResponse,
  ImportUploadResponse,
  ImportRowStatus,
} from "./types";

const BASE = "/imports";

/**
 * Service tipado de la importación CSV (T-CSV-8): espejo 1:1 de
 * `backend/src/api/v1/imports/router.py`.
 *
 * - La plantilla se devuelve como TEXTO (text/csv) → apiFetchText.
 * - El upload es multipart (FormData) → apiFetch detecta el FormData y no
 *   setea Content-Type JSON (el navegador arma el boundary).
 * - DELETE devuelve 204 → apiFetch resuelve undefined.
 */
export const importsService = {
  /** GET /imports/template?entity= — plantilla CSV de la entidad (texto). */
  template(entity: ImportEntity): Promise<string> {
    return apiFetchText(`${BASE}/template?entity=${entity}`);
  },

  /** POST /imports — upload multipart (file + entity). 201 con import_id. */
  upload(file: File, entity: ImportEntity): Promise<ImportUploadResponse> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("entity", entity);
    return apiFetch<ImportUploadResponse>(BASE, {
      method: "POST",
      body: fd,
    });
  },

  /** GET /imports/{id}/rows — preview paginado, opcional filtro por estado. */
  rows(
    id: string,
    page = 1,
    pageSize = 100,
    status?: ImportRowStatus,
  ): Promise<ImportRowsResponse> {
    const q = new URLSearchParams();
    q.set("page", String(page));
    q.set("page_size", String(pageSize));
    if (status) q.set("status", status);
    return apiFetch<ImportRowsResponse>(`${BASE}/${id}/rows?${q.toString()}`);
  },

  /** POST /imports/{id}/confirm — transacción única; duplicados → skipped. */
  confirm(id: string): Promise<ConfirmResponse> {
    return apiFetch<ConfirmResponse>(`${BASE}/${id}/confirm`, {
      method: "POST",
    });
  },

  /** DELETE /imports/{id} — descarta y borra el staging. 204. */
  discard(id: string): Promise<DiscardResponse> {
    return apiFetch<DiscardResponse>(`${BASE}/${id}`, { method: "DELETE" });
  },
};

/** Re-export para tipar filas sueltas en el dialog. */
export type { ImportRowOut };
