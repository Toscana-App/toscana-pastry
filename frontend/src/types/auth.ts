export interface User {
  id: string;
  email: string;
  googleId?: string;
}

export interface AuthResponse {
  user_id: string;
  email: string;
  token: string;
  google_id?: string;
}

export interface LoginRequest {
  email?: string;
  googleId?: string;
}
