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

type OrderState = Exclude<PublicDelivery["state"], "expired">;

type View =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; delivery: PublicDelivery };

const STATUS_TONE: Record<
  OrderState,
  { bg: string; border: string; fg: string; dot: string }
> = {
  active: {
    bg: "warning.subtle",
    border: "warning.border",
    fg: "fg.warning",
    dot: "orange.solid",
  },
  delivered: {
    bg: "green.subtle",
    border: "green.emphasized",
    fg: "green.fg",
    dot: "green.solid",
  },
  cancelled: {
    bg: "red.subtle",
    border: "red.border",
    fg: "fg.error",
    dot: "red.solid",
  },
};

function StatusBanner({ state, label }: { state: OrderState; label: string }) {
  const tone = STATUS_TONE[state];
  return (
    <Box
      as="div"
      role="status"
      w="full"
      display="flex"
      alignItems="center"
      gap={3}
      borderWidth="1px"
      borderColor={tone.border}
      bg={tone.bg}
      rounded="lg"
      px={4}
      py={3}
    >
      <Box
        aria-hidden
        flexShrink="0"
        width="10px"
        height="10px"
        rounded="full"
        bg={tone.dot}
      />
      <Text fontSize="md" fontWeight="700" color={tone.fg}>
        {label}
      </Text>
    </Box>
  );
}

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
              {view.delivery.state !== "expired" ? (
                <StatusBanner
                  state={view.delivery.state}
                  label={view.delivery.status_label}
                />
              ) : null}
              {view.delivery.items && view.delivery.items.length > 0 ? (
                <Box
                  w="full"
                  borderTopWidth="1px"
                  borderColor="border"
                  pt={4}
                >
                  <Text fontSize="sm" color="fg.muted" fontWeight="600" mb={2}>
                    Tu pedido
                  </Text>
                  <Stack gap={2} w="full">
                    {view.delivery.items.map((item, index) => (
                      <Box
                        key={`${item.name}-${index}`}
                        display="flex"
                        justifyContent="space-between"
                        gap={4}
                      >
                        <Text lineClamp={2}>{item.name}</Text>
                        <Text
                          as="span"
                          color="fg.muted"
                          fontVariantNumeric="tabular-nums"
                          whiteSpace="nowrap"
                        >
                          × {item.quantity}
                        </Text>
                      </Box>
                    ))}
                  </Stack>
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
