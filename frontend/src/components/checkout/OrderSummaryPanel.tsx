"use client";

/** Checkout side summary (RF-P11-02): items + cart totals. */

import { Badge, Box, Flex, Stack, Text } from "@chakra-ui/react";
import type { CartResponse } from "@/types/orders";

export function OrderSummaryPanel({ cart }: { cart: CartResponse }) {
  return (
    <Box
      borderWidth="1px"
      borderColor="border.muted"
      rounded="md"
      p={4}
      bg="bg"
    >
      <Stack gap={3}>
        <Text fontWeight="semibold">Resumen</Text>

        {cart.items.map((item) => (
          <Flex key={item.product_id} justify="space-between" gap={2}>
            <Text fontSize="sm">
              {item.name} × {item.qty}
            </Text>
            <Text fontSize="sm" whiteSpace="nowrap">
              ${item.total}
            </Text>
          </Flex>
        ))}

        {cart.coupon && (
          <Flex justify="space-between" gap={2}>
            <Flex align="center" gap={2}>
              <Badge colorPalette="green" variant="subtle">
                Cupón {cart.coupon.code}
              </Badge>
            </Flex>
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
  );
}
