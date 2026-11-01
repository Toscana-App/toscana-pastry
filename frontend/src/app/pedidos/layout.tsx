import type { Metadata } from "next";
import { Container } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export const metadata: Metadata = {
  title: {
    default: "Pedidos",
    template: "%s · Pedidos",
  },
};

/**
 * Sección de pedidos (Fase 6): listado P6 + wizard + detalle.
 *
 * - ProtectedRoute (sin rol): la API de pedidos exige sesión para leer.
 * - La creación/edición/mutaciones se protegen aparte con
 *   requiredRole="admin" (mismo RBAC que productos).
 */
export default function OrdersLayout({
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
