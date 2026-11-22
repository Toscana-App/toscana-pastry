import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { ApiError } from "@/lib/api";
import { gooeyToast } from "goey-toast";
import LoginForm from "./LoginForm";

type GsiCallback = (response: { credential: string }) => void;

const h = vi.hoisted(() => ({
  initialize: vi.fn(),
  renderButton: vi.fn(),
  disableAutoSelect: vi.fn(),
  initOptions: null as Record<string, unknown> | null,
  callback: null as GsiCallback | null,
  fetchNonce: vi.fn(),
  login: vi.fn(),
  refresh: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("@/services/authService", () => ({
  authService: {
    fetchGoogleNonce: (...a: unknown[]) => h.fetchNonce(...a),
    loginWithGoogleCredential: (...a: unknown[]) => h.login(...a),
    getUser: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    loading: false,
    logout: vi.fn(),
    refresh: (...a: unknown[]) => h.refresh(...a),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: h.routerReplace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("goey-toast", () => ({
  gooeyToast: { success: vi.fn(), error: vi.fn() },
}));

function installGoogle() {
  h.initialize.mockImplementation(
    (options: { callback: GsiCallback }) => {
      h.initOptions = options as unknown as Record<string, unknown>;
      h.callback = options.callback;
    },
  );
  Object.defineProperty(window, "google", {
    value: {
      accounts: {
        id: {
          initialize: h.initialize,
          renderButton: h.renderButton,
          disableAutoSelect: h.disableAutoSelect,
        },
      },
    },
    configurable: true,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  h.initOptions = null;
  h.callback = null;
  h.fetchNonce.mockResolvedValue({ nonce: "nonce-1" });
  h.refresh.mockResolvedValue(null);
  installGoogle();
});

describe("LoginForm", () => {
  it("without a client id: no GSI button, honest 'not configured' text", () => {
    renderWithProviders(<LoginForm />);

    expect(
      screen.getByText("Acceso con Google no configurado"),
    ).toBeInTheDocument();
    expect(h.initialize).not.toHaveBeenCalled();
    expect(h.renderButton).not.toHaveBeenCalled();
    expect(h.fetchNonce).not.toHaveBeenCalled();
  });

  it("fetches the nonce and initializes with nonce + client_id, then renders the button", async () => {
    renderWithProviders(<LoginForm googleClientId="client-123" />);

    await waitFor(() => expect(h.renderButton).toHaveBeenCalledTimes(1));
    expect(h.fetchNonce).toHaveBeenCalledTimes(1);
    expect(h.initOptions).toMatchObject({
      client_id: "client-123",
      nonce: "nonce-1",
      auto_select: false,
      cancel_on_tap_outside: true,
    });
    const [el, opts] = h.renderButton.mock.calls[0] as [
      HTMLElement,
      Record<string, unknown>,
    ];
    expect(el).toBeInstanceOf(HTMLElement);
    expect(opts).toMatchObject({
      theme: "outline",
      size: "large",
      text: "continue_with",
    });
  });

  it("on credential: POSTs it, refreshes auth and redirects by role", async () => {
    h.login.mockResolvedValue({
      user_id: "u1",
      email: "u@gmail.com",
      role: "admin",
      state: "signed_in",
    });
    renderWithProviders(<LoginForm googleClientId="client-123" />);
    await waitFor(() => expect(h.callback).not.toBeNull());

    await act(async () => {
      h.callback!({ credential: "jwt-1" });
    });

    expect(h.login).toHaveBeenCalledWith("jwt-1");
    await waitFor(() => expect(h.refresh).toHaveBeenCalled());
    await waitFor(() => expect(h.routerReplace).toHaveBeenCalledWith("/admin"));
  });

  it("409 no_account: shows the backend message in an alert", async () => {
    h.login.mockRejectedValue(
      new ApiError(409, "conflict", {
        detail: {
          message: "Revisá tu email de compra para crear tu cuenta.",
          state: "no_account",
        },
      }),
    );
    renderWithProviders(<LoginForm googleClientId="client-123" />);
    await waitFor(() => expect(h.callback).not.toBeNull());

    await act(async () => {
      h.callback!({ credential: "jwt-1" });
    });

    expect(
      screen.getByText("Revisá tu email de compra para crear tu cuenta."),
    ).toBeInTheDocument();
    expect(h.refresh).not.toHaveBeenCalled();
    expect(h.routerReplace).not.toHaveBeenCalled();
  });

  it("409 link_pending: shows the backend message in an alert", async () => {
    h.login.mockRejectedValue(
      new ApiError(409, "conflict", {
        detail: {
          message: "Confirmá tu cuenta para enlazar Google.",
          state: "link_pending",
        },
      }),
    );
    renderWithProviders(<LoginForm googleClientId="client-123" />);
    await waitFor(() => expect(h.callback).not.toBeNull());

    await act(async () => {
      h.callback!({ credential: "jwt-1" });
    });

    expect(
      screen.getByText("Confirmá tu cuenta para enlazar Google."),
    ).toBeInTheDocument();
  });

  it("401: shows the fixed 'could not validate' message", async () => {
    h.login.mockRejectedValue(new ApiError(401, "Invalid Google token"));
    renderWithProviders(<LoginForm googleClientId="client-123" />);
    await waitFor(() => expect(h.callback).not.toBeNull());

    await act(async () => {
      h.callback!({ credential: "bad-jwt" });
    });

    expect(
      screen.getByText(
        "No pudimos validar tu cuenta de Google. Volvé a intentar.",
      ),
    ).toBeInTheDocument();
  });

  it("other errors: toast, no alert, no redirect", async () => {
    h.login.mockRejectedValue(new Error("network down"));
    renderWithProviders(<LoginForm googleClientId="client-123" />);
    await waitFor(() => expect(h.callback).not.toBeNull());

    await act(async () => {
      h.callback!({ credential: "jwt-1" });
    });

    expect(vi.mocked(gooeyToast.error)).toHaveBeenCalled();
    expect(h.refresh).not.toHaveBeenCalled();
    expect(h.routerReplace).not.toHaveBeenCalled();
  });
});
