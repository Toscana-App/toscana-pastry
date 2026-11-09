"use client";

import { Container } from "@chakra-ui/react";
import { ProductStoreDetail } from "@/components/portal/ProductStoreDetail";

export function StoreDetailShell({ id }: { id: string }) {
  return (
    <Container maxW="5xl" py={8} minH="50vh">
      <ProductStoreDetail id={id} />
    </Container>
  );
}
