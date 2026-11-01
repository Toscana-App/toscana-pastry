/** Pure logic for role → audience mapping and CTA visibility.

Re-exported from this module so pages and tests can import a single
source of truth.
*/

import { Audience } from "@/types/pricing";

/** Role that can access both audiences. */
export const ADMIN_ROLE = "admin";

/** Role that can only access ``revendedores``. */
export const NEGOCIO_ROLE = "negocio";

/** Role that can only access ``consumidor_final``. */
export const CLIENTE_ROLE = "customer";

/**
 * The audience that belongs to a given role — the *default* audience.
 *
 * - ``admin`` → ``null`` (no single default; admin picks)
 * - ``negocio`` → ``"revendedores"``
 * - ``customer`` → ``"consumidor_final"``
 */
export function roleDefaultAudience(role: string): Audience | null {
  const map: Record<string, Audience | null> = {
    [NEGOCIO_ROLE]: "revendedores",
    [CLIENTE_ROLE]: "consumidor_final",
  };
  return map[role] ?? null;
}

/**
 * The list of audiences a role is allowed to access.
 *
 * - ``admin`` → both
 * - ``negocio`` → only ``revendedores``
 * - ``customer`` → only ``consumidor_final``
 */
export function roleAllowedAudiences(role: string): Audience[] {
  if (role === ADMIN_ROLE) {
    return ["revendedores", "consumidor_final"];
  }
  const defaultAud = roleDefaultAudience(role);
  return defaultAud ? [defaultAud] : [];
}

/**
 * Whether the role can switch between audiences (admin-only).
 */
export function canSwitchAudience(role: string): boolean {
  return role === ADMIN_ROLE;
}

/**
 * The audience that should be shown by default for a given role.
 *
 * - ``admin`` → ``"revendedores"`` (the admin picks explicitly)
 * - ``negocio`` → ``"revendedores"``
 * - ``customer`` → ``"consumidor_final"``
 */
export function roleDefaultDisplayAudience(role: string): Audience {
  if (role === ADMIN_ROLE) {
    return "revendedores";
  }
  const defaultAud = roleDefaultAudience(role);
  if (defaultAud) return defaultAud;
  // Fallback for unknown roles — shouldn't happen in practice.
  return "revendedores";
}
