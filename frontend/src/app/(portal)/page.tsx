"use client";

import { Suspense } from "react";
import { Container, Heading } from "@chakra-ui/react";
import { CatalogSkeleton } from "@/components/ui/skeleton";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";
import { CATALOG_ANCHOR, HeroSection } from "@/components/portal/hero_section";

export default function PortalHome() {
  return (
    <>
      <HeroSection />
      <Container id={CATALOG_ANCHOR} maxW="5xl" py={8} scrollMarginTop="72px">
        <Heading as="h2" size="2xl" mb={6}>
          Catálogo
        </Heading>
        <Suspense fallback={<CatalogSkeleton />}>
          <ProductsCatalog />
        </Suspense>
      </Container>
    </>
  );
}
