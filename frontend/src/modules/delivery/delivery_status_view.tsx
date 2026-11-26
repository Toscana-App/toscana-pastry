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

const UNAVAILABLE = "Este enlace no está disponible";

type View =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; delivery: PublicDelivery };

function messageFor(cause: unknown): string {
  return cause instanceof Error && cause.message ? cause.message : UNAVAILABLE;
}

export function DeliveryStatusView({ token }: DeliveryStatusViewProps) {
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<View>(() =>
    token ? { kind: "loading" } : { kind: "error", message: UNAVAILABLE },
  );

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    // El primer setState ocurre después del await: el efecto no encadena
    // renders (react-hooks/set-state-in-effect). Desmontar o cambiar de token
    // aborta la request y descarta la respuesta tardía.
    void (async () => {
      try {
        const delivery = await fetchPublicDelivery(token, controller.signal);
        if (!controller.signal.aborted) setView({ kind: "ready", delivery });
      } catch (cause) {
        if (controller.signal.aborted) return;
        setView({ kind: "error", message: messageFor(cause) });
      }
    })();
    return () => controller.abort();
  }, [token, attempt]);

  const retry = useCallback(() => {
    setView({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, []);

  return (
    <Box minH="100dvh" bg="bg.subtle" py={{ base: 10, md: 20 }}>
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
          {view.kind === "loading" ? (
            <Stack gap={4}>
              <Skeleton height="8" width="70%" />
              <Skeleton height="4" width="40%" />
              <Skeleton height="4" width="55%" />
            </Stack>
          ) : view.kind === "error" ? (
            <Stack gap={5} align="flex-start">
              <Heading
                as="h1"
                fontSize={{ base: "2xl", md: "3xl" }}
                css={{ textWrap: "balance" }}
              >
                No pudimos abrir este enlace
              </Heading>
              <Text color="fg.muted">{view.message}</Text>
              <Button variant="outline" onClick={retry}>
                Reintentar
              </Button>
            </Stack>
          ) : (
            <Stack gap={5} align="flex-start">
              <Heading
                as="h1"
                fontSize={{ base: "2xl", md: "4xl" }}
                lineHeight="1.15"
                css={{ textWrap: "balance" }}
              >
                {view.delivery.message}
              </Heading>
              {view.delivery.order_code ? (
                <Text fontSize="lg" fontWeight="medium">
                  Pedido{" "}
                  <Text as="span" fontFamily="mono" color="fg.muted">
                    {view.delivery.order_code}
                  </Text>
                </Text>
              ) : null}
              {view.delivery.state === "active" ? (
                <Box
                  borderWidth="1px"
                  borderColor="border"
                  rounded="md"
                  px={3}
                  py={1}
                  fontSize="sm"
                  color="fg.muted"
                >
                  {view.delivery.status_label}
                </Box>
              ) : null}
              {view.delivery.state === "delivered" ? (
                <Text color="fg.muted">
                  Gracias por elegir Toscana. Podés cerrar esta página.
                </Text>
              ) : null}
            </Stack>
          )}
        </Box>
      </Container>
    </Box>
  );
}
