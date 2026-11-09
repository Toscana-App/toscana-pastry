import { centsToPesos } from "@/lib/format";

export const DIFFICULTIES = ["simple", "intermedio", "complejo"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

export interface BusinessSettings {
  hourly_rate: number;
  margin_pct: string;
  round_step: number;
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: string;
  include_waste: boolean;
  waste_pct: string;
  urgent_surcharge_pct: string;
  consumer_markup_pct?: string;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: Difficulty;
}

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
  consumer_markup_pct: number;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: Difficulty;
}

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
  consumer_markup_pct: 40,
  default_prep_minutes: 30,
  default_servings: 6,
  default_difficulty: "simple",
};

export function toFormValues(settings: BusinessSettings): SettingsFormValues {
  return {
    hourly_rate: centsToPesos(settings.hourly_rate),
    margin_pct: Number(settings.margin_pct),
    round_step: centsToPesos(settings.round_step),
    include_labor: settings.include_labor,
    include_gas: settings.include_gas,
    gas_pct: Number(settings.gas_pct),
    include_waste: settings.include_waste,
    waste_pct: Number(settings.waste_pct),
    urgent_surcharge_pct: Number(settings.urgent_surcharge_pct),
    consumer_markup_pct: Number(settings.consumer_markup_pct ?? SETTINGS_DEFAULTS.consumer_markup_pct),
    default_prep_minutes: settings.default_prep_minutes,
    default_servings: settings.default_servings,
    default_difficulty: settings.default_difficulty,
  };
}

export interface OrderWindow {
  open: boolean;
  reopens_at: string | null;
  message: string;
}

export interface OrderWindowUpdate {
  open: boolean;
  reopens_at?: string | null;
  message?: string;
}
