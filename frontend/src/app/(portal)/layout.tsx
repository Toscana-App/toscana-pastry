"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { FullPageSkeleton } from "@/components/ui/skeleton";

import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { ConsentBanner } from "@/components/layout/ConsentBanner";
import { PortalFooter } from "@/components/portal/PortalFooter";
import { WhatsAppFloat } from "@/components/portal/WhatsAppFloat";

/**
 * Self-service portal layout (route group `(portal)`, flat URLs:
 * "/" (home), "/my-orders", "/carrito", "/checkout", "/profile").
 *
 * Role gate (p11 RF-P11-01):
 * - no session → /login with `from` to return after login
 * - admin (or foreign role) → /admin (the portal is business/customer only)
 * - business/customer → navbar global (única navegación) + content +
 *   footer de contacto + botón flotante de WhatsApp.
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
    return <FullPageSkeleton />;
  }

  return (
    <>
      <ConsentBanner />
      {children}
      <PortalFooter />
      <WhatsAppFloat />
    </>
  );
}
