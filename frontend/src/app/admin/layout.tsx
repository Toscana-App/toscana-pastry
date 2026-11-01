import type { Metadata } from "next";
import { Container } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AdminNav } from "@/components/layout/AdminNav";

export const metadata: Metadata = {
  title: {
    default: "Administración",
    template: "%s · Administración",
  },
};

/**
 * Layout de la sección admin (Fase 4, WU3).
 *
 * Centraliza lo que antes repetía cada página:
 * - ProtectedRoute requiredRole="admin" (la página /admin lo tenía; las rutas
 *   nuevas heredan la protección).
 * - Contenedor + AdminNav (Usuarios / Ingredientes / Configuración).
 *
 * Las páginas que viven aquí ya NO envuelven ProtectedRoute: la protección
 * vive una sola vez, acá.
 */
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute requiredRole="admin">
      <Container py={10} maxW="container.md">
        <AdminNav />
        {children}
      </Container>
    </ProtectedRoute>
  );
}
