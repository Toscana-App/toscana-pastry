"use client";

import { useRouter } from "next/navigation";
import { Button, Container, Flex, Heading, Text } from "@chakra-ui/react";

export default function UnauthorizedPage() {
  const router = useRouter();

  return (
    <Container maxW="2xl" minH="100dvh">
      <Flex direction="column" align="center" justify="center" gap={4} minH="100dvh">
        <Heading as="h1" fontSize="3xl" textWrap="balance">Acceso denegado</Heading>
        <Text color="fg.muted" textAlign="center">
          Tu cuenta no tiene permisos para ver esta página.
        </Text>
        <Flex gap={3}>
          <Button colorPalette="brand" onClick={() => router.push("/")}>
            Ir a inicio
          </Button>
          <Button variant="outline" onClick={() => router.push("/login")}>
            Ingresar con otra cuenta
          </Button>
        </Flex>
      </Flex>
    </Container>
  );
}
