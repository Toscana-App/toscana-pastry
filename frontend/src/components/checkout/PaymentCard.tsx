"use client";

/** Tarjeta de pago post-pedido (F3 — RF-P11-10/11).

Estados sobre polling `GET /orders/{id}/payment` ≤ 5 s:
- pending → spinner "Procesando…"
- approved → success
- rejected|failed → danger + motivo
Efectivo: badge "Pagar en efectivo en la entrega".
Solo se redirige a checkout_url de origen confiable (allowlist).
*/

import { Alert, Box, Button, Flex, Spinner, Stack, Text } from "@chakra-ui/react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchOrderPaymentStatus,
  initOrderPayment,
} from "@/services/ordersService";
import { OrderDetail } from "@/types/orders";

const POLL_INTERVAL_MS = 5000;
const MAX_POLLS = 12; // ≤ 60 s

type PollState =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "approved" }
  | { kind: "rejected"; reason: string }
  | { kind: "error"; message: string };

const REJECTION_REASONS: Record<string, string> = {
  rejected: "El pago fue rechazado por el emisor.",
  failed: "El pago falló. Intentá de nuevo o pagá en efectivo.",
};

/** Returns the checkout URL only when the host is allowlisted.

The link is rendered as `<a href>` (no dynamic assignment to the page
location) with the origin rebuilt from the allowed host.
*/
const ALLOWED_CHECKOUT_HOSTS = ["mercadopago.com"];

function toTrustedCheckoutUrl(raw: string): string | null {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "https:") return null;
    const host = parsed.hostname;
    const allowed = ALLOWED_CHECKOUT_HOSTS.some(
      (h) => host === h || host.endsWith(`.${h}`)
    );
    if (!allowed) return null;
    return new URL(parsed.pathname + parsed.search, `https://${host}`).toString();
  } catch {
    return null;
  }
}

function makeIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function PaymentCard({ order }: { order: OrderDetail }) {
  const isMercadopago = order.payment_method === "mercadopago";
  // attempt=1 inicial si es MP: arranca solo al montar, sin effect de setState.
  const [attempt, setAttempt] = useState(isMercadopago ? 1 : 0);
  const [state, setState] = useState<PollState>({ kind: "idle" });
  const [reference, setReference] = useState<string | null>(null);
  const [checkoutHref, setCheckoutHref] = useState<string | null>(null);

  // ── Init del pago (una vez por attempt) ─────────────────────────────
  useEffect(() => {
    if (attempt === 0) return;
    let cancelled = false;
    (async () => {
      try {
        const init = await initOrderPayment(order.id, makeIdempotencyKey());
        if (cancelled) return;
        setReference(init.reference);
        setCheckoutHref(toTrustedCheckoutUrl(init.checkout_url));
      } catch (error) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              error instanceof Error
                ? error.message
                : "No se pudo iniciar el pago.",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt, order.id]);

  // ── Polling del estado (mientras haya reference) ────────────────────
  useEffect(() => {
    if (reference === null) return;
    let pollsLeft = MAX_POLLS;
    let done = false;

    const tick = async (): Promise<void> => {
      if (done) return;
      try {
        const status = await fetchOrderPaymentStatus(order.id);
        if (done) return;
        if (status.paid || status.status === "approved") {
          done = true;
          setState({ kind: "approved" });
          return;
        }
        if (status.status === "rejected" || status.status === "failed") {
          done = true;
          setState({
            kind: "rejected",
            reason: REJECTION_REASONS[status.status] ?? "Pago no aprobado.",
          });
          return;
        }
      } catch {
        // red/timeout: seguimos en pending
      }
      if (!done) setState({ kind: "pending" });
    };

    void tick();
    const intervalId = setInterval(() => {
      if (done) {
        clearInterval(intervalId);
        return;
      }
      pollsLeft -= 1;
      if (pollsLeft <= 0) {
        clearInterval(intervalId);
        return;
      }
      void tick();
    }, POLL_INTERVAL_MS);

    return () => {
      done = true;
      clearInterval(intervalId);
    };
  }, [reference, order.id]);

  const retry = useCallback(() => {
    setState({ kind: "pending" });
    setReference(null);
    setCheckoutHref(null);
    setAttempt((a) => a + 1);
  }, []);

  if (!isMercadopago) {
    return (
      <Alert.Root status="info">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>Pagar en efectivo en la entrega</Alert.Title>
          <Alert.Description>
            No hace falta pago online: abonás al recibir tu pedido.
          </Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  return (
    <Box borderWidth="1px" borderColor="border.muted" rounded="md" p={4}>
      <Stack gap={3}>
        <Text fontWeight="semibold">Mercado Pago</Text>

        {state.kind === "idle" && (
          <Text fontSize="sm" color="fg.muted">
            Preparamos tu pago…
          </Text>
        )}

        {state.kind === "pending" && (
          <Flex align="center" gap={3}>
            <Spinner size="sm" color="brand.fg" />
            <Text fontSize="sm">
              Procesando pago, esto puede tardar unos segundos…
            </Text>
          </Flex>
        )}

        {state.kind === "approved" && (
          <Alert.Root status="success" width="100%">
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>¡Pago aprobado!</Alert.Title>
              <Alert.Description>
                Tu pedido quedó confirmado con el pago online.
              </Alert.Description>
            </Alert.Content>
          </Alert.Root>
        )}

        {(state.kind === "rejected" || state.kind === "error") && (
          <Stack gap={3} width="100%">
            <Alert.Root status="error" width="100%">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>
                  {state.kind === "rejected"
                    ? "Pago no aprobado"
                    : "Error al iniciar el pago"}
                </Alert.Title>
                <Alert.Description>
                  {state.kind === "rejected" ? state.reason : state.message}
                </Alert.Description>
              </Alert.Content>
            </Alert.Root>
            <Flex justify="flex-end">
              <Button size="sm" variant="outline" onClick={retry}>
                Reintentar pago
              </Button>
            </Flex>
          </Stack>
        )}

        {reference !== null && state.kind === "pending" && (
          <Stack gap={2} width="100%">
            <Text fontSize="xs" color="fg.muted">
              Reference: {reference}
            </Text>
            {checkoutHref !== null && (
              <Button asChild size="sm" colorPalette="brand">
                <a href={checkoutHref} rel="noopener noreferrer">
                  Ir a pagar con Mercado Pago
                </a>
              </Button>
            )}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
