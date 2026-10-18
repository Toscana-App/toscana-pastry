"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  HStack,
  Skeleton,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { formatCents, formatPct } from "@/lib/format";
import { ordersService } from "../service";
import {
  ALLOWED_TRANSITIONS,
  ORDER_STATUS_LABELS,
  type OrderDetail,
  type OrderStatus,
  type WhatsAppLink,
} from "../types";

const STATUS_COLORS: Record<OrderStatus, "blue" | "green" | "gray" | "red"> = {
  nuevo: "blue",
  confirmado: "green",
  entregado: "gray",
  cancelado: "red",
};

/**
 * Detalle de pedido (Fase 6, UC-03/UC-05/UC-06) — /pedidos/[id].
 *
 * Muestra el snapshot congelado (RNF-P6-03): líneas de costo, precios y
 * total tal como se calcularon al crear, sin recalcular en el cliente.
 *
 * Acciones (admin): transición de estado con confirmación (RNF-P6-01),
 * enlace de WhatsApp (UC-06) y edición (solo estado nuevo). Confirmar
 * descuenta stock atómicamente: un 409 no cambió nada.
 */
interface OrderDetailPageProps {
  orderId: string;
}

export function OrderDetailPage({ orderId }: OrderDetailPageProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [whatsapp, setWhatsApp] = useState<WhatsAppLink | null>(null);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingTransition, setPendingTransition] = useState<OrderStatus | null>(null);

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    ordersService
      .getDetail(orderId)
      .then((d) => {
        if (!cancelled) setOrder(d);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "No se pudo cargar el pedido");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  const runTransition = useCallback(
    async (status: OrderStatus) => {
      if (!order) return;
      setActionLoading(true);
      setActionError(null);
      try {
        const updated = await ordersService.changeStatus(order.id, status);
        setOrder(updated);
      } catch (e) {
        setActionError(e instanceof Error ? e.message : "La transición falló");
      } finally {
        setActionLoading(false);
        setPendingTransition(null);
      }
    },
    [order],
  );

  const sendWhatsApp = useCallback(async () => {
    if (!order) return;
    setWhatsappLoading(true);
    try {
      setWhatsApp(await ordersService.whatsapp(order.id));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "No se pudo generar el enlace");
    } finally {
      setWhatsappLoading(false);
    }
  }, [order]);

  if (loading) {
    return (
      <Stack gap={3} maxW="720px">
        <Skeleton h="32px" />
        <Skeleton h="96px" />
        <Skeleton h="160px" />
      </Stack>
    );
  }

  if (error || !order) {
    return (
      <Alert.Root status="error" maxW="640px">
        <Alert.Content>
          <Alert.Title>No se pudo cargar el pedido</Alert.Title>
          <Alert.Description>{error ?? "Pedido no encontrado"}</Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  const nextStatuses = isAdmin ? ALLOWED_TRANSITIONS[order.status] : [];

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <HStack gap={3} align="center">
          <Heading fontSize="2xl">Pedido {order.id.slice(0, 8)}</Heading>
          <Badge colorPalette={STATUS_COLORS[order.status]} variant="subtle">
            {ORDER_STATUS_LABELS[order.status]}
          </Badge>
        </HStack>
        <Button variant="ghost" asChild>
          <NextLink href="/pedidos">Volver al listado</NextLink>
        </Button>
      </Flex>

      {/* Cliente + datos */}
      <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={4}>
        <VStack align="start" gap={2}>
          <Text fontWeight="600">{order.customer.name}</Text>
          <Text color="fg.muted" fontSize="sm">{order.customer.phone}</Text>
          <HStack gap={4} fontSize="sm" color="fg.muted" wrap="wrap">
            <Text>Fecha del pedido: {order.date}</Text>
            <Text>
              Margen: {order.margin_pct == null ? "margen del negocio" : formatPct(order.margin_pct)}
            </Text>
            {order.whatsapp_sent_at ? (
              <Text>WhatsApp enviado: {order.whatsapp_sent_at}</Text>
            ) : null}
          </HStack>
        </VStack>
      </Box>

      {/* Snapshot de líneas */}
      <Box borderWidth="1px" borderColor="gray.200" rounded="md" overflowX="auto">
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr>
              {["Producto", "Cant.", "Porc.", "Nota", "Base", "Margen", "Final", "Ajuste"].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: "left",
                    padding: "10px 14px",
                    borderBottom: "1px solid #e5e5e5",
                    fontWeight: 600,
                    color: "#525252",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.product_id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "10px 14px", fontWeight: 500 }}>{item.product_name}</td>
                <td style={{ padding: "10px 14px" }}>{item.qty}</td>
                <td style={{ padding: "10px 14px" }}>{item.portions}</td>
                <td style={{ padding: "10px 14px", maxWidth: "220px" }}>{item.note}</td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.price.base)}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.price.margin_pct)}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.price.final)}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.rounded)}
                </td>
                <td style={{ display: "none" }} aria-hidden="true" />
              </tr>
            ))}
          </tbody>
        </table>
      </Box>

      {/* Líneas de costo + faltantes del snapshot */}
      {order.items.map((item) =>
        item.lines.length > 0 || item.missing_ingredients.length > 0 ? (
          <Box
            key={`lines-${item.product_id}`}
            borderWidth="1px"
            borderColor="gray.100"
            rounded="md"
            p={3}
          >
            <Text fontSize="sm" fontWeight="600" mb={2}>
              {item.product_name} — líneas de costo
            </Text>
            {item.lines.length > 0 ? (
              <Stack gap={1}>
                {item.lines.map((line) => (
                  <HStack key={line.ingredient_id} justify="space-between" fontSize="sm">
                    <Text color={line.is_missing ? "red.600" : "fg.muted"}>
                      {line.ingredient_name} · {line.qty} {line.unit}
                      {line.is_missing ? " (sin precio)" : ""}
                    </Text>
                    <Text fontVariantNumeric="tabular-nums">{formatCents(line.cost)}</Text>
                  </HStack>
                ))}
              </Stack>
            ) : (
              <Text fontSize="sm" color="fg.muted">
                Sin líneas de costo (producto sin precio completo).
              </Text>
            )}
            {item.missing_ingredients.length > 0 ? (
              <Alert.Root status="warning" mt={2}>
                <Alert.Content>
                  <Alert.Description fontSize="sm">
                    Insumos sin precio al momento de crear:{" "}
                    {item.missing_ingredients.join(", ")}.
                  </Alert.Description>
                </Alert.Content>
              </Alert.Root>
            ) : null}
          </Box>
        ) : null,
      )}

      {/* Total */}
      <HStack justify="flex-end" gap={2}>
        <Text fontWeight="600">Total</Text>
        <Text fontWeight="700" fontSize="xl" fontVariantNumeric="tabular-nums">
          {formatCents(order.total)}
        </Text>
      </HStack>

      {/* Acciones admin */}
      {isAdmin ? (
        <HStack gap={3} wrap="wrap">
          {order.status === "nuevo" ? (
            <Button variant="outline" asChild>
              <NextLink href={`/pedidos/${order.id}/editar`}>Editar</NextLink>
            </Button>
          ) : null}
          {nextStatuses.map((s) => (
            <Button
              key={s}
              colorPalette={s === "cancelado" ? "red" : "brand"}
              variant={s === "cancelado" ? "outline" : "solid"}
              loading={actionLoading && pendingTransition === s}
              onClick={() => setPendingTransition(s)}
            >
              Pasar a {ORDER_STATUS_LABELS[s].toLowerCase()}
            </Button>
          ))}
          <Button
            variant="outline"
            loading={whatsappLoading}
            onClick={() => {
              void sendWhatsApp();
            }}
          >
            WhatsApp
          </Button>
        </HStack>
      ) : null}

      {whatsapp ? (
        <Alert.Root status="success">
          <Alert.Content>
            <Alert.Title>Enlace de WhatsApp</Alert.Title>
            <HStack mt={2} gap={3} wrap="wrap">
              <Text fontSize="sm" color="fg.muted" maxW="480px" overflowWrap="anywhere">
                {whatsapp.message}
              </Text>
              <Button size="sm" colorPalette="brand" asChild>
                <a href={whatsapp.url} target="_blank" rel="noreferrer">
                  Abrir chat
                </a>
              </Button>
            </HStack>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {actionError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Description>{actionError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {/* Confirmación de transición (Dialog v3, mismo patrón que F5) */}
      <Dialog.Root
        open={pendingTransition !== null}
        onOpenChange={(e) => {
          if (!e.open) setPendingTransition(null);
        }}
        role="alertdialog"
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>
                ¿Pasar el pedido a {pendingTransition ? ORDER_STATUS_LABELS[pendingTransition] : ""}?
              </Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>
                {pendingTransition === "confirmado"
                  ? "Al confirmar se descuenta stock de los insumos. Si no alcanza, el pedido queda sin cambios."
                  : pendingTransition === "cancelado"
                    ? "Al cancelar desde confirmado se devuelve el stock que se había descontado."
                    : "Esta acción no se puede deshacer desde la interfaz."}
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" onClick={() => setPendingTransition(null)}>
                Cancelar
              </Button>
              <Button
                colorPalette={pendingTransition === "cancelado" ? "red" : "brand"}
                loading={actionLoading}
                onClick={() => {
                  if (pendingTransition) void runTransition(pendingTransition);
                }}
              >
                Confirmar
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Flex>
  );
}
