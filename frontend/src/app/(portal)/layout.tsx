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
 * "/my-orders", "/carrito", "/checkout", "/profile").
 *
 * The home page (`/`) is public (app/page.tsx) and does NOT use this layout.
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

  const isProfilePage = pathname === "/profile";
  const canAccess = isPortalRole(user?.role) || (isProfilePage && user?.role === "admin");

  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    } else if (!canAccess) {
      router.replace("/admin");
    }
  }, [loading, isAuthenticated, canAccess, router, pathname]);

  if (loading || !isAuthenticated || !canAccess) {
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
