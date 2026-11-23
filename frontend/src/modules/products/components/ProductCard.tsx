"use client";

import { Badge, Flex, FormatNumber, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { centsToPesos } from "@/lib/format";
import type { ProductListItem } from "../types";

const MAX_VISIBLE_TAGS = 2;

interface ProductCardProps {
  product: ProductListItem;
}

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
        borderColor="border"
        rounded="lg"
        p={4}
        h="full"
        transition="border-color 120ms ease-out"
        _hover={{ borderColor: "brand.solid" }}
        _focusWithin={{
          outline: "2px solid",
          outlineColor: "brand.focusRing",
          outlineOffset: "2px",
        }}
      >
        <Flex align="flex-start" justify="space-between" gap={3}>
          <Text fontSize="lg" fontWeight="500" lineClamp={2} overflowWrap="anywhere" minW={0}>
            {product.name}
          </Text>
          {product.complete && product.price_final !== null ? (
            <Text
              fontSize="lg"
              fontWeight="600"
              fontVariantNumeric="tabular-nums"
              whiteSpace="nowrap"
            >
              <FormatNumber value={centsToPesos(product.price_final)} style="currency" currency="ARS" />
            </Text>
          ) : (
            <Badge colorPalette="orange" size="sm" flexShrink={0}>
              sin precio
            </Badge>
          )}
        </Flex>
        <Flex align="center" gap={2}>
          <Text fontSize="xs" color="fg.muted">
            {product.category}
          </Text>
          <Badge
            size="sm"
            variant="subtle"
            colorPalette={product.available ? "green" : "gray"}
          >
            {product.available ? "En tienda" : "Oculto"}
          </Badge>
        </Flex>
        {product.tags.length > 0 ? (
          <Flex gap={1.5} wrap="wrap">
            {product.tags.slice(0, MAX_VISIBLE_TAGS).map((tag) => (
              <Badge key={tag} size="xs" variant="outline" colorPalette="gray">
                {tag}
              </Badge>
            ))}
            {product.tags.length > MAX_VISIBLE_TAGS ? (
              <Text fontSize="xs" color="fg.muted">
                +{product.tags.length - MAX_VISIBLE_TAGS}
              </Text>
            ) : null}
          </Flex>
        ) : null}
      </Flex>
    </NextLink>
  );
}
