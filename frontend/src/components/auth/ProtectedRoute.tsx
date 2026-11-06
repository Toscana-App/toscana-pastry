"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { FullPageSkeleton } from "@/components/ui/skeleton";

import { useAuth } from "@/contexts/AuthContext";
import type { UserRole } from "@/types/auth";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole;
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { user, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  const lacksRole = Boolean(requiredRole) && user?.role !== requiredRole;

  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      router.replace("/login");
    } else if (lacksRole) {
      router.replace("/unauthorized");
    }
  }, [isAuthenticated, loading, lacksRole, router]);

  if (loading || !isAuthenticated || lacksRole) {
    return <FullPageSkeleton />;
  }

  return <>{children}</>;
}
