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


export interface GoogleSignInResponse {
  user_id: string;
  email: string;
  role: UserRole;
  state: "signed_in";
}


export type GoogleSignInConflictState = "no_account" | "link_pending";

export interface GoogleSignInConflictDetail {
  message: string;
  state: GoogleSignInConflictState;
}
