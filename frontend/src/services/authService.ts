import { apiFetch, clearSession } from "@/lib/api";
import { GoogleSignInResponse, UserInfo } from "@/types/auth";

export const authService = {
  
  async fetchGoogleNonce(): Promise<{ nonce: string }> {
    return apiFetch<{ nonce: string }>("/auth/google/nonce", undefined, false);
  },

  
  async loginWithGoogleCredential(
    credential: string,
  ): Promise<GoogleSignInResponse> {
    return apiFetch<GoogleSignInResponse>(
      "/auth/google/signin",
      { method: "POST", body: JSON.stringify({ credential }) },
      false,
    );
  },

  async getUser(): Promise<UserInfo> {
    return apiFetch<UserInfo>("/auth/me");
  },

  async logout(): Promise<void> {
    try {
      await apiFetch<void>("/auth/logout", { method: "POST" }, false);
    } finally {
      clearSession();
    }
  },
};
