"use client";

import { Container, Flex, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";

/**
 * /products (admin) reutiliza el mismo componente de catálogo del portal
 * (RNF-P11-03: una sola vía de cálculo de precios — el backend).
 */
export default function ProductsPage() {
  return (
    <Container py={10} maxW="container.lg">
      <Flex direction="column" gap={6}>
        <Heading size="3xl">Price List</Heading>
        <ProductsCatalog />
      </Flex>
    </Container>
  );
}
