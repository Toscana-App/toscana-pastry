import { getCookie, setCookie, removeCookie } from "./cookies";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const ACCESS_TOKEN_COOKIE = "auth_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

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
    const error = await response.json().catch(() => ({ message: "An error occurred" }));
    throw new Error(error.detail || error.message || "Network error");
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
}
