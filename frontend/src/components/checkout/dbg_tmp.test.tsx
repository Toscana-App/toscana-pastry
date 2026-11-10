import { screen } from "@testing-library/react";
import { writeFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import { StepAddress } from "./StepAddress";
import type { Address } from "@/types/orders";

vi.mock("@/services/ordersService", () => ({ createMyAddress: vi.fn() }));
vi.mock("@/lib/toaster", () => ({ toaster: { create: vi.fn() } }));

const a: Address = {
  id: "addr-1",
  street_line_1: "Calle A 1",
  street_line_2: null,
  city: null,
  postal_code: null,
  province: null,
  phone: null,
  is_default: false,
  created_at: "",
  updated_at: "",
};

describe("dbg", () => {
  it("dump", () => {
    render(<StepAddress addresses={[a]} initial={null} onNext={vi.fn()} />);
    const group = screen.getByRole("radiogroup");
    writeFileSync("C:/Users/Usuario/toscana-pastry/frontend/dbg_dump.txt", group.outerHTML.slice(0, 4000));
    expect(true).toBe(true);
  });
});
