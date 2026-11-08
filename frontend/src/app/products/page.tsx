"use client";

import { Container, Flex, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";

/**
 * /products (admin) reuses the portal's catalog component
 * (RNF-P11-03: a single pricing path — the backend).
 */
export default function ProductsPage() {
  return (
    <Container py={10} maxW="5xl">
      <Flex direction="column" gap={6}>
        <Heading size="3xl">Lista de precios</Heading>
        <ProductsCatalog />
      </Flex>
    </Container>
  );
}
