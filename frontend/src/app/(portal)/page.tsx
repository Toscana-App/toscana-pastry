"use client";

import { Container, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";

/**
 * Portal home tab: catalog with the role's audience price
 * (business → resellers, customer → end consumer) + restriction
 * tags when present (p11 UC-02, RNF-P11-03).
 */
export default function PortalHome() {
  return (
    <Container maxW="5xl" py={8}>
      <Heading size="2xl" mb={6}>
        Catálogo
      </Heading>
      <ProductsCatalog />
    </Container>
  );
}
