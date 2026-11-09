import type { Metadata } from "next";
import { Container } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export const metadata: Metadata = {
  title: {
    default: "Productos",
    template: "%s · Productos",
  },
};

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
