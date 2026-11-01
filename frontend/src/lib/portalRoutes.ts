/** Pure logic for the self-service portal shell (F1 — p11 RF-P11-01).

No React here: pages, the navbar and the login form all resolve portal
routing through these helpers so the rules have a single home.
*/

import { UserRole } from "@/types/auth";

/** Roles that live in the self-service portal (RF-P11-01). */
export const PORTAL_ROLES: readonly UserRole[] = ["negocio", "customer"];

/** Whether the role belongs to the portal (negocio/cliente only). */
export function isPortalRole(role: UserRole | undefined | null): boolean {
  return role !== undefined && role !== null && PORTAL_ROLES.includes(role);
}

/** One entry of the portal tab bar. Order matters. */
export interface PortalTab {
  label: string;
  href: string;
}

/**
 * Tab bar of the portal shell (p11 "UI — Shell del portal"):
 * Inicio · Mis pedidos · Carrito · Cuenta.
 */
export const PORTAL_TABS: readonly PortalTab[] = [
  { label: "Inicio", href: "/" },
  { label: "Mis pedidos", href: "/my-orders" },
  { label: "Carrito", href: "/carrito" },
  { label: "Cuenta", href: "/profile" },
];

/** CTA "Nuevo pedido" of the portal shell → 5-step checkout (F2). */
export const NEW_ORDER_HREF = "/checkout";

/**
 * Sanitizes the `from` redirect target after login.
 *
 * Only relative internal paths are accepted (start with `/` but not
 * `//`, so scheme-relative URLs are rejected). Anything else falls back.
 */
export function safeRedirectTarget(
  raw: string | null | undefined,
  fallback: string,
): string {
  if (raw !== null && raw !== undefined && raw.startsWith("/") && !raw.startsWith("//")) {
    return raw;
  }
  return fallback;
}

/**
 * Default landing after login when no `from` target is available.
 *
 * - admin → `/admin` (the portal is not for admin, RF-P11-01)
 * - portal roles → `/products` (their audience price list, T5)
 */
export function postLoginTarget(role: UserRole | undefined | null): string {
  if (role === "admin") return "/admin";
  return "/products";
}
