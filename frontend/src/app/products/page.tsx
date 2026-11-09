"use client";

import { Suspense } from "react";
import { Box, Container, Flex, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";

export default function ProductsPage() {
  return (
    <Container py={10} maxW="5xl">
      <Flex direction="column" gap={6}>
        <Heading size="3xl">Lista de precios</Heading>
        <Suspense fallback={<Box minH="240px" borderRadius="lg" />}>
          <ProductsCatalog />
        </Suspense>
      </Flex>
    </Container>
  );
}
