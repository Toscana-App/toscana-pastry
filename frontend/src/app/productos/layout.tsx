import type { Metadata } from "next";
import { Container } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export const metadata: Metadata = {
  title: {
    default: "Productos",
    template: "%s · Productos",
  },
};

/**
 * Sección de productos (Fase 5): vitrina P3 + detalle P4.
 *
 * - ProtectedRoute (sin rol): la API de productos exige sesión para leer.
 * - Container lg: la grilla del P3 necesita ~900 px para las 3 columnas
 *   (RNF-P3-02); con container.md nunca llegarían a 3.
 * - El alta y la edición se protegen aparte con requiredRole="admin".
 */
export default function ProductsLayout({
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
