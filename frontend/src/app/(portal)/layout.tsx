"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Center, Spinner } from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { PortalShellHeader } from "@/components/layout/PortalShellHeader";

/**
 * Layout del portal self-service (grupo de rutas `(portal)`, URLs planas:
 * "/" (Inicio), "/mis-pedidos", "/carrito", "/checkout", "/profile").
 *
 * Gate por rol (p11 RF-P11-01):
 * - sin sesión → /login con `from` para volver después del login
 * - admin (o rol ajeno) → /admin (el portal es solo negocio/cliente)
 * - negocio/cliente → shell (tab bar + CTA) + contenido
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
      <PortalShellHeader />
      {children}
    </>
  );
}
