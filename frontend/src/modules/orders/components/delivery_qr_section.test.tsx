import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "@/test-utils";
import { DeliveryQrSection } from "./delivery_qr_section";

vi.mock("@/services/deliveryService", () => ({
  fetchDeliveryLink: vi.fn(),
  fetchDeliveryQrObjectUrl: vi.fn(),
  copyToClipboard: vi.fn(),
}));

import {
  copyToClipboard,
  fetchDeliveryLink,
  fetchDeliveryQrObjectUrl,
} from "@/services/deliveryService";

const mockedLink = vi.mocked(fetchDeliveryLink);
const mockedQr = vi.mocked(fetchDeliveryQrObjectUrl);
const mockedCopy = vi.mocked(copyToClipboard);

beforeEach(() => {
  vi.clearAllMocks();
  mockedLink.mockResolvedValue({
    token: "2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e",
    url: "https://app.example.com/entrega/2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e",
    state: "active",
    created_at: "2026-11-26T10:00:00Z",
  });
  mockedQr.mockResolvedValue("blob:qr");
  mockedCopy.mockResolvedValue(true);
});

describe("DeliveryQrSection", () => {
  it("is hidden once the order reached a terminal status", () => {
    render(<DeliveryQrSection orderId="o1" orderStatus="delivered" />);
    expect(screen.queryByRole("button", { name: "Ver QR de entrega" })).toBeNull();

    render(<DeliveryQrSection orderId="o1" orderStatus="cancelled" />);
    expect(screen.queryByRole("button", { name: "Ver QR de entrega" })).toBeNull();
  });

  it("opens the dialog with the QR image and the public link", async () => {
    render(<DeliveryQrSection orderId="o1" orderStatus="confirmed" />);

    fireEvent.click(screen.getByRole("button", { name: "Ver QR de entrega" }));

    expect(await screen.findByAltText("Código QR de entrega del pedido")).toBeTruthy();
    expect(mockedLink).toHaveBeenCalledWith("o1");
    expect(mockedQr).toHaveBeenCalledWith("o1");
    expect(
      screen.getByText("https://app.example.com/entrega/2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e"),
    ).toBeTruthy();
  });

  it("confirms the copy in a live region", async () => {
    render(<DeliveryQrSection orderId="o1" orderStatus="confirmed" />);
    fireEvent.click(screen.getByRole("button", { name: "Ver QR de entrega" }));
    await screen.findByAltText("Código QR de entrega del pedido");

    fireEvent.click(screen.getByRole("button", { name: "Copiar enlace" }));

    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Enlace copiado"));
    expect(mockedCopy).toHaveBeenCalledWith(
      "https://app.example.com/entrega/2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e",
    );
  });

  it("shows the failure path when the clipboard is denied", async () => {
    mockedCopy.mockResolvedValue(false);
    render(<DeliveryQrSection orderId="o1" orderStatus="confirmed" />);
    fireEvent.click(screen.getByRole("button", { name: "Ver QR de entrega" }));
    await screen.findByAltText("Código QR de entrega del pedido");

    fireEvent.click(screen.getByRole("button", { name: "Copiar enlace" }));

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toBe(
        "No pudimos copiar. Seleccioná el enlace y copialo a mano.",
      ),
    );
  });

  it("reports when the QR cannot be generated", async () => {
    mockedLink.mockRejectedValue(new Error("Pedido no encontrado"));

    render(<DeliveryQrSection orderId="o1" orderStatus="confirmed" />);
    fireEvent.click(screen.getByRole("button", { name: "Ver QR de entrega" }));

    expect(await screen.findByText("Pedido no encontrado")).toBeTruthy();
    expect(screen.queryByAltText("Código QR de entrega del pedido")).toBeNull();
  });
});
