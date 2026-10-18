import { apiFetch } from "@/lib/api";
import { pesosToCents } from "@/lib/format";
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
 * - El formulario trabaja en pesos; el wire habla centavos (Money long) y
 *   porcentajes como string decimal (Pct).
 */
export const settingsService = {
  get(): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE);
  },

  update(values: SettingsFormValues): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE, {
      method: "PUT",
      body: JSON.stringify({
        ...values,
        // Money: el usuario tipea pesos, la API recibe centavos.
        hourly_rate: pesosToCents(values.hourly_rate),
        round_step: pesosToCents(values.round_step),
        // Pct: string decimal (el backend lo parsea a Decimal, sin centavos).
        margin_pct: String(values.margin_pct),
        gas_pct: String(values.gas_pct),
        waste_pct: String(values.waste_pct),
        urgent_surcharge_pct: String(values.urgent_surcharge_pct),
      }),
    });
  },
};
