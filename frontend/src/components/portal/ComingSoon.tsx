"use client";

import { Box, Badge, Heading, Text, VStack } from "@chakra-ui/react";
import { Container } from "@chakra-ui/react";

/**
 * Estado vacío para las secciones del portal que llegan en las próximas
 * slices stacked (F2 checkout, F3 carrito/pago, F4 mis pedidos/cuentas).
 * El shell (tabs + CTA) ya está completo; el contenido se reemplaza en
 * su slice sin tocar la navegación.
 */
export function ComingSoon({ title, message }: { title: string; message: string }) {
  return (
    <Container maxW="container.md" py={10}>
      <Box
        as="section"
        border="1px"
        borderColor="border.muted"
        rounded="md"
        py={12}
      >
        <VStack gap={3} align="center" textAlign="center">
          <Heading size="lg">{title}</Heading>
          <Text color="fg.muted">{message}</Text>
          <Badge colorPalette="gray">Próximamente</Badge>
        </VStack>
      </Box>
    </Container>
  );
}
