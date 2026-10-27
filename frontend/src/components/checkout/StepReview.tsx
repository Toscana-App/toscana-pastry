"use client";

/** Paso 5 — Revisar y confirmar (RF-P11-08 / UC-08).

El pedido se crea SOLO acá (POST /orders, C6). 409 order_window_closed →
banner + CTA deshabilitado. Éxito → confirmación con código de pedido.
*/

import {
  Alert,
  Box,
  Button,
  Code,
  DataList,
  Flex,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useState } from "react";
import { PaymentCard } from "@/components/checkout/PaymentCard";
import { trackEvent } from "@/lib/analytics";
import { toaster } from "@/lib/toaster";
import { createPortalOrder } from "@/services/ordersService";
import {
  CartResponse,
  OrderDetail,
  PortalOrderPayload,
} from "@/types/orders";
import {
  AddressSelection,
  ContactData,
  DeliveryData,
  PaymentData,
} from "./checkoutTypes";

function formatDate(value: string): string {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  return d.toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function StepReview({
  contact,
  address,
  delivery,
  payment,
  cart,
  onBack,
  onConfirmed,
}: {
  contact: ContactData;
  address: AddressSelection | null;
  delivery: DeliveryData;
  payment: PaymentData;
  cart: CartResponse;
  onBack: () => void;
  onConfirmed: (order: OrderDetail) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [windowClosed, setWindowClosed] = useState(false);

  const confirm = async () => {
    if (windowClosed || submitting) return;
    setSubmitting(true);
    try {
      const payload: PortalOrderPayload = {
        items: cart.items.map((item) => ({
          product_id: item.product_id,
          product_name: item.name,
          quantity: item.qty,
          unit_price: item.unit_price,
          portion_note: "",
        })),
        date: delivery.date,
        delivery_mode: delivery.delivery_mode,
        delivery_address:
          delivery.delivery_mode === "delivery" ? (address?.line ?? "") : null,
        payment_method: payment.payment_method,
        coupon_code: cart.coupon?.code ?? null,
      };
      const order = await createPortalOrder(payload);
      trackEvent("order_confirmed", {
        order_code: order.code,
        payment_method: order.payment_method,
        delivery_mode: order.delivery_mode,
        total: order.total,
      });
      onConfirmed(order);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (message === "order_window_closed") {
        setWindowClosed(true);
      } else {
        toaster.create({
          title: "No se pudo crear el pedido",
          description: message || "Intentá de nuevo",
          type: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (windowClosed) {
    return (
      <Stack gap={4} maxW="md">
        <Alert.Root status="error">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>La ventana de pedidos está cerrada</Alert.Title>
            <Alert.Description>
              Por ahora no podemos aceptar pedidos. Volvé más tarde; el
              enlace &quot;Nuevo pedido&quot; se habilitará solo.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
        <Flex justify="flex-end">
          <Button variant="outline" onClick={onBack}>
            Volver
          </Button>
        </Flex>
      </Stack>
    );
  }

  return (
    <Stack gap={4} maxW="md">
      <Box
        borderWidth="1px"
        borderColor="border.muted"
        rounded="md"
        p={4}
      >
        <DataList.Root columns={{ base: 1, md: 2 }} gap={2}>
          <DataList.Item>
            <DataList.ItemLabel>Contacto</DataList.ItemLabel>
            <DataList.ItemValue>
              {contact.name}
              <Text fontSize="sm" color="fg.muted">
                {contact.phone} · {contact.email}
              </Text>
            </DataList.ItemValue>
          </DataList.Item>

          <DataList.Item>
            <DataList.ItemLabel>Dirección</DataList.ItemLabel>
            <DataList.ItemValue>
              {delivery.delivery_mode === "delivery"
                ? address?.line || "—"
                : "Retiro en tienda"}
            </DataList.ItemValue>
          </DataList.Item>

          <DataList.Item>
            <DataList.ItemLabel>Entrega</DataList.ItemLabel>
            <DataList.ItemValue>
              {formatDate(delivery.date)}
              <Text fontSize="sm" color="fg.muted">
                {delivery.delivery_mode === "delivery"
                  ? "A domicilio"
                  : "Retiro"}
              </Text>
            </DataList.ItemValue>
          </DataList.Item>

          <DataList.Item>
            <DataList.ItemLabel>Pago</DataList.ItemLabel>
            <DataList.ItemValue>
              {payment.payment_method === "mercadopago"
                ? "Mercado Pago (online)"
                : "Efectivo en la entrega"}
            </DataList.ItemValue>
          </DataList.Item>
        </DataList.Root>
      </Box>

      <Box
        borderWidth="1px"
        borderColor="border.muted"
        rounded="md"
        p={4}
      >
        <Stack gap={2}>
          {cart.items.map((item) => (
            <Flex key={item.product_id} justify="space-between" gap={2}>
              <Text fontSize="sm">
                {item.name} × {item.qty}
              </Text>
              <Text fontSize="sm">${item.total}</Text>
            </Flex>
          ))}
          {cart.coupon && (
            <Flex justify="space-between" gap={2}>
              <Text fontSize="sm" color="green.600">
                Cupón {cart.coupon.code}
              </Text>
              <Text fontSize="sm" color="green.600">
                −${cart.discount_amount}
              </Text>
            </Flex>
          )}
          <Flex justify="space-between" borderTopWidth="1px" pt={2}>
            <Text fontWeight="semibold">Total</Text>
            <Text fontWeight="bold">${cart.total}</Text>
          </Flex>
        </Stack>
      </Box>

      <Flex justify="space-between" gap={3}>
        <Button variant="outline" onClick={onBack} disabled={submitting}>
          Volver
        </Button>
        <Button
          colorPalette="brand"
          onClick={confirm}
          loading={submitting}
          disabled={windowClosed}
        >
          Confirmar pedido
        </Button>
      </Flex>
    </Stack>
  );
}

/** Post-order confirmation screen (UC-08: order code). */
export function CheckoutSuccess({
  order,
}: {
  order: OrderDetail;
}) {
  return (
    <Stack gap={4} maxW="md" align="center" textAlign="center" py={8}>
      <Text fontSize="2xl" fontWeight="bold" color="green.600">
        ¡Pedido recibido!
      </Text>
      <Text color="fg.muted">
        Tu código de pedido es
      </Text>
      <Code fontSize="lg" px={3} py={1}>
        {order.code}
      </Code>
      <Text fontSize="sm" color="fg.muted">
        {order.payment_method === "cash"
          ? "Recordá: pagás en efectivo en la entrega o el retiro."
          : "El pago se procesa online; podés dar seguimiento en Mis pedidos."}
      </Text>
      <Box w="100%">
        <PaymentCard order={order} />
      </Box>
    </Stack>
  );
}
