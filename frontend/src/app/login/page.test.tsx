import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import LoginPage from "./page";

// `useSearchParams` needs a stub outside of a Next render context.
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("login page", () => {
  it("shows the static form (no endpoint data → no skeleton anywhere)", () => {
    const { container } = renderWithProviders(<LoginPage />);
    // The real form renders: heading, subtitle, both actions.
    expect(screen.getByText("Iniciar sesión")).toBeTruthy();
    expect(screen.getByText("Elige un método para continuar")).toBeTruthy();
    expect(screen.getByText("Enviar link de acceso")).toBeTruthy();
    expect(screen.getByText("Continuar con Google")).toBeTruthy();
    // No loading surface: nothing on this screen comes from an endpoint.
    expect(container.querySelector('[role="status"]')).toBeNull();
  });
});
