import { apiFetch } from "@/lib/api";
import { AuthResponse, LoginRequest } from "@/types/auth";

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
};
