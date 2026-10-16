import { apiFetch } from "@/lib/api";
import type { BusinessSettings, SettingsFormValues } from "./types";

// Path del contrato (p05 / api_endpoints.md): la configuración del negocio vive
// bajo /tenant/settings, no como recurso suelto.
const BASE = "/tenant/settings";

/**
 * Servicio de configuración del negocio (Fase 4, WU7).
 *
 * - GET: cualquier usuario autenticado (el formulario de admin la lee).
 * - PUT: reemplaza la configuración completa (12 campos, todos obligatorios);
 *   requiere rol admin — un customer recibe 403.
 */
export const settingsService = {
  get(): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE);
  },

  update(values: SettingsFormValues): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE, {
      method: "PUT",
      body: JSON.stringify(values),
    });
  },
};
