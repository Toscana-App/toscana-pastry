"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { FullPageSkeleton } from "@/components/ui/skeleton";

import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { ConsentBanner } from "@/components/layout/ConsentBanner";
import { PortalFooter } from "@/components/portal/PortalFooter";
import { WhatsAppFloat } from "@/components/portal/WhatsAppFloat";

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
