"use client";


import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Input,
  Separator,
  Skeleton,
  Stack,
  Text,
} from "@chakra-ui/react";
import { ShimmerDot } from "@/components/ui/skeleton";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  addCartItem,
  applyCoupon,
  fetchCart,
  removeCartItem,
  removeCoupon,
} from "@/services/cartService";
import { CartResponse } from "@/types/orders";

function CartPage() {
  const router = useRouter();
  const [cart, setCart] = useState<CartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [couponInput, setCouponInput] = useState("");
  const [couponError, setCouponError] = useState<string | null>(null);
  const [loadKey, setLoadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const cartRes = await fetchCart();
        if (cancelled) return;
        setCart(cartRes);
      } catch (error) {
        if (cancelled) return;
        setLoadError(
          error instanceof Error
            ? error.message
            : "No pudimos cargar el carrito"
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [loadKey]);

  const retryLoad = useCallback(() => {
    setLoadError(null);
    setLoading(true);
    setLoadKey((k) => k + 1);
  }, []);

  const changeQty = useCallback(
    async (productId: string, nextQty: number) => {
      if (nextQty < 1 || busy) return;
      setBusy(true);
      try {
        setCart(await addCartItem(productId, nextQty));
      } finally {
        setBusy(false);
      }
    },
    [busy]
  );

  const removeItem = useCallback(
    async (productId: string) => {
      if (busy) return;
      setBusy(true);
      try {
        setCart(await removeCartItem(productId));
      } finally {
        setBusy(false);
      }
    },
    [busy]
  );

  const submitCoupon = useCallback(async () => {
    const code = couponInput.trim();
    if (!code || busy) return;
    setBusy(true);
    setCouponError(null);
    try {
      const next = await applyCoupon(code);
      setCart(next);
      setCouponInput("");
    } catch (error) {
      setCouponError(
        error instanceof Error ? error.message : "Cupón no válido"
      );
    } finally {
      setBusy(false);
    }
  }, [couponInput, busy]);

  const onRemoveCoupon = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      setCart(await removeCoupon());
      setCouponError(null);
    } finally {
      setBusy(false);
    }
  }, [busy]);

  if (loading) {
    return (
      <Card.Root as="main">
        <Card.Body>
          {}
          <Stack gap={3} py={4} role="status">
            <Text srOnly>Cargando tu carrito</Text>
            <Skeleton h="20px" />
            <Skeleton h="20px" />
            <Skeleton h="20px" />
          </Stack>
        </Card.Body>
      </Card.Root>
    );
  }

  if (loadError) {
    return (
      <main>
        <Alert.Root status="error" role="alert" aria-live="polite">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>No pudimos cargar tu carrito</Alert.Title>
            <Alert.Description>{loadError}</Alert.Description>
          </Alert.Content>
          <Button variant="outline" size="sm" onClick={() => retryLoad()}>
            Reintentar
          </Button>
        </Alert.Root>
      </main>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <Card.Root>
        <Card.Body>
          <Stack align="center" gap={3} py={8} textAlign="center">
            <Text fontWeight="semibold">Tu carrito está vacío</Text>
            <Text fontSize="sm" color="fg.muted">
              Agregá productos desde el catálogo para empezar.
            </Text>
            <Button colorPalette="brand" onClick={() => router.push("/")}>
              Ver catálogo
            </Button>
          </Stack>
        </Card.Body>
      </Card.Root>
    );
  }

  return (
    <Card.Root as="main">
      <Card.Body>
        <Stack gap={4}>
          <Heading as="h1" size="md">
            Tu carrito
          </Heading>
          {}
          <Text srOnly role="status">
            {cart.items.length} {cart.items.length === 1 ? "producto" : "productos"} en el carrito
          </Text>

          {cart.audience === "premium" && (
            <Badge colorPalette="brand" variant="solid">
              Cliente premium
            </Badge>
          )}

          <Stack gap={2}>
            {cart.items.map((item) => (
              <Flex key={item.product_id} justify="space-between" align="center" gap={3} flexWrap="wrap">
                <Box minW="0" flex="1">
                  <Text fontWeight="medium">{item.name}</Text>
                  <Text fontSize="sm" color="fg.muted">
                    ${item.unit_price} c/u
                  </Text>
                </Box>
                <Flex align="center" gap={2}>
                  <Button
                    size="xs"
                    variant="outline"
                    aria-label={`Quitar un ${item.name}`}
                    disabled={busy || item.qty <= 1}
                    onClick={() => void changeQty(item.product_id, item.qty - 1)}
                  >
                    −
                  </Button>
                  <Text fontSize="sm" minW="2ch" textAlign="center">
                    {item.qty}
                  </Text>
                  <Button
                    size="xs"
                    variant="outline"
                    aria-label={`Agregar un ${item.name}`}
                    disabled={busy}
                    onClick={() => void changeQty(item.product_id, item.qty + 1)}
                  >
                    +
                  </Button>
                </Flex>
                <Text fontWeight="medium" minW="8ch" textAlign="right">
                  ${item.total}
                </Text>
                <Button
                  size="xs"
                  variant="ghost"
                  colorPalette="red"
                  aria-label={`Quitar ${item.name} del carrito`}
                  disabled={busy}
                  onClick={() => void removeItem(item.product_id)}
                >
                  Quitar
                </Button>
              </Flex>
            ))}
          </Stack>

          <Separator />

          <Box>
            <Stack gap={2}>
              <Text fontSize="sm" fontWeight="medium">
                ¿Tenés un cupón?
              </Text>
              {cart.coupon && (
                <Flex align="center" gap={2} justify="space-between">
                  <Text fontSize="sm">
                    Cupón <strong>{cart.coupon.code}</strong> aplicado
                    {cart.discount_amount !== "0" &&
                      ` (ahorrás $${cart.discount_amount})`}
                  </Text>
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => void onRemoveCoupon()}
                  >
                    Quitar
                  </Button>
                </Flex>
              )}
              {!cart.coupon && (
                <Flex
                  as="form"
                  aria-label="Cupón de descuento"
                  gap={2}
                  onSubmit={(e) => {
                    e.preventDefault();
                    void submitCoupon();
                  }}
                >
                  <Input
                    aria-label="Código de cupón"
                    placeholder="Código de cupón"
                    value={couponInput}
                    onChange={(e) => setCouponInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void submitCoupon();
                    }}
                    disabled={busy}
                  />
                  <Button
                    variant="outline"
                    onClick={() => void submitCoupon()}
                    disabled={busy || couponInput.trim() === ""}
                  >
                    Aplicar
                  </Button>
                </Flex>
              )}
              {couponError && (
                <Alert.Root status="error" py={2}>
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description>{couponError}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
            </Stack>
          </Box>

          <Separator />

          <Flex direction="column" gap={3}>
            <Flex justify="space-between">
              <Text fontWeight="semibold">Total</Text>
              <Text fontWeight="bold" fontSize="lg">
                ${cart.total}
              </Text>
            </Flex>
            <Flex justify="space-between" align="center">
              {busy ? (
                <ShimmerDot size="14px" />
              ) : (
                <Text fontSize="sm" color="fg.muted">
                  Los precios pueden variar según tu audiencia.
                </Text>
              )}
              <Button
                colorPalette="brand"
                disabled={busy}
                onClick={() => router.push("/checkout")}
              >
                Ir a pagar
              </Button>
            </Flex>
          </Flex>
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export default CartPage;
