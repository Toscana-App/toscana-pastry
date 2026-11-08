import { getCookie, setCookie, removeCookie } from "./cookies";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const ACCESS_TOKEN_COOKIE = "auth_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

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

function bodyIsFormData(body: unknown): boolean {
  return typeof FormData !== "undefined" && body instanceof FormData;
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
      ...(bodyIsFormData(options.body)
        ? {}
        : { "Content-Type": "application/json" }),
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
  const token = getCookie(ACCESS_TOKEN_COOKIE);

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401 && allowRefresh && getCookie(REFRESH_TOKEN_COOKIE)) {
    const newToken = await requestNewAccessToken();
    if (newToken) {
      return apiFetchText(endpoint, options, false);
    }
    clearSession();
  }

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

export function persistSession(accessToken: string, refreshToken: string) {
  setCookie(ACCESS_TOKEN_COOKIE, accessToken, 1);
  setCookie(REFRESH_TOKEN_COOKIE, refreshToken, 7);
}

export function clearSession() {
  removeCookie(ACCESS_TOKEN_COOKIE);
  removeCookie(REFRESH_TOKEN_COOKIE);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}
