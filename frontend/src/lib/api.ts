export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// The session lives in HttpOnly cookies set by the backend: JavaScript never
// reads the tokens. Every request sends them with credentials: "include".

// Event emitted by lib/api when a session is closed (logout or failed
// refresh): AuthContext listens for it to clear the in-memory user so
// ProtectedRoute can redirect. Without it, navigation depended on
// something reloading the page.
export const AUTH_SESSION_CLEARED_EVENT = "auth:session-cleared";

/**
 * Typed API error.
 *
 * `status` and `payload` are needed for Phase 4 flows:
 * - DELETE /ingredients/{id} → 409 with `{"impacted_recipes": N}` (UC-05):
 *   the confirmation dialog shows the impact before deleting.
 * - Backend 422: `detail` is an array of issues (FastAPI), not a string.
 */
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

// A single shared refresh promise: avoids N calls to /auth/refresh when
// several requests fail with 401 at the same time (the backend rotates the
// refresh token, so a second concurrent call would look like a replay).
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

/**
 * Runs an authenticated request. On 401 it tries one session refresh and
 * retries; if the refresh fails the session is cleared.
 */
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

/**
 * ¿El body es un FormData (multipart)? En ese caso NO se setea Content-Type:
 * el navegador debe generar el `multipart/form-data; boundary=...` solo.
 * (T-CSV: upload de archivos CSV a POST /imports.)
 */
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
    // FastAPI responde 422 con detail: [{loc, msg, type}] — se toma el primer
    // msg en vez de serializar el cuerpo completo (el usuario no debe ver
    // JSON de validación de Pydantic).
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

  // 204 No Content (p. ej. DELETE /ingredients/{id}): no hay cuerpo que parsear.
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

/**
 * Variante de apiFetch para respuestas que NO son JSON (T-CSV: la plantilla
 * de importación es `text/csv`). Maneja el mismo refresh de sesión y el
 * ApiError, pero devuelve el cuerpo como texto.
 */
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
  // The HttpOnly cookies can only be removed by the backend (/auth/logout).
  // This notifies the auth layer: AuthContext only evaluates the session on
  // mount, so without the event the user keeps seeing an "authenticated" UI
  // while every following request fails.
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}
