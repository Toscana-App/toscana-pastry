"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Center, Spinner } from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { ConsentBanner } from "@/components/layout/ConsentBanner";
import { PortalShellHeader } from "@/components/layout/PortalShellHeader";

/**
 * Self-service portal layout (route group `(portal)`, flat URLs:
 * "/" (home), "/my-orders", "/carrito", "/checkout", "/profile").
 *
 * Role gate (p11 RF-P11-01):
 * - no session → /login with `from` to return after login
 * - admin (or foreign role) → /admin (the portal is business/customer only)
 * - business/customer → shell (tab bar + CTA) + content
 */
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    } else if (!isPortalRole(user?.role)) {
      router.replace("/admin");
    }
  }, [loading, isAuthenticated, user?.role, router, pathname]);

  if (loading || !isAuthenticated || !isPortalRole(user?.role)) {
    return (
      <Center minH="60dvh">
        <Spinner size="xl" />
      </Center>
    );
  }

  return (
    <>
      <ConsentBanner />
      <PortalShellHeader />
      {children}
    </>
  );
}
