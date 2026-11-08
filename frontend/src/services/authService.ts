import { apiFetch, persistSession, clearSession } from "@/lib/api";
import { AuthResponse, UserInfo } from "@/types/auth";

export const authService = {
  async loginWithGoogle(googleId: string): Promise<AuthResponse> {
    const data = await apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ google_id: googleId }),
    });
    persistSession(data.access_token, data.refresh_token);
    return data;
  },

  async getUser(): Promise<UserInfo> {
    return apiFetch<UserInfo>("/auth/me");
  },

  logout() {
    clearSession();
  },
};
