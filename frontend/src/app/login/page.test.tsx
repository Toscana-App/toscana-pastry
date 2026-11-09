import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import LoginPage from "./page";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("login page", () => {
  it("shows the Google-only form without a loading surface", () => {
    const { container } = renderWithProviders(<LoginPage />);
    expect(screen.getByText("Iniciar sesión")).toBeTruthy();
    expect(screen.getByText("Continúa con tu cuenta de Google")).toBeTruthy();
    expect(screen.getByText("Continuar con Google")).toBeTruthy();
    expect(screen.queryByText("Enviar link de acceso")).toBeNull();
    expect(container.querySelector('[role="status"]')).toBeNull();
  });
});
