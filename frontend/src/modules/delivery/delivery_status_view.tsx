"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Box,
  Button,
  Container,
  Heading,
  Skeleton,
  Stack,
  Text,
} from "@chakra-ui/react";
import { fetchPublicDelivery } from "@/services/deliveryService";
import type { PublicDelivery } from "@/types/delivery";

interface DeliveryStatusViewProps {
  token: string;
}

export function DeliveryStatusView({ token }: DeliveryStatusViewProps) {
  const [delivery, setDelivery] = useState<PublicDelivery | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) {
      setError("Este enlace no está disponible");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setDelivery(await fetchPublicDelivery(token));
    } catch (cause) {
      setError(
        cause instanceof Error && cause.message
          ? cause.message
          : "Este enlace no está disponible",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Box as="main" minH="100dvh" bg="bg.subtle" py={{ base: 10, md: 20 }}>
      <Container maxW="lg" px={4}>
        <Box
          bg="bg.panel"
          borderWidth="1px"
          borderColor="border"
          rounded="xl"
          px={{ base: 6, md: 10 }}
          py={{ base: 8, md: 12 }}
          aria-live="polite"
        >
          {loading ? (
            <Stack gap={4}>
              <Skeleton height="8" width="70%" />
              <Skeleton height="4" width="40%" />
              <Skeleton height="4" width="55%" />
            </Stack>
          ) : error ? (
            <Stack gap={5} align="flex-start">
              <Heading
                as="h1"
                fontSize={{ base: "2xl", md: "3xl" }}
                css={{ textWrap: "balance" }}
              >
                No pudimos abrir este enlace
              </Heading>
              <Text color="fg.muted">{error}</Text>
              <Button variant="outline" onClick={() => void load()}>
                Reintentar
              </Button>
            </Stack>
          ) : delivery ? (
            <Stack gap={5} align="flex-start">
              <Heading
                as="h1"
                fontSize={{ base: "2xl", md: "4xl" }}
                lineHeight="1.15"
                css={{ textWrap: "balance" }}
              >
                {delivery.message}
              </Heading>
              {delivery.order_code ? (
                <Text fontSize="lg" fontWeight="medium">
                  Pedido{" "}
                  <Text as="span" fontFamily="mono" color="fg.muted">
                    {delivery.order_code}
                  </Text>
                </Text>
              ) : null}
              {delivery.state === "active" ? (
                <Box
                  borderWidth="1px"
                  borderColor="border"
                  rounded="md"
                  px={3}
                  py={1}
                  fontSize="sm"
                  color="fg.muted"
                >
                  {delivery.status_label}
                </Box>
              ) : null}
              {delivery.state === "delivered" ? (
                <Text color="fg.muted">
                  Gracias por elegir Toscana. Podés cerrar esta página.
                </Text>
              ) : null}
            </Stack>
          ) : null}
        </Box>
      </Container>
    </Box>
  );
}
