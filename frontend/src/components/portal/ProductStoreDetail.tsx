"use client";

import { useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Image,
  Text,
  FormatNumber,
} from "@chakra-ui/react";
import { gooeyToast } from "goey-toast";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { roleDefaultDisplayAudience } from "@/lib/roleAudience";
import { addCartItem } from "@/services/cartService";
import { fetchStoreDetail } from "@/services/storeService";
import type { StoreProductDetail } from "@/types/pricing";

export function ProductStoreDetail({ id }: { id: string }) {
  const { user } = useAuth();
  const audience = roleDefaultDisplayAudience(user?.role ?? "");
  const canBuy = isPortalRole(user?.role);

  const [detail, setDetail] = useState<StoreProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchStoreDetail(id, audience);
        if (!cancelled) setDetail(data);
      } catch {
        if (!cancelled) setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, audience]);

  const addToCart = async () => {
    if (!detail || adding) return;
    setAdding(true);
    try {
      await addCartItem(detail.id, 1);
      gooeyToast.success("¡Agregado al carrito!", { description: detail.name });
    } catch (error) {
      gooeyToast.error("¡Ups! No se pudo agregar al carrito", {
        description:
          error instanceof Error ? error.message : "Intenta de nuevo",
      });
    } finally {
      setAdding(false);
    }
  };

  if (loading) {
    return (
      <Box py={12} textAlign="center" role="status" aria-live="polite">
        <Text color="fg.muted">Cargando producto…</Text>
      </Box>
    );
  }

  if (notFound || !detail) {
    return (
      <Box py={12} textAlign="center" flex="1">
        <Heading size="md" mb={2} textWrap="balance">
          Producto no disponible
        </Heading>
        <Text color="fg.muted">
          El producto que buscás no está disponible en este momento.
        </Text>
      </Box>
    );
  }

  return (
    <Flex
      direction={{ base: "column", md: "row" }}
      gap={8}
      align={{ base: "flex-start", md: "center" }}
    >
      <Box boxSize={{ base: "100%", md: "22rem" }} flexShrink={0}>
        {detail.image_url ? (
          <Image
            src={detail.image_url}
            alt={`Imagen de ${detail.name}`}
            htmlWidth={352}
            htmlHeight={352}
            w="100%"
            aspectRatio="1"
            objectFit="cover"
            rounded="lg"
            borderWidth="1px"
            borderColor="border.muted"
          />
        ) : (
          <Box
            w="100%"
            aspectRatio="1"
            bg="bg.muted"
            rounded="lg"
            borderWidth="1px"
            borderColor="border.muted"
          />
        )}
      </Box>

      <Flex direction="column" gap={4} flex="1">
        <Flex direction="column" gap={2}>
          <Badge colorPalette="brand" variant="subtle" alignSelf="flex-start">
            {detail.category}
          </Badge>
          <Heading as="h1" size="2xl" textWrap="balance" overflowWrap="anywhere">
            {detail.name}
          </Heading>
          {detail.description ? (
            <Text color="fg.muted" overflowWrap="anywhere">{detail.description}</Text>
          ) : null}
        </Flex>

        <Flex gap={4} wrap="wrap">
          <Box>
            <Text fontSize="xs" color="fg.muted">
              Rinde
            </Text>
            <Text fontWeight="medium" fontVariantNumeric="tabular-nums">{detail.servings} porciones</Text>
          </Box>
          <Box>
            <Text fontSize="xs" color="fg.muted">
              Preparación
            </Text>
            <Text fontWeight="medium" fontVariantNumeric="tabular-nums">{detail.prep_time_min} min</Text>
          </Box>
        </Flex>

        <Flex
          align="center"
          gap={4}
          borderWidth="1px"
          borderColor="border.muted"
          rounded="md"
          p={4}
          maxW="24rem"
          w="full"
        >
          <Box flex="1">
            <Text fontSize="xs" color="fg.muted">
              Precio
            </Text>
            <Text fontSize="xl" fontWeight="bold" fontVariantNumeric="tabular-nums">
              <FormatNumber value={Number(detail.price)} style="currency" currency="ARS" />
            </Text>
          </Box>
          {canBuy && (
            <Button
              colorPalette="brand"
              disabled={adding}
              onClick={() => void addToCart()}
              aria-label={`Agregar ${detail.name} al carrito`}
            >
              Agregar al carrito
            </Button>
          )}
        </Flex>
      </Flex>
    </Flex>
  );
}
