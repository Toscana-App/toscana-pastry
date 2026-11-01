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
}
