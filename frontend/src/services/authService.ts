import { apiFetch, clearSession } from "@/lib/api";
import { GoogleSignInResponse, UserInfo } from "@/types/auth";

export const authService = {
  /** GET /auth/google/nonce: server-issued nonce bound to a pre-auth cookie. */
  async fetchGoogleNonce(): Promise<{ nonce: string }> {
    return apiFetch<{ nonce: string }>("/auth/google/nonce", undefined, false);
  },

  /**
   * POST /auth/google/signin with the GIS ID token. On 409 the backend
   * returns detail { message, state } ("no_account" | "link_pending"); the
   * caller must branch on state (RNF-P1-07).
   */
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
