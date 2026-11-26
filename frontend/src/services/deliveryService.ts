import { API_BASE_URL, ApiError, apiFetch, authorizedFetch } from "@/lib/api";
import type { DeliveryLink, PublicDelivery } from "@/types/delivery";

export async function fetchDeliveryLink(orderId: string): Promise<DeliveryLink> {
  return apiFetch<DeliveryLink>(`/orders/${orderId}/delivery-link`);
}

export async function fetchDeliveryQrObjectUrl(orderId: string): Promise<string> {
  const response = await authorizedFetch(`/orders/${orderId}/delivery-qr.svg`);
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      (body as { detail?: unknown } | null)?.detail ?? "No se pudo generar el QR";
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : "No se pudo generar el QR",
      body,
    );
  }
  return URL.createObjectURL(await response.blob());
}

export async function fetchPublicDelivery(
  token: string,
  signal?: AbortSignal,
): Promise<PublicDelivery> {
  const response = await fetch(
    `${API_BASE_URL}/public/orders/${encodeURIComponent(token)}`,
    { credentials: "omit", cache: "no-store", signal },
  );
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      (body as { detail?: unknown } | null)?.detail ?? "Enlace no disponible";
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : "Enlace no disponible",
      body,
    );
  }
  return (await response.json()) as PublicDelivery;
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
