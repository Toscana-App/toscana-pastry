import { apiFetch, clearSession } from "@/lib/api";
import { AuthResponse, UserInfo } from "@/types/auth";

export const authService = {
  // The backend sets the session cookies (HttpOnly) on the response.
  loginWithGoogle(googleId: string): Promise<AuthResponse> {
    return apiFetch<AuthResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ google_id: googleId }) },
      false,
    );
  },

  async getUser(): Promise<UserInfo> {
    return apiFetch<UserInfo>("/auth/me");
  },

  /** Revokes the session server-side and clears the cookies. */
  async logout(): Promise<void> {
    try {
      await apiFetch<void>("/auth/logout", { method: "POST" }, false);
    } finally {
      clearSession();
    }
  },
};
