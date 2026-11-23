export interface GoogleGsiCredentialResponse {
  credential: string;
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
