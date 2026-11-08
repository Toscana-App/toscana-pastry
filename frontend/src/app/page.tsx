"use client";

import { Suspense } from "react";
import { Container, Heading } from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { CatalogSkeleton } from "@/components/ui/skeleton";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";
import { CATALOG_ANCHOR, HeroSection } from "@/components/portal/hero_section";

/**
 * Public-facing home page (`/`).
 *
 * - Hero: visible para todos (logueado o no).
 * - Catálogo: solo si hay sesión activa (precios por rol).
 *   Sin sesión se muestra el hero sin catálogo — sin redirección.
 */
export default function HomePage() {
  const { isAuthenticated } = useAuth();

  return (
    <>
      <HeroSection />
      <Container id={CATALOG_ANCHOR} maxW="5xl" py={8} scrollMarginTop="72px">
        <Heading as="h2" size="2xl" mb={6}>
          Catálogo
        </Heading>
        {isAuthenticated ? (
          <Suspense fallback={<CatalogSkeleton />}>
            <ProductsCatalog />
          </Suspense>
        ) : (
          <CatalogSkeleton />
        )}
      </Container>
    </>
  );
}
