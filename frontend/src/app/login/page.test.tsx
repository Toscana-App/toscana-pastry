import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { AuthProvider } from "@/contexts/AuthContext";
import LoginPage from "./page";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("next/headers", () => ({
  headers: () => new Headers(),
}));

vi.mock("@/services/authService", () => ({
  authService: {
    fetchGoogleNonce: vi.fn(),
    loginWithGoogleCredential: vi.fn(),
    getUser: vi.fn().mockResolvedValue(null),
    logout: vi.fn(),
  },
}));

describe("login page", () => {
  it("shows the Google-only form without a loading surface", () => {
    const { container } = renderWithProviders(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    expect(screen.getByText("Iniciar sesión")).toBeTruthy();
    expect(screen.getByText("Continúa con tu cuenta de Google")).toBeTruthy();
    expect(
      screen.getByText("Acceso con Google no configurado"),
    ).toBeTruthy();
    expect(screen.queryByText("Enviar link de acceso")).toBeNull();
    expect(container.querySelector('[role="status"]')).toBeNull();
  });
});
