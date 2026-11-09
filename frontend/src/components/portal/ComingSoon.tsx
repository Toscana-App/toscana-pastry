"use client";

import { Box, Badge, Heading, Text, VStack } from "@chakra-ui/react";
import { Container } from "@chakra-ui/react";

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
