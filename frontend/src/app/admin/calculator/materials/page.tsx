"use client";

import { Container, Heading, Flex } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import MaterialsAbm from "@/components/calc/MaterialsAbm";

export default function MaterialesPage() {
  return (
    <ProtectedRoute requiredRole="admin">
      <Container py={10} maxW="6xl">
        <Flex direction="column" gap={6}>
          <Heading fontSize="3xl" textWrap="balance">Materiales</Heading>
          <MaterialsAbm />
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
