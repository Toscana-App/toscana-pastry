"use client";

import { Container, Heading } from "@chakra-ui/react";
import { ProductsCatalog } from "@/components/catalog/ProductsCatalog";

/**
 * Tab "Inicio" del portal: catálogo con el precio de la audiencia del
 * rol (negocio → revendedores, cliente → consumidor final) + tags de
 * restricción si existen (p11 UC-02, RNF-P11-03).
 */
export default function PortalHome() {
  return (
    <Container maxW="container.lg" py={8}>
      <Heading size="2xl" mb={6}>
        Catálogo
      </Heading>
      <ProductsCatalog />
    </Container>
  );
}
