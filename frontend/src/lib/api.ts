import { getCookie, setCookie, removeCookie } from "./cookies";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const ACCESS_TOKEN_COOKIE = "auth_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Event emitted by lib/api when a session is closed (logout or failed
// refresh): AuthContext listens for it to clear the in-memory user so
// ProtectedRoute can redirect. Without it, navigation depended on
// something reloading the page.
export const AUTH_SESSION_CLEARED_EVENT = "auth:session-cleared";

/**
 * Error tipado de la API.
 *
 * `status` y `payload` son necesarios para los flujos de la Fase 4:
 * - DELETE /ingredients/{id} → 409 con `{"impacted_recipes": N}` (UC-05): el
 *   diálogo de confirmación muestra el impacto antes de eliminar.
 * - 422 del backend: `detail` es un array de issues (FastAPI), no un string.
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

// Una sola promesa de refresh compartida: evita N llamadas a /auth/refresh
// cuando varias requests fallan con 401 al mismo tiempo.
let refreshInFlight: Promise<string | null> | null = null;

async function requestNewAccessToken(): Promise<string | null> {
  const refreshToken = getCookie(REFRESH_TOKEN_COOKIE);
  if (!refreshToken) return null;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) return null;
        const data = (await response.json()) as { access_token: string };
        setCookie(ACCESS_TOKEN_COOKIE, data.access_token, 1);
        return data.access_token;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }

  return refreshInFlight;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  allowRefresh = true
): Promise<T> {
  const token = getCookie(ACCESS_TOKEN_COOKIE);

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401 && allowRefresh && getCookie(REFRESH_TOKEN_COOKIE)) {
    const newToken = await requestNewAccessToken();
    if (newToken) {
      return apiFetch<T>(endpoint, options, false);
    }
    clearSession();
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const candidate =
      (body as { detail?: unknown } | null)?.detail ??
      (body as { message?: unknown } | null)?.message ??
      "An error occurred";
    // FastAPI responde 422 con detail: [{loc, msg, type}] — se toma el primer
    // msg; el cuerpo completo queda en `payload`.
    const message =
      typeof candidate === "string"
        ? candidate
        : Array.isArray(candidate) &&
            typeof (candidate[0] as { msg?: unknown } | undefined)?.msg === "string"
          ? (candidate[0] as { msg: string }).msg
          : "An error occurred";
    throw new ApiError(response.status, message, body);
  }

  // 204 No Content (p. ej. DELETE /ingredients/{id}): no hay cuerpo que parsear.
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

export function persistSession(accessToken: string, refreshToken: string) {
  setCookie(ACCESS_TOKEN_COOKIE, accessToken, 1);
  setCookie(REFRESH_TOKEN_COOKIE, refreshToken, 7);
}

export function clearSession() {
  removeCookie(ACCESS_TOKEN_COOKIE);
  removeCookie(REFRESH_TOKEN_COOKIE);
  // Notifies the auth layer: removing the cookies does not change the
  // in-memory state, and AuthContext only evaluates the session on mount.
  // Without this notification the user keeps seeing an "authenticated" UI
  // with no tokens and every following request fails.
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}
