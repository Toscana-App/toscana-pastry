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

export const importsService = {
  template(entity: ImportEntity): Promise<string> {
    return apiFetchText(`${BASE}/template?entity=${entity}`);
  },

  upload(file: File, entity: ImportEntity): Promise<ImportUploadResponse> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("entity", entity);
    return apiFetch<ImportUploadResponse>(BASE, {
      method: "POST",
      body: fd,
    });
  },

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

  confirm(id: string): Promise<ConfirmResponse> {
    return apiFetch<ConfirmResponse>(`${BASE}/${id}/confirm`, {
      method: "POST",
    });
  },

  discard(id: string): Promise<DiscardResponse> {
    return apiFetch<DiscardResponse>(`${BASE}/${id}`, { method: "DELETE" });
  },
};

export type { ImportRowOut };
