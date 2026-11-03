"use client";

import { Container, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";
import { CATALOG_ANCHOR, HeroSection } from "@/components/portal/hero_section";

/**
 * Portal home tab: hero + catalog with the role's audience price
 * (business → resellers, customer → end consumer) + restriction
 * tags when present (p11 UC-02, RNF-P11-03).
 */
export default function PortalHome() {
  return (
    <>
      <HeroSection />
      <Container id={CATALOG_ANCHOR} maxW="5xl" py={8} scrollMarginTop="72px">
        <Heading as="h2" size="2xl" mb={6}>
          Catálogo
        </Heading>
        <ProductsCatalog />
      </Container>
    </>
  );
}
