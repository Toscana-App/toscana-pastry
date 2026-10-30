"use client";

import { Container, Heading, Flex } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import MaterialsAbm from "@/components/calc/MaterialsAbm";

// Página /admin/calculadora/materiales (F2, T-F2): catálogo de materiales
// de la calculadora de costos. Solo listado + ABM (sin tabs); maxW xl
// porque la tabla tiene ~9 columnas (decisión en PREGUNTAS.md F2).
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
