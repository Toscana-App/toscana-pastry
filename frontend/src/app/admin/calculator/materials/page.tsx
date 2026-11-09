"use client";

import { Container, Heading, Flex } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import MaterialsAbm from "@/components/calc/MaterialsAbm";

export default function MaterialesPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <Container py={10} maxW="container.xl">
        <Flex direction="column" gap={6}>
          <Heading fontSize="3xl">Materiales</Heading>
          <MaterialsAbm />
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
