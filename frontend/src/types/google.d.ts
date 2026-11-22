/**
 * Minimal type declarations for the Google Identity Services (GIS) client
 * script (https://accounts.google.com/gsi/client). The script is always
 * loaded from Google at runtime (RNF-P1-08) — there is no npm package, so
 * only the surface this app uses is declared here.
 */

export interface GoogleGsiCredentialResponse {
  /** The signed ID token (JWT) to send to the backend. */
  credential: string;
  /** "auto" when the account was auto-selected, "manual" otherwise. */
  select_by?: string;
}

export interface GoogleGsiInitializeOptions {
  client_id: string;
  callback: (response: GoogleGsiCredentialResponse) => void;
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
  nonce?: string;
  locale?: string;
  [key: string]: unknown;
}

export interface GoogleGsiRenderButtonOptions {
  theme?: "outline" | "filled_black" | "filled_blue" | "filled_white";
  size?: "large" | "medium" | "small";
  shape?: "pill" | "circle" | "square";
  text?: "sign_in" | "sign_up" | "continue_with" | "signin_with";
  logo_alignment?: "left" | "center";
  width?: number | "auto";
  [key: string]: unknown;
}

interface GoogleIdApi {
  initialize(options: GoogleGsiInitializeOptions): void;
  renderButton(
    element: HTMLElement,
    options: GoogleGsiRenderButtonOptions,
  ): void;
  disableAutoSelect?(): void;
}

interface GoogleAccountsApi {
  id?: GoogleIdApi;
}

interface GoogleGsiNamespace {
  accounts?: GoogleAccountsApi;
}

declare global {
  interface Window {
    google?: GoogleGsiNamespace;
  }
}
