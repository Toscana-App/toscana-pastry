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
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const isAuthenticated = !!user;

  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      try {
        const response = await authService.getUser();
        if (cancelled) return;
        setUser({
          id: response.user_id,
          email: response.email,
          role: response.role,
          googleId: response.google_id,
        });
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    checkAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  // La sesión puede cerrarse desde afuera del contexto (refresh fallido en
  // lib/api): el evento limpia el usuario y ProtectedRoute redirige a /login.
  useEffect(() => {
    const onSessionCleared = () => setUser(null);
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
    return () =>
      window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, onSessionCleared);
  }, []);

  const logout = () => {
    setUser(null);
    authService.logout();
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, loading, logout }}>
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
