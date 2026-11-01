"use client";

import { Badge, Flex, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { formatCents } from "@/lib/format";
import type { ProductListItem } from "../types";

interface ProductCardProps {
  product: ProductListItem;
}

/**
 * Card del listado P3 (RF-P3: nombre, categoría y precio final).
 *
 * RNF-P3-03: interactiva pero sin scale/translate — el hover solo fortalece
 * el outline, y el focus de teclado es visible. El precio usa tabular-nums
 * para que las columnas de la grilla queden alineadas.
 *
 * Producto incompleto (RF-P3-05): badge "sin precio" en lugar del monto; el
 * detalle explica qué insumos lo bloquean.
 */
export function ProductCard({ product }: ProductCardProps) {
  return (
    <NextLink
      href={`/productos/${product.id}`}
      style={{ display: "block", borderRadius: "0.5rem" }}
    >
      <Flex
        direction="column"
        gap={1}
        borderWidth="1px"
        borderColor="gray.200"
        rounded="lg"
        p={4}
        h="full"
        transition="border-color 120ms ease-out"
        _hover={{ borderColor: "brand.600" }}
        _focusWithin={{
          outline: "2px solid var(--chakra-colors-brand-600)",
          outlineOffset: "2px",
        }}
      >
        <Flex align="flex-start" justify="space-between" gap={3}>
          <Text fontSize="lg" fontWeight="500" lineClamp={2}>
            {product.name}
          </Text>
          {product.complete && product.price_final !== null ? (
            <Text
              fontSize="lg"
              fontWeight="600"
              fontVariantNumeric="tabular-nums"
              whiteSpace="nowrap"
            >
              {formatCents(product.price_final)}
            </Text>
          ) : (
            <Badge colorPalette="orange" size="sm" flexShrink={0}>
              sin precio
            </Badge>
          )}
        </Flex>
        <Text fontSize="xs" color="fg.muted">
          {product.category}
        </Text>
      </Flex>
    </NextLink>
  );
}
