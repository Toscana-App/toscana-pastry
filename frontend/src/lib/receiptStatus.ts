import type { OrderDetail } from "@/types/orders";

export type ReceiptState =
  | "not_applicable"
  | "uploadable"
  | "pending_review"
  | "none";

const TERMINAL_STATUSES = new Set(["delivered", "cancelled"]);

export function deriveReceiptState(
  order: Pick<
    OrderDetail,
    | "payment_method"
    | "status"
    | "paid"
    | "payment_status"
    | "receipt_uploaded"
  >,
): ReceiptState {
  if (order.payment_method !== "transfer") return "not_applicable";
  if (TERMINAL_STATUSES.has(order.status)) return "none";
  if (!order.receipt_uploaded) return "uploadable";
  const paymentPending =
    !order.paid &&
    (order.payment_status === null ||
      order.payment_status === "" ||
      order.payment_status === "pending");
  return paymentPending ? "pending_review" : "none";
}
