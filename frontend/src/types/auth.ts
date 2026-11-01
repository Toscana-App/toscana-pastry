export type UserRole = "admin" | "customer" | "negocio";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  googleId?: string;
}

export interface AuthResponse {
  user_id: string;
  email: string;
  access_token: string;
  refresh_token: string;
  role: UserRole;
  google_id?: string;
}

export interface UserInfo {
  user_id: string;
  email: string;
  role: UserRole;
  google_id?: string;
}

export interface LoginRequest {
  email?: string;
  googleId?: string;
}
