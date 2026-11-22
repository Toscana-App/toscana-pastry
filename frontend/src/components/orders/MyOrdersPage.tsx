"use client";


import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Skeleton,
  Stack,
  Text,
} from "@chakra-ui/react";
import { OrderListSkeleton } from "@/components/ui/skeleton";

import { useCallback, useEffect, useState } from "react";
import { gooeyToast } from "goey-toast";
import {
  fetchMyOrderByCode,
  fetchMyOrders,
  initOrderPayment,
} from "@/services/ordersService";
import { OrderDetail } from "@/types/orders";

const PAGE_SIZE = 10;

function formatMoney(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return parsed.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function canPayNow(order: OrderDetail): boolean {
  if (order.paid) return false;
  if (order.payment_method !== "mercadopago") return false;
  return [
    null,
    "",
    "rejected",
    "failed",
  ].includes(order.payment_status);
}

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
    return <Badge colorPalette="green" variant="subtle">Pagado</Badge>;
  }
  if (order.payment_method === "cash") {
    return (
      <Badge colorPalette="yellow" variant="subtle">
        Pagar en efectivo en la entrega
      </Badge>
    );
  }
  if (order.payment_method === "transfer") {
    return (
      <Badge colorPalette="blue" variant="subtle">
        Pagar por transferencia
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

function OrderCard({
  order,
  onPaidChange,
}: {
  order: OrderDetail;
  onPaidChange: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [paying, setPaying] = useState(false);

  const handlePay = useCallback(async () => {
    setPaying(true);
    try {
      const { checkout_url } = await initOrderPayment(
        order.id,
        crypto.randomUUID()
      );
      const isInternal =
        checkout_url.startsWith("/") && !checkout_url.startsWith("//");
      let safeTarget: string;
      if (isInternal) {
        safeTarget = checkout_url;
      } else {
        let url: URL | null = null;
        try {
          url = new URL(checkout_url);
        } catch {
          url = null;
        }
        if (!url || url.protocol !== "https:") {
          gooeyToast.error("¡Ups! No se pudo iniciar el pago", {
            description: "La URL de pago no es segura. Intenta de nuevo.",
          });
          return;
        }
        safeTarget = url.toString();
      }
      window.open(safeTarget, isInternal ? "_self" : "_blank", "noopener");
      gooeyToast.success("¡Pago iniciado!", {
        description: "Completa el pago en la ventana que se abrió.",
      });
      onPaidChange();
    } catch (error) {
      gooeyToast.error("¡Ups! No se pudo iniciar el pago", {
        description:
          error instanceof Error ? error.message : "Intenta de nuevo.",
      });
    } finally {
      setPaying(false);
    }
  }, [order.id, onPaidChange]);

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
              {canPayNow(order) && (
                <Button
                  size="sm"
                  colorPalette="brand"
                  loading={paying}
                  onClick={() => void handlePay()}
                >
                  Pagar con Mercado Pago
                </Button>
              )}
            </Flex>
          </Flex>

          <Flex justify="space-between" align="center">
            <Text fontWeight="bold">${formatMoney(order.total)}</Text>
            <Button
              size="sm"
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
                    ` (ahorras $${formatMoney(detail.discount_amount)})`}
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
                    <Text>${formatMoney(item.total)}</Text>
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
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

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
  }, [page, refreshKey]);

  if (loading) {
    return <OrderListSkeleton />;
  }

  if (error) {
    return (
      <Alert.Root status="error">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>¡Ups! No pudimos cargar tus pedidos</Alert.Title>
          <Alert.Description>{error}</Alert.Description>
          <Flex justify="flex-end" mt={2}>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setError(null);
                setLoading(true);
                refresh();
              }}
            >
              Reintentar
            </Button>
          </Flex>
        </Alert.Content>
      </Alert.Root>
    );
  }

  if (!orders || orders.length === 0) {
    return (
      <Card.Root>
        <Card.Body>
          <Stack align="center" gap={3} py={8} textAlign="center">
            <Text fontWeight="semibold">Todavía no tienes pedidos</Text>
            <Text fontSize="sm" color="fg.muted">
              Cuando hagas tu primer pedido podrás seguirlo acá.
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
        <OrderCard key={order.id} order={order} onPaidChange={refresh} />
      ))}
      {pageCount > 1 && (
        <Flex justify="center" align="center" gap={3} mt={2}>
          <Button
            size="sm"
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
            size="sm"
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
