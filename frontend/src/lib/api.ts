export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const AUTH_SESSION_CLEARED_EVENT = "auth:session-cleared";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly payload: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        return response.ok;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }

  return refreshInFlight;
}

export async function authorizedFetch(
  endpoint: string,
  options: RequestInit = {},
  allowRefresh = true,
): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    credentials: "include",
  });

  if (response.status === 401 && allowRefresh) {
    if (await refreshSession()) {
      return authorizedFetch(endpoint, options, false);
    }
    clearSession();
  }

  return response;
}

function bodyIsFormData(body: unknown): boolean {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  allowRefresh = true
): Promise<T> {
  const response = await authorizedFetch(
    endpoint,
    {
      ...options,
      headers: {
        ...(bodyIsFormData(options.body)
          ? {}
          : { "Content-Type": "application/json" }),
        ...options.headers,
      },
    },
    allowRefresh,
  );

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const candidate =
      (body as { detail?: unknown } | null)?.detail ??
      (body as { message?: unknown } | null)?.message ??
      "An error occurred";
    let message: string;
    if (typeof candidate === "string") {
      message = candidate;
    } else if (Array.isArray(candidate)) {
      const firstMsg = (candidate as Array<{ msg?: unknown }>).map(
        (issue) => issue?.msg
      ).find((m): m is string => typeof m === "string");
      message = firstMsg ?? "Solicitud inválida";
    } else {
      message = JSON.stringify(candidate);
    }
    throw new ApiError(response.status, message, body);
  }

  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

export async function apiFetchText(
  endpoint: string,
  options: RequestInit = {},
  allowRefresh = true,
): Promise<string> {
  const response = await authorizedFetch(endpoint, options, allowRefresh);

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const candidate =
      (body as { detail?: unknown } | null)?.detail ??
      (body as { message?: unknown } | null)?.message ??
      "An error occurred";
    const message =
      typeof candidate === "string"
        ? candidate
        : Array.isArray(candidate)
          ? ((candidate as Array<{ msg?: unknown }>)
              .map((i) => i?.msg)
              .find((m): m is string => typeof m === "string") ?? "Solicitud inválida")
          : JSON.stringify(candidate);
    throw new ApiError(response.status, message, body);
  }

  return response.text();
}

export function clearSession() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}
