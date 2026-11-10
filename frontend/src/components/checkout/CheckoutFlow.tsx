"use client";


import {
  Box,
  Button,
  Center,
  Container,
  Flex,
  Heading,
  Link,
  Stack,
  Steps,
  Text,
} from "@chakra-ui/react";
import { CheckoutSkeleton } from "@/components/ui/skeleton";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { toaster } from "@/lib/toaster";
import { fetchCart } from "@/services/cartService";
import { fetchMyAddresses } from "@/services/ordersService";
import { Address, CartResponse, OrderDetail } from "@/types/orders";
import { OrderSummaryPanel } from "./OrderSummaryPanel";
import {
  AddressSelection,
  ContactData,
  DeliveryData,
  PaymentData,
  STEP_TITLES,
} from "./checkoutTypes";
import { StepAddress } from "./StepAddress";
import { StepContact } from "./StepContact";
import { StepDelivery } from "./StepDelivery";
import { StepPayment } from "./StepPayment";
import { CheckoutSuccess, StepReview } from "./StepReview";

export function CheckoutFlow() {
  const { user } = useAuth();

  const [cart, setCart] = useState<CartResponse | null>(null);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);

  const [step, setStep] = useState(0);
  const [contact, setContact] = useState<ContactData | null>(null);
  const [address, setAddress] = useState<AddressSelection | null>(null);
  const [delivery, setDelivery] = useState<DeliveryData>({
    date: "",
    delivery_mode: "delivery",
  });
  const [payment, setPayment] = useState<PaymentData>({
    payment_method: "cash",
  });
  const [placed, setPlaced] = useState<OrderDetail | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [cartRes, addrRes] = await Promise.all([
          fetchCart(),
          fetchMyAddresses(),
        ]);
        if (cancelled) return;
        setCart(cartRes);
        setAddresses(addrRes.items ?? []);
      } catch (error) {
        if (cancelled) return;
        toaster.create({
          title: "No se pudo cargar el checkout",
          description:
            error instanceof Error ? error.message : "Intentá de nuevo",
          type: "error",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const goTo = useCallback((target: number) => {
    const clamped = Math.max(0, Math.min(STEP_TITLES.length - 1, target));
    setStep(clamped);
  }, []);

  if (loading) {
    return <CheckoutSkeleton />;
  }

  if (cart === null) {
    return (
      <Center minH="50dvh" py={12}>
        <Text>No se pudo cargar tu carrito.</Text>
      </Center>
    );
  }

  if (placed) {
    return (
      <Container maxW="container.md" py={10}>
        <CheckoutSuccess order={placed} />
      </Container>
    );
  }

  if (cart.items.length === 0) {
    return (
      <Center minH="50dvh" py={12}>
        <Stack gap={4} align="center" textAlign="center">
          <Heading size="lg" textWrap="balance">Tu carrito está vacío</Heading>
          <Text color="fg.muted">
            Agregá productos desde el catálogo para iniciar un pedido.
          </Text>
          <Link href="/" textDecoration="none">
            <Button colorPalette="brand" size="sm">
              Ir al catálogo
            </Button>
          </Link>
        </Stack>
      </Center>
    );
  }

  return (
    <Container maxW="container.lg" py={8}>
      <Flex gap={6} wrap="wrap" align="flex-start">
        <Box flex="1 1 420px" minW="300px">
          <Steps.Root
            step={step + 1}
            count={STEP_TITLES.length}
            onStepChange={(details) => setStep(details.step - 1)}
          >
            <Steps.List>
              {STEP_TITLES.map((title, index) => (
                <Steps.Item key={title} index={index + 1}>
                  <Steps.Indicator />
                  <Steps.Title>{title}</Steps.Title>
                  <Steps.Separator />
                </Steps.Item>
              ))}
            </Steps.List>

            <Stack mt={8} gap={4}>
              {step === 0 && (
                <StepContact
                  userEmail={user?.email ?? null}
                  onNext={(data) => {
                    setContact(data);
                    goTo(1);
                  }}
                />
              )}

              {step === 1 && (
                <StepAddress
                  addresses={addresses}
                  initial={address}
                  onNext={(data) => {
                    setAddress(data);
                    goTo(2);
                  }}
                />
              )}

              {step === 2 && (
                <StepDelivery
                  data={delivery}
                  addressSet={!!address}
                  onChange={setDelivery}
                  onNext={() => goTo(3)}
                  onBack={() => goTo(1)}
                />
              )}

              {step === 3 && (
                <StepPayment
                  value={payment.payment_method}
                  onChange={(method) => setPayment({ payment_method: method })}
                  onNext={() => goTo(4)}
                  onBack={() => goTo(2)}
                />
              )}

              {step === 4 && contact && (
                <StepReview
                  contact={contact}
                  address={address}
                  delivery={delivery}
                  payment={payment}
                  cart={cart}
                  onBack={() => goTo(3)}
                  onConfirmed={setPlaced}
                />
              )}
            </Stack>
          </Steps.Root>
        </Box>

        {}
        <Box flex="1 1 280px" maxW="360px" minW="260px">
          <OrderSummaryPanel cart={cart} />
        </Box>
      </Flex>
    </Container>
  );
}
