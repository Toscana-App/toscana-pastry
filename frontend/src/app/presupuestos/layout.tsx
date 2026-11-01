import type { Metadata } from "next";
import { Container } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export const metadata: Metadata = {
  title: {
    default: "Presupuestos",
    template: "%s · Presupuestos",
  },
};

/**
 * Sección de presupuestos (Fase 7): listado P7 + wizard + detalle/edición.
 *
 * - ProtectedRoute (sin rol): la API de presupuestos exige sesión para leer.
 * - Creación/edición/mutaciones se protegen aparte con requiredRole="admin".
 */
export default function BudgetsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <Container py={10} maxW="container.lg">
        {children}
      </Container>
    </ProtectedRoute>
  );
}
