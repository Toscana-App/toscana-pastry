import { getCookie } from "./cookies";
import { ACCESS_TOKEN_COOKIE } from "./api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Helper compartido de descargas binarias (Fase 5, UC-08): mismo patrón
 * fetch→blob→download que `pricingService` para los exports CSV/PDF de
 * pedidos y presupuestos.
 *
 * - El token de acceso viaja en el header Authorization (los exports son
 *   admin y requieren autenticación, como el resto de la API).
 * - El filename sale del header Content-Disposition del backend; si no
 *   viene, se usa el nombre de respaldo que pasa el caller.
 */

/** Fetch de un endpoint binario (CSV/PDF) con token; lanza si no es OK. */
export async function fetchBlob(endpoint: string): Promise<Response> {
  const token = getCookie(ACCESS_TOKEN_COOKIE);

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const detail =
      (error as { detail?: unknown } | null)?.detail ??
      (error as { message?: unknown } | null)?.message ??
      "Ocurrió un error al generar el archivo";
    throw new Error(typeof detail === "string" ? detail : String(detail));
  }

  return response;
}

/** Dispara la descarga del blob en el navegador (object URL + anchor). */
export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Descarga completa de un endpoint binario: fetch con token, filename del
 * Content-Disposition (con respaldo) y disparo de la descarga.
 *
 * @param endpoint Ruta relativa a /api/v1 (con querystring ya armado).
 * @param fallbackFilename Nombre del archivo si no viene Content-Disposition.
 */
export async function downloadEndpoint(
  endpoint: string,
  fallbackFilename: string,
): Promise<void> {
  const response = await fetchBlob(endpoint);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/i);
  const filename = filenameMatch?.[1] ?? fallbackFilename;

  const blob = await response.blob();
  triggerDownload(blob, filename);
}
