
import { Audience } from "@/types/pricing";

const API_BASE_URL =
  typeof process !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1")
    : "http://localhost:8000/api/v1";


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
