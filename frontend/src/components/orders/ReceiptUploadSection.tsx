"use client";

import { Alert, Box, Button, Stack, Status, Text } from "@chakra-ui/react";
import { useState } from "react";
import { deriveReceiptState } from "@/lib/receiptStatus";
import type { OrderDetail } from "@/types/orders";
import { ReceiptUploadDialog } from "./ReceiptUploadDialog";

export function ReceiptUploadSection({
  order,
  onUpdated,
}: {
  order: OrderDetail;
  onUpdated?: (order: OrderDetail) => void;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const state = deriveReceiptState(order);

  if (state === "none" || state === "not_applicable") return null;

  if (state === "pending_review") {
    return (
      <Box borderWidth="1px" borderColor="border.muted" rounded="md" p={4}>
        <Status.Root colorPalette="brand">
          <Status.Indicator />
          <Text fontWeight="semibold">Comprobante en verificación</Text>
        </Status.Root>
        <Text fontSize="sm" color="fg.muted" mt={1}>
          La verificación es manual y toma hasta 24 horas.
        </Text>
      </Box>
    );
  }

  return (
    <Stack gap={3}>
      <Alert.Root status="warning">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Description>
            Para confirmar su pedido, por favor suba el comprobante de la
            transferencia.
          </Alert.Description>
        </Alert.Content>
      </Alert.Root>
      <Button
        colorPalette="brand"
        onClick={() => setDialogOpen(true)}
        alignSelf="flex-start"
      >
        Subir comprobante
      </Button>
      <ReceiptUploadDialog
        orderId={order.id}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onUploaded={(updated) => onUpdated?.(updated)}
      />
    </Stack>
  );
}
