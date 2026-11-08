"use client";

import { Container } from "@chakra-ui/react";
import { useParams } from "next/navigation";
import { ProductStoreDetail } from "@/components/portal/ProductStoreDetail";

export default function ProductDetailRoute() {
  const params = useParams<{ id: string }>();
  return (
    <Container maxW="5xl" py={8} minH="50vh">
      <ProductStoreDetail id={params.id} />
    </Container>
  );
}
