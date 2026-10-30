import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import GeneralSettingsForm from "./GeneralSettingsForm";
import type { CalcSettingsResponse } from "@/types/calc";

// Seams: el service y el toaster. Sin backend real (PREGUNTAS.md → F1).
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";

const settings: CalcSettingsResponse = {
  business_name: "Toscana Pastry",
  main_currency_name: "Peso argentino",
  main_currency_symbol: "$",
  default_margin_percent: "30",
  default_discount_percent: "0",
  default_tax_percent: "19",
  rounding_mode: "none",
};

const marginInput = () => screen.getByLabelText("Margen por defecto (%)");

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(calcSettingsService.getSettings).mockResolvedValue(settings);
  vi.mocked(calcSettingsService.updateSettings).mockResolvedValue(settings);
});

describe("GeneralSettingsForm", () => {
  it("renders the values fetched from the API", async () => {
    render(<GeneralSettingsForm />);

    expect(
      await screen.findByLabelText("Nombre del negocio")
    ).toHaveDisplayValue("Toscana Pastry");
    expect(
      screen.getByLabelText("Moneda principal (nombre)")
    ).toHaveDisplayValue("Peso argentino");
    expect(marginInput()).toHaveDisplayValue("30");
    expect(
      screen.getByLabelText("Descuento por defecto (%)")
    ).toHaveDisplayValue("0");
    expect(
      screen.getByLabelText("Impuesto por defecto (%)")
    ).toHaveDisplayValue("19");
    // rounding_mode "none" → su label en español (trigger del select y
    // opción del select nativo de a11y que Ark UI mantiene en el DOM).
    expect(screen.getAllByText("Sin redondeo").length).toBeGreaterThanOrEqual(
      1
    );
  });

  it("saves the form sending the full 7-field payload", async () => {
    render(<GeneralSettingsForm />);
    await screen.findByLabelText("Nombre del negocio");

    fireEvent.change(screen.getByLabelText("Nombre del negocio"), {
      target: { value: "Toscana Bakery" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(calcSettingsService.updateSettings).toHaveBeenCalledTimes(1)
    );
    expect(calcSettingsService.updateSettings).toHaveBeenCalledWith({
      business_name: "Toscana Bakery",
      main_currency_name: "Peso argentino",
      main_currency_symbol: "$",
      default_margin_percent: "30",
      default_discount_percent: "0",
      default_tax_percent: "19",
      rounding_mode: "none",
    });
  });

  it("does not send the request when a percent is out of the 0-100 range", async () => {
    render(<GeneralSettingsForm />);
    await screen.findByLabelText("Nombre del negocio");

    fireEvent.change(marginInput(), { target: { value: "150" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(calcSettingsService.updateSettings).not.toHaveBeenCalled();
  });

  it("shows an error toast when the API rejects the save", async () => {
    vi.mocked(calcSettingsService.updateSettings).mockRejectedValue(
      new Error("default_margin_percent: must be greater than or equal to 0")
    );

    render(<GeneralSettingsForm />);
    await screen.findByLabelText("Nombre del negocio");

    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          description:
            "default_margin_percent: must be greater than or equal to 0",
        })
      )
    );
  });
});
