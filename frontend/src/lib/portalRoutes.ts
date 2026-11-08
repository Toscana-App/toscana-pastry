
import { UserRole } from "@/types/auth";

export const PORTAL_ROLES: readonly UserRole[] = ["negocio", "customer"];

export function isPortalRole(role: UserRole | undefined | null): boolean {
  return role !== undefined && role !== null && PORTAL_ROLES.includes(role);
}

export interface PortalTab {
  label: string;
  href: string;
}

export const PORTAL_TABS: readonly PortalTab[] = [
  { label: "Inicio", href: "/" },
  { label: "Mis pedidos", href: "/my-orders" },
  { label: "Carrito", href: "/carrito" },
  { label: "Cuenta", href: "/profile" },
];

export const NEW_ORDER_HREF = "/checkout";

export function safeRedirectTarget(
  raw: string | null | undefined,
  fallback: string,
): string {
  if (raw !== null && raw !== undefined && raw.startsWith("/") && !raw.startsWith("//")) {
    return raw;
  }
  return fallback;
}

export function postLoginTarget(role: UserRole | undefined | null): string {
  if (role === "admin") return "/admin";
  return "/products";
}
