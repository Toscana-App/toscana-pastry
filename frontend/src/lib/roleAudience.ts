
import { Audience } from "@/types/pricing";

export const ADMIN_ROLE = "admin";

export const NEGOCIO_ROLE = "negocio";

export const CLIENTE_ROLE = "customer";

export function roleDefaultAudience(role: string): Audience | null {
  const map: Record<string, Audience | null> = {
    [NEGOCIO_ROLE]: "revendedores",
    [CLIENTE_ROLE]: "consumidor_final",
  };
  return map[role] ?? null;
}

export function roleAllowedAudiences(role: string): Audience[] {
  if (role === ADMIN_ROLE) {
    return ["revendedores", "consumidor_final"];
  }
  const defaultAud = roleDefaultAudience(role);
  return defaultAud ? [defaultAud] : [];
}

export function canSwitchAudience(role: string): boolean {
  return role === ADMIN_ROLE;
}

export function roleDefaultDisplayAudience(role: string): Audience {
  if (role === ADMIN_ROLE) {
    return "revendedores";
  }
  const defaultAud = roleDefaultAudience(role);
  if (defaultAud) return defaultAud;
  return "revendedores";
}
