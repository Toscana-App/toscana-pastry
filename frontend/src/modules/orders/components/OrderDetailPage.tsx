"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { ApiError } from "@/lib/api";
import { invoicesService } from "@/modules/invoicing/service";
import { InvoiceDialog } from "@/modules/invoicing/components/InvoiceDialog";
import { InvoiceResult } from "@/modules/invoicing/components/InvoiceResult";
import {
  isFacturable,
  type Invoice,
  type InvoiceComprobante,
  type InvoiceCreatePayload,
  type InvoiceItemPayload,
} from "@/modules/invoicing/types";
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

/** Mensajes amigables para los errores de emisión de factura (sin stack traces). */
function invoiceErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 409) return "El pedido ya tiene comprobante.";
    if (e.status === 503)
      return "Facturación no configurada. Revisá la configuración del emisor.";
  }
  return e instanceof Error ? e.message : "No se pudo emitir la factura";
}

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
  const [invoiceOpen, setInvoiceOpen] = useState(false);
  const [issued, setIssued] = useState<Invoice | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [invoiceError, setInvoiceError] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

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

  const markPaid = useCallback(async () => {
    if (!order) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const result = await ordersService.markPaid(order.id);
      setOrder({ ...order, paid: result.paid });
    } catch (e) {
      setActionError(
        e instanceof Error && e.message.includes("409")
          ? "El pedido ya está marcado como pagado."
          : e instanceof Error
            ? e.message
            : "No se pudo marcar como pagado",
      );
    } finally {
      setActionLoading(false);
    }
  }, [order]);

  const comprobante = useMemo<InvoiceComprobante | null>(() => {
    if (issued != null) {
      return {
        punto_venta: issued.punto_venta,
        numero: issued.numero,
        cae: issued.cae,
        cae_vto: issued.cae_vto,
        pdf_url: issued.pdf_url,
        id: issued.id,
      };
    }
    if (order?.invoice != null) {
      return {
        punto_venta: null,
        numero: order.invoice.numero,
        cae: order.invoice.cae,
        cae_vto: order.invoice.cae_vto,
        pdf_url: order.invoice.pdf_url,
      };
    }
    return null;
  }, [issued, order]);

  const canInvoice =
    isAdmin &&
    order != null &&
    comprobante == null &&
    isFacturable(order.status, order.paid);

  const invoiceItems: InvoiceItemPayload[] = useMemo(
    () =>
      order
        ? order.items.map((it) => ({
            descripcion: it.note
              ? `${it.product_name} — ${it.note}`
              : it.product_name,
            cantidad: it.qty,
            precio_unit: it.qty > 0 ? Math.round(it.rounded / it.qty) : 0,
          }))
        : [],
    [order],
  );

  const issueInvoice = useCallback(
    async (payload: InvoiceCreatePayload) => {
      setIssuing(true);
      setInvoiceError(null);
      try {
        const inv = await invoicesService.create(payload);
        setIssued(inv);
        setInvoiceOpen(false);
      } catch (e) {
        setInvoiceError(invoiceErrorMessage(e));
      } finally {
        setIssuing(false);
      }
    },
    [],
  );

  const downloadInvoicePdf = useCallback(async () => {
    if (!comprobante) return;
    setDownloadingPdf(true);
    try {
      await invoicesService.downloadPdf(comprobante.pdf_url);
    } catch (e) {
      setInvoiceError(
        e instanceof Error ? e.message : "No se pudo descargar el PDF",
      );
    } finally {
      setDownloadingPdf(false);
    }
  }, [comprobante]);

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
          <Badge
            colorPalette={order.paid ? "green" : "orange"}
            variant="subtle"
          >
            {order.paid ? "Pagado" : "Sin pagar"}
          </Badge>
        </HStack>
        <Button variant="ghost" asChild>
          <NextLink href="/pedidos">Volver al listado</NextLink>
        </Button>
      </Flex>

      {}
      <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
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

      {}
      <Box borderWidth="1px" borderColor="border" rounded="md" overflowX="auto">
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr>
              {["Producto", "Cant.", "Porc.", "Nota", "Base", "Margen", "Final", "Ajuste"].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: "left",
                    padding: "10px 14px",
                    borderBottom: "1px solid var(--chakra-colors-border)",
                    fontWeight: 600,
                    color: "var(--chakra-colors-fg-muted)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {order.items.map((item, idx) => (
              <tr key={`${item.product_id}-${idx}`} style={{ borderBottom: "1px solid var(--chakra-colors-border-muted)" }}>
                <td style={{ padding: "10px 14px", fontWeight: 500 }}>{item.product_name}</td>
                <td style={{ padding: "10px 14px" }}>{item.qty}</td>
                <td style={{ padding: "10px 14px" }}>{item.portions}</td>
                <td style={{ padding: "10px 14px", maxWidth: "220px" }}>{item.note}</td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.price.base)}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatPct(item.price.margin_pct)}
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

      {}
      {order.items.map((item, idx) =>
        item.lines.length > 0 || item.missing_ingredients.length > 0 ? (
          <Box
            key={`lines-${item.product_id}-${idx}`}
            borderWidth="1px"
            borderColor="border.muted"
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
                    <Text color={line.is_missing ? "red.fg" : "fg.muted"}>
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

      {}
      <HStack justify="flex-end" gap={2}>
        <Text fontWeight="600">Total</Text>
        <Text fontWeight="700" fontSize="xl" fontVariantNumeric="tabular-nums">
          {formatCents(order.total)}
        </Text>
      </HStack>

      {}
      {isAdmin ? (
        <HStack gap={3} wrap="wrap">
          {order.status === "nuevo" ? (
            <Button variant="outline" asChild>
              <NextLink href={`/pedidos/${order.id}/editar`}>Editar</NextLink>
            </Button>
          ) : null}
          {order.paid ? (
            <Text fontSize="sm" color="fg.muted" alignSelf="center">
              Pago registrado
            </Text>
          ) : (
            <Button
              variant="outline"
              colorPalette="green"
              loading={actionLoading}
              onClick={() => {
                void markPaid();
              }}
            >
              Marcar pagado
            </Button>
          )}
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
          {canInvoice ? (
            <Button variant="outline" onClick={() => setInvoiceOpen(true)}>
              Facturar
            </Button>
          ) : null}
        </HStack>
      ) : null}

      {isAdmin && comprobante != null ? (
        <InvoiceResult
          comprobante={comprobante}
          impTotal={issued?.imp_total ?? null}
          downloading={downloadingPdf}
          onDownload={() => {
            void downloadInvoicePdf();
          }}
        />
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

      {}
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

      <InvoiceDialog
        open={invoiceOpen}
        onOpenChange={(o) => setInvoiceOpen(o)}
        orderId={order.id}
        orderCode={order.id.slice(0, 8)}
        total={order.total}
        receptorNombreInicial={order.customer.name}
        items={invoiceItems}
        issuing={issuing}
        error={invoiceError}
        onConfirm={(payload) => {
          void issueInvoice(payload);
        }}
      />
    </Flex>
  );
}
