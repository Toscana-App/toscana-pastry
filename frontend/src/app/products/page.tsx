"use client";

import { Suspense } from "react";
import { Container, Flex, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";
import { CatalogSkeleton } from "@/components/ui/skeleton";

export default function ProductsPage() {
  return (
    <Container py={10} maxW="5xl">
      <Flex direction="column" gap={6}>
        <Heading as="h1" size="3xl">
          Lista de precios
        </Heading>
        <Suspense fallback={<CatalogSkeleton />}>
          <ProductsCatalog />
        </Suspense>
      </Flex>
    </Container>
  );
}
