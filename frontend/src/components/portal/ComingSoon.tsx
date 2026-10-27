"use client";

import { Box, Badge, Heading, Text, VStack } from "@chakra-ui/react";
import { Container } from "@chakra-ui/react";

/**
 * Empty state for portal sections that arrive in the next stacked
 * slices (F2 checkout, F3 cart/payment, F4 my-orders/accounts).
 * The shell (tabs + CTA) is already complete; the content is replaced
 * in its slice without touching the navigation.
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
