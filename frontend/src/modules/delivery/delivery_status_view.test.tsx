import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "@/test-utils";
import { DeliveryStatusView } from "./delivery_status_view";

vi.mock("@/services/deliveryService", () => ({
  fetchPublicDelivery: vi.fn(),
}));

import { fetchPublicDelivery } from "@/services/deliveryService";

const mockedFetch = vi.mocked(fetchPublicDelivery);
const TOKEN = "2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DeliveryStatusView", () => {
  it("says the order was delivered and names the order code", async () => {
    mockedFetch.mockResolvedValue({
      state: "delivered",
      order_code: "#00042",
      status: "delivered",
      status_label: "Entregado",
      message: "Su pedido ha sido entregado",
    });

    render(<DeliveryStatusView token={TOKEN} />);

    expect(
      await screen.findByRole("heading", { name: "Su pedido ha sido entregado" }),
    ).toBeTruthy();
    expect(screen.getByText("#00042")).toBeTruthy();
    expect(mockedFetch).toHaveBeenCalledWith(TOKEN, expect.any(AbortSignal));
  });

  it("lets the visitor retry after a failed load", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("Sin conexión"));

    render(<DeliveryStatusView token={TOKEN} />);

    const retry = await screen.findByRole("button", { name: "Reintentar" });
    mockedFetch.mockResolvedValueOnce({
      state: "active",
      order_code: "#00044",
      status: "pending_delivery",
      status_label: "Pendiente entrega",
      message: "Su pedido está en curso",
    });
    fireEvent.click(retry);

    expect(
      await screen.findByRole("heading", { name: "Su pedido está en curso" }),
    ).toBeTruthy();
    expect(mockedFetch).toHaveBeenCalledTimes(2);
  });

  it("shows the current status while the order is in progress", async () => {
    mockedFetch.mockResolvedValue({
      state: "active",
      order_code: "#00043",
      status: "pending_delivery",
      status_label: "Pendiente entrega",
      message: "Su pedido está en curso",
    });

    render(<DeliveryStatusView token={TOKEN} />);

    expect(
      await screen.findByRole("heading", { name: "Su pedido está en curso" }),
    ).toBeTruthy();
    expect(screen.getByText("Pendiente entrega")).toBeTruthy();
  });

  it("shows a generic message for unknown links", async () => {
    mockedFetch.mockRejectedValue(new Error("Link inválido o expirado"));

    render(<DeliveryStatusView token={TOKEN} />);

    expect(
      await screen.findByRole("heading", { name: "No pudimos abrir este enlace" }),
    ).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Link inválido o expirado")).toBeTruthy());
  });

  it("never renders an order code when the link expired", async () => {
    mockedFetch.mockResolvedValue({
      state: "expired",
      order_code: "",
      status: "",
      status_label: "",
      message: "Este enlace ya no está disponible",
    });

    render(<DeliveryStatusView token={TOKEN} />);

    expect(
      await screen.findByRole("heading", { name: "Este enlace ya no está disponible" }),
    ).toBeTruthy();
    expect(screen.queryByText("Pedido")).toBeNull();
  });
});
