import { Button, Container, Flex, Heading, Text } from "@chakra-ui/react";
import NextLink from "next/link";

export default function NotFoundPage() {
  return (
    <Container maxW="2xl" minH="100dvh">
      <Flex direction="column" align="center" justify="center" gap={4} minH="100dvh">
        <Heading as="h1" fontSize="3xl" textWrap="balance">
          Página no encontrada
        </Heading>
        <Text color="fg.muted" textAlign="center">
          La página que buscás no existe o ya no está disponible.
        </Text>
        <Button asChild colorPalette="brand">
          <NextLink href="/">Ir a inicio</NextLink>
        </Button>
      </Flex>
    </Container>
  );
}
