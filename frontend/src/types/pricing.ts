export type Audience = "revendedores" | "consumidor_final";

export interface Product {
  id: string;
  name: string;
  category: string;
  description: string;
  image_url: string | null;
  price: string;
  price_per_serving: string | null;
  complete: boolean;
}

export interface StoreProductDetail {
  id: string;
  name: string;
  category: string;
  description: string;
  image_url: string | null;
  price: string;
  servings: number;
  prep_time_min: number;
}
