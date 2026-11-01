/** Service functions for the dual-pricing feature (T5).

Reuses ``apiFetch`` for JSON endpoints and a lightweight blob helper
for the CSV/PDF pricelist downloads.
*/

import { Audience } from "@/types/pricing";

const API_BASE_URL =
  typeof process !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1")
    : "http://localhost:8000/api/v1";

/* ------------------------------------------------------------------ */
/*  Blob helpers for CSV / PDF exports                                 */
/* ------------------------------------------------------------------ */

/**
 * Fetch an endpoint that returns a binary blob (CSV / PDF).
 *
 * Reuses the same token / refresh logic as ``apiFetch`` so that
 * 401 responses trigger a refresh before the blob request.
 */
async function apiFetchBlob(endpoint: string): Promise<Response> {
  const token =
    typeof document !== "undefined"
      ? document.cookie
          .split(";")
          .map((c) => c.trim())
          .find((c) => c.startsWith("auth_token="))
          ?.split("=")[1]
      : undefined;

  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: "An error occurred",
    }));
    throw new Error(
      error.detail || error.message || "Network error"
    );
  }

  return response;
}

/* ------------------------------------------------------------------ */
/*  Pricelist exports                                                  */
/* ------------------------------------------------------------------ */

/**
 * Download a CSV pricelist for the given audience.
 *
 * Extracts the filename from ``Content-Disposition`` or falls back to
 * ``pricelist_${audience}.csv``.
 */
export async function downloadPricelistCSV(audience: Audience): Promise<void> {
  const response = await apiFetchBlob(
    `/products/pricelist/csv?audience=${audience}`
  );

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/i);
  const filename = filenameMatch?.[1] ?? `pricelist_${audience}.csv`;

  const blob = await response.blob();
  triggerDownload(blob, filename);
}

/**
 * Download a PDF pricelist for the given audience.
 *
 * Extracts the filename from ``Content-Disposition`` or falls back to
 * ``pricelist_${audience}.pdf``.
 */
export async function downloadPricelistPDF(audience: Audience): Promise<void> {
  const response = await apiFetchBlob(
    `/products/pricelist/pdf?audience=${audience}`
  );

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/i);
  const filename = filenameMatch?.[1] ?? `pricelist_${audience}.pdf`;

  const blob = await response.blob();
  triggerDownload(blob, filename);
}

/**
 * Trigger a browser download for a Blob.
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
