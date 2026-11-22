"use client"

import React, { createContext, useContext, useState, useEffect } from "react";
import { authService } from "@/services/authService";
import { AUTH_SESSION_CLEARED_EVENT } from "@/lib/api";
import { User } from "@/types/auth";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  logout: () => void;
  /** Re-fetch /auth/me; resolve with the fresh user (null when unauthenticated). */
  refresh: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const isAuthenticated = !!user;

  const refresh = React.useCallback(async (): Promise<User | null> => {
    try {
      const response = await authService.getUser();
      const next: User = {
        id: response.user_id,
        email: response.email,
        role: response.role,
        googleId: response.google_id,
      };
      setUser(next);
      return next;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      await refresh();
      if (!cancelled) setLoading(false);
    }

    checkAuth();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    const onSessionCleared = () => setUser(null);
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
    return () =>
      window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
  }, []);

  const logout = () => {
    setUser(null);
    // GIS: stop auto-selecting the account for subsequent sign-ins (RNF-P1-08
    // hygiene). Guarded: the script may not have loaded (no clientId configured).
    window.google?.accounts?.id?.disableAutoSelect?.();
    void authService.logout();
  };

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated, loading, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
