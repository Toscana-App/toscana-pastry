import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import { StepAddress } from "./StepAddress";
import type { Address } from "@/types/orders";

vi.mock("@/services/ordersService", () => ({
  createMyAddress: vi.fn(),
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

const savedAddress: Address = {
  id: "addr-1",
  street_line_1: "Av. Corrientes 1234",
  street_line_2: null,
  city: "Buenos Aires",
  postal_code: "C1042",
  province: "CABA",
  phone: null,
  is_default: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("StepAddress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("opens the new-address form when the 'new' radio is activated by keyboard", async () => {
    render(
      <StepAddress
        addresses={[savedAddress]}
        initial={null}
        onNext={vi.fn()}
      />
    );

    const radios = screen.getAllByRole("radio");
    // orden en el DOM: [dirección guardada, "usar una nueva"]
    const newRadio = radios[radios.length - 1];
    fireEvent.focus(newRadio);
    fireEvent.click(newRadio);

    await waitFor(() => {
      expect(
        screen.getByText("Calle y número *")
      ).toBeInTheDocument();
    });
  });

  it("shows the saved address list and continues on selection", async () => {
    const onNext = vi.fn();
    render(
      <StepAddress
        addresses={[savedAddress]}
        initial={null}
        onNext={onNext}
      />
    );

    expect(
      screen.getByText(/Av\. Corrientes 1234/)
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("radio")[0]);

    await waitFor(() => {
      expect(onNext).toHaveBeenCalledWith(
        expect.objectContaining({ addressId: "addr-1" })
      );
    });
  });
});
