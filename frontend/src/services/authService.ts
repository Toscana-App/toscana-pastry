import { apiFetch } from "@/lib/api";
import { AuthResponse, LoginRequest, UserInfo } from "@/types/auth";
import { removeCookie } from "@/lib/cookies";

export const authService = {
  async loginWithMagicLink(email: string): Promise<AuthResponse> {
    return apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async loginWithGoogle(googleId: string): Promise<AuthResponse> {
    return apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ google_id: googleId }),
    });
  },

  async getUser(): Promise<UserInfo> {
    return apiFetch<UserInfo>("/auth/me");
  },

  logout() {
    removeCookie("auth_token");
    window.location.href = "/login";
  }
};
