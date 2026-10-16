/**
 * Tipos del módulo de configuración del negocio (Fase 4, WU7).
 *
 * Espejo 1:1 de `backend/src/api/v1/settings/schemas.py`.
 * - Path real: /api/v1/tenant/settings (los costos son configuración del
 *   negocio, no un recurso suelto).
 * - Money viaja como string en la response; el PUT acepta number.
 * - Leer: cualquier usuario autenticado. Escribir: solo admin (403 si no).
 * - RF-P5-06: cada porcentaje exige su toggle encendido (gas_pct = 0 si
 *   include_gas es false; idem merma).
 */

export const DIFFICULTIES = ["simple", "intermedio", "complejo"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

/** Respuesta del backend (Money como string). */
export interface BusinessSettings {
  hourly_rate: string;
  margin_pct: string;
  round_step: string;
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: string;
  include_waste: boolean;
  waste_pct: string;
  urgent_surcharge_pct: string;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: Difficulty;
}

/** Valores del formulario: mismos campos, numéricos (inputs con valueAsNumber). */
export interface SettingsFormValues {
  hourly_rate: number;
  margin_pct: number;
  round_step: number;
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: number;
  include_waste: boolean;
  waste_pct: number;
  urgent_surcharge_pct: number;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: Difficulty;
}

/**
 * Defaults de fábrica (RF-P5-04), usados para pre-cargar el formulario antes
 * de que llegue la response y por el botón "Restaurar valores por defecto".
 */
export const SETTINGS_DEFAULTS: SettingsFormValues = {
  hourly_rate: 3000,
  margin_pct: 30,
  round_step: 100,
  include_labor: true,
  include_gas: true,
  gas_pct: 3,
  include_waste: true,
  waste_pct: 3,
  urgent_surcharge_pct: 20,
  default_prep_minutes: 30,
  default_servings: 6,
  default_difficulty: "simple",
};

/** Convierte la response (Money string) a valores de formulario (number). */
export function toFormValues(settings: BusinessSettings): SettingsFormValues {
  return {
    hourly_rate: Number(settings.hourly_rate),
    margin_pct: Number(settings.margin_pct),
    round_step: Number(settings.round_step),
    include_labor: settings.include_labor,
    include_gas: settings.include_gas,
    gas_pct: Number(settings.gas_pct),
    include_waste: settings.include_waste,
    waste_pct: Number(settings.waste_pct),
    urgent_surcharge_pct: Number(settings.urgent_surcharge_pct),
    default_prep_minutes: settings.default_prep_minutes,
    default_servings: settings.default_servings,
    default_difficulty: settings.default_difficulty,
  };
}
