"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Button, Dialog, HStack, Stack, Text } from "@chakra-ui/react";
import {
  copyToClipboard,
  fetchDeliveryLink,
  fetchDeliveryQrObjectUrl,
} from "@/services/deliveryService";

const TERMINAL_STATUSES = new Set(["delivered", "cancelled"]);

interface DeliveryQrSectionProps {
  orderId: string;
  orderStatus: string;
}

export function DeliveryQrSection({
  orderId,
  orderStatus,
}: DeliveryQrSectionProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkUrl, setLinkUrl] = useState<string | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"ok" | "error" | null>(null);
  const qrRef = useRef<string | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const releaseQr = useCallback(() => {
    if (qrRef.current) {
      URL.revokeObjectURL(qrRef.current);
      qrRef.current = null;
    }
    setQrUrl(null);
  }, []);

  useEffect(
    () => () => {
      if (qrRef.current) URL.revokeObjectURL(qrRef.current);
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

  if (TERMINAL_STATUSES.has(orderStatus)) return null;

  const openQr = async () => {
    setLoading(true);
    setError(null);
    try {
      const link = await fetchDeliveryLink(orderId);
      const objectUrl = await fetchDeliveryQrObjectUrl(orderId);
      qrRef.current = objectUrl;
      setLinkUrl(link.url);
      setQrUrl(objectUrl);
      setOpen(true);
    } catch (cause) {
      setError(
        cause instanceof Error && cause.message
          ? cause.message
          : "No se pudo generar el QR de entrega",
      );
    } finally {
      setLoading(false);
    }
  };

  const copyLink = async () => {
    if (!linkUrl) return;
    const copied = await copyToClipboard(linkUrl);
    setCopyState(copied ? "ok" : "error");
    if (copyTimer.current) clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => setCopyState(null), 2000);
  };

  return (
    <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
      <Stack gap={3} align="flex-start">
        <Text fontWeight="600">QR de entrega</Text>
        <Text fontSize="sm" color="fg.muted">
          El cliente lo escanea para ver el estado del pedido. Deja de mostrar
          datos apenas el pedido se entrega.
        </Text>
        <Button variant="outline" size="sm" loading={loading} onClick={() => void openQr()}>
          Ver QR de entrega
        </Button>
        {error ? (
          <Text fontSize="sm" color="fg.error">
            {error}
          </Text>
        ) : null}
      </Stack>

      <Dialog.Root
        open={open}
        onOpenChange={(details) => {
          if (!details.open) {
            setOpen(false);
            setCopyState(null);
            releaseQr();
          }
        }}
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>QR de entrega</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Stack gap={4} align="flex-start">
                {qrUrl ? (
                  <img
                    src={qrUrl}
                    alt="Código QR de entrega del pedido"
                    width={220}
                    height={220}
                  />
                ) : null}
                <HStack gap={2} wrap="wrap">
                  <Button size="sm" variant="outline" onClick={() => void copyLink()}>
                    Copiar enlace
                  </Button>
                  {qrUrl ? (
                    <Button size="sm" variant="ghost" asChild>
                      <a href={qrUrl} download="entrega-pedido.svg">
                        Descargar QR
                      </a>
                    </Button>
                  ) : null}
                </HStack>
                <Text
                  role="status"
                  fontSize="sm"
                  color={copyState === "error" ? "fg.error" : "fg.muted"}
                >
                  {copyState === "ok"
                    ? "Enlace copiado"
                    : copyState === "error"
                      ? "No pudimos copiar. Seleccioná el enlace y copialo a mano."
                      : ""}
                </Text>
                {linkUrl ? (
                  <Text fontSize="xs" color="fg.subtle" wordBreak="break-all">
                    {linkUrl}
                  </Text>
                ) : null}
              </Stack>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cerrar
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Box>
  );
}
