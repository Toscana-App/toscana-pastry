/** Tipos de leads (RF-P11-13, C5) y coupons (admin ABM, F4). */

export type CustomerType = "consumer" | "business";

export interface LeadCreatePayload {
  name: string;
  email: string;
  customer_type: CustomerType;
  message: string;
  phone?: string | null;
  business_name?: string | null;
  location?: string | null;
}

export interface LeadOut {
  id: string;
  name: string;
  email: string;
  customer_type: CustomerType;
  message: string;
  phone: string | null;
  business_name: string | null;
  location: string | null;
  read: boolean;
  created_at: string;
}

export interface LeadListResponse {
  items: LeadOut[];
  total: number;
  page: number;
  page_size: number;
}

export type CouponType = "percent" | "fixed";

export type CouponStatus = "active" | "paused";

export interface CouponCreatePayload {
  code: string;
  type: CouponType;
  value: string; // Money como string (RNF-P4-02)
  valid_from?: string | null;
  valid_until?: string | null;
  max_uses?: number | null;
  status?: CouponStatus;
}

export interface CouponOut {
  id: string;
  code: string;
  type: CouponType;
  value: string;
  valid_from: string | null;
  valid_until: string | null;
  max_uses: number | null;
  uses: number;
  status: CouponStatus;
  created_at: string;
  updated_at: string;
}

export interface CouponListResponse {
  items: CouponOut[];
  total: number;
  page: number;
  page_size: number;
}
