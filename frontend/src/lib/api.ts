import { getCookie, setCookie, removeCookie } from "./cookies";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const ACCESS_TOKEN_COOKIE = "auth_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Evento que emite lib/api al cerrar una sesión (logout o refresh fallido):
// AuthContext lo escucha para limpiar el usuario en memoria y que
// ProtectedRoute redirija. Sin él, la navegación dependía de que algo
// recargara la página.
export const AUTH_SESSION_CLEARED_EVENT = "auth:session-cleared";

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

// Error tipado de respuestas no-ok: conserva status y body para que los
// llamadores distingan casos (p. ej. 409 con `in_use_by`) sin parsear mensajes.
export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
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
    const error = await response.json().catch(() => ({ message: "An error occurred" }));
    throw new ApiError(
      error?.detail || error?.message || "Network error",
      response.status,
      error
    );
  }

  // 204 / body vacío (p. ej. DELETE exitoso): no hay JSON que parsear.
  if (response.status === 204 || response.headers?.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function persistSession(accessToken: string, refreshToken: string) {
  setCookie(ACCESS_TOKEN_COOKIE, accessToken, 1);
  setCookie(REFRESH_TOKEN_COOKIE, refreshToken, 7);
}

export function clearSession() {
  removeCookie(ACCESS_TOKEN_COOKIE);
  removeCookie(REFRESH_TOKEN_COOKIE);
  // Avisa a la capa de auth: borrar los cookies no cambia el estado en memoria,
  // y AuthContext sólo evalúa la sesión al montar. Sin este aviso el usuario
  // queda viendo una UI "autenticada" sin tokens y toda request siguiente falla.
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}
