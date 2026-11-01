"use client";

/** Mis pedidos del portal (F4 — RF-P11-08).

Listado mobile-first (cards) + badges de estado y pago con texto,
detalle expandible (líneas, entrega, cupón) y paginación.
Badge "Pagar en efectivo en la entrega" para pedidos en efectivo.
*/

import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Skeleton,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useCallback, useEffect, useState } from "react";
import { fetchMyOrderByCode, fetchMyOrders } from "@/services/ordersService";
import { OrderDetail } from "@/types/orders";

const PAGE_SIZE = 10;

const STATUS_BADGES: Record<
  string,
  { label: string; palette: "gray" | "brand" | "green" | "red" }
> = {
  nuevo: { label: "Nuevo", palette: "gray" },
  confirmado: { label: "Confirmado", palette: "brand" },
  entregado: { label: "Entregado", palette: "green" },
  cancelado: { label: "Cancelado", palette: "red" },
};

function PaymentBadge({ order }: { order: OrderDetail }) {
  if (order.paid) {
    return <Badge colorPalette="green" variant="solid">Pagado</Badge>;
  }
  if (order.payment_method === "cash") {
    return (
      <Badge colorPalette="yellow" variant="subtle">
        Pagar en efectivo en la entrega
      </Badge>
    );
  }
  switch (order.payment_status) {
    case "pending":
      return (
        <Badge colorPalette="gray" variant="subtle">
          Pagando…
        </Badge>
      );
    case "rejected":
      return (
        <Badge colorPalette="red" variant="subtle">
          Pago rechazado
        </Badge>
      );
    case "failed":
      return (
        <Badge colorPalette="red" variant="subtle">
          Pago fallido
        </Badge>
      );
    default:
      return (
        <Badge colorPalette="gray" variant="subtle">
          Pendiente de pago
        </Badge>
      );
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function OrderCard({ order }: { order: OrderDetail }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const toggleDetail = useCallback(async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (detail) {
      setExpanded(true);
      return;
    }
    setLoadingDetail(true);
    try {
      setDetail(await fetchMyOrderByCode(order.code));
      setExpanded(true);
    } finally {
      setLoadingDetail(false);
    }
  }, [expanded, detail, order.code]);

  const statusBadge = STATUS_BADGES[order.status] ?? STATUS_BADGES.nuevo;

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={3}>
          <Flex
            justify="space-between"
            align="center"
            gap={2}
            flexWrap="wrap"
          >
            <Box>
              <Text fontWeight="semibold">{order.code}</Text>
              <Text fontSize="sm" color="fg.muted">
                {formatDate(order.date)} ·{" "}
                {order.delivery_mode === "delivery"
                  ? "A domicilio"
                  : "Retiro"}
              </Text>
            </Box>
            <Flex gap={2} align="center" flexWrap="wrap">
              <Badge colorPalette={statusBadge.palette} variant="solid">
                {statusBadge.label}
              </Badge>
              <PaymentBadge order={order} />
            </Flex>
          </Flex>

          <Flex justify="space-between" align="center">
            <Text fontWeight="bold">${order.total}</Text>
            <Button
              size="xs"
              variant="outline"
              onClick={() => void toggleDetail()}
              loading={loadingDetail}
            >
              {expanded ? "Ocultar detalle" : "Ver detalle"}
            </Button>
          </Flex>

          {expanded && !detail && loadingDetail && (
            <Stack gap={2}>
              <Skeleton h="16px" />
              <Skeleton h="16px" />
            </Stack>
          )}

          {expanded && detail && (
            <Stack gap={2} fontSize="sm">
              {detail.delivery_address && (
                <Text>
                  Dirección: {detail.delivery_address}
                </Text>
              )}
              {detail.coupon_code && (
                <Text>
                  Cupón: {detail.coupon_code}
                  {detail.discount_amount !== null &&
                    detail.discount_amount !== "0" &&
                    ` (ahorrás $${detail.discount_amount})`}
                </Text>
              )}
              <Box>
                {detail.items.map((item) => (
                  <Flex
                    key={item.product_id}
                    justify="space-between"
                    gap={2}
                  >
                    <Text>
                      {item.product_name} × {item.quantity}
                    </Text>
                    <Text>${item.total}</Text>
                  </Flex>
                ))}
              </Box>
            </Stack>
          )}
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

function MyOrdersPage() {
  const [orders, setOrders] = useState<OrderDetail[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetchMyOrders(page, PAGE_SIZE);
        if (cancelled) return;
        setOrders(res.orders);
        setTotal(res.total);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "No pudimos cargar tus pedidos"
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [page]);

  if (loading) {
    return (
      <Stack gap={3}>
        <Spinner color="brand.500" />
        <Skeleton h="80px" />
        <Skeleton h="80px" />
      </Stack>
    );
  }

  if (error) {
    return (
      <Text color="red.600">{error}</Text>
    );
  }

  if (!orders || orders.length === 0) {
    return (
      <Card.Root>
        <Card.Body>
          <Stack align="center" gap={3} py={8} textAlign="center">
            <Text fontWeight="semibold">Todavía no tenés pedidos</Text>
            <Text fontSize="sm" color="fg.muted">
              Cuando hagas tu primer pedido vas a poder seguirlo acá.
            </Text>
          </Stack>
        </Card.Body>
      </Card.Root>
    );
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Stack gap={3}>
      {orders.map((order) => (
        <OrderCard key={order.id} order={order} />
      ))}
      {pageCount > 1 && (
        <Flex justify="center" align="center" gap={3} mt={2}>
          <Button
            size="xs"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </Button>
          <Text fontSize="sm">
            {page} / {pageCount}
          </Text>
          <Button
            size="xs"
            variant="outline"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
          >
            Siguiente
          </Button>
        </Flex>
      )}
    </Stack>
  );
}

export default MyOrdersPage;
