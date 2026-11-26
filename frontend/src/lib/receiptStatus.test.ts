import { describe, expect, it } from "vitest";
import { deriveReceiptState } from "./receiptStatus";
import type { OrderDetail } from "@/types/orders";

function order(overrides: Partial<OrderDetail> = {}): OrderDetail {
  return {
    id: "o1",
    code: "PED-001",
    customer_id: "c1",
    status: "new",
    date: "2026-11-01T12:00:00Z",
    payment_method: "transfer",
    delivery_mode: "pickup",
    delivery_address: null,
    coupon_code: null,
    discount_amount: null,
    paid: false,
    payment_status: null,
    total: "100",
    items: [],
    created_at: "2026-11-01T12:00:00Z",
    receipt_uploaded: false,
    receipt_content_type: null,
    receipt_uploaded_at: null,
    receipt_viewed_at: null,
    ...overrides,
  };
}

describe("deriveReceiptState (D5)", () => {
  it("transfer sin comprobante en estado no terminal → uploadable", () => {
    expect(deriveReceiptState(order())).toBe("uploadable");
    expect(deriveReceiptState(order({ status: "confirmed" }))).toBe("uploadable");
    expect(deriveReceiptState(order({ status: "preparing" }))).toBe("uploadable");
  });

  it("transfer sin comprobante en estado terminal → none", () => {
    expect(deriveReceiptState(order({ status: "delivered" }))).toBe("none");
    expect(deriveReceiptState(order({ status: "cancelled" }))).toBe("none");
  });

  it("comprobante cargado + pago pendiente (null o pending) + no terminal → pending_review", () => {
    const withReceipt = {
      receipt_uploaded: true,
      receipt_content_type: "application/pdf",
      receipt_uploaded_at: "2026-11-01T12:00:00Z",
    };
    expect(deriveReceiptState(order(withReceipt))).toBe("pending_review");
    expect(
      deriveReceiptState(
        order({ ...withReceipt, payment_status: "pending", status: "confirmed" }),
      ),
    ).toBe("pending_review");
  });

  it("comprobante cargado + pago aprobado → none", () => {
    expect(
      deriveReceiptState(
        order({
          receipt_uploaded: true,
          paid: true,
          payment_status: "approved",
          status: "preparing",
        }),
      ),
    ).toBe("none");
  });

  it("comprobante cargado + pedido cancelado (rechazo) → none", () => {
    expect(
      deriveReceiptState(
        order({
          receipt_uploaded: true,
          payment_status: "rejected",
          status: "cancelled",
        }),
      ),
    ).toBe("none");
  });

  it("método no transfer → not_applicable (cero cambios de UX)", () => {
    expect(deriveReceiptState(order({ payment_method: "cash" }))).toBe(
      "not_applicable",
    );
    expect(
      deriveReceiptState(order({ payment_method: "mercadopago" })),
    ).toBe("not_applicable");
  });
});
