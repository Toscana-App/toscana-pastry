/** Types for the dual-pricing feature (T5: S1/S2/S3). */

/** Audience literal matching the backend ``Audience`` type. */
export type Audience = "revendedores" | "consumidor_final";

/** Product (ingredient) returned by the ingredients API. */
export interface Product {
  id: string;
  name: string;
  unit: string;
  price_per_unit: string;
  status?: string;
  /** Restriction tags (P3/P4) — rendered as chips "si existen" (p11 UC-02). */
  tags?: string[];
}

/** Settings returned by GET /tenant/settings. */
export interface SettingsResponse {
  hourly_rate: string;
  margin_pct: string;
  round_step: string;
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: string;
  include_waste: boolean;
  waste_pct: string;
  urgent_surcharge_pct: string;
  consumer_markup_pct: string;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: string;
}

/** Payload for PUT /tenant/settings. */
export interface SettingsUpdatePayload {
  hourly_rate: string;
  margin_pct: string;
  round_step: string;
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: string;
  include_waste: boolean;
  waste_pct: string;
  urgent_surcharge_pct: string;
  consumer_markup_pct: string;
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: string;
}
