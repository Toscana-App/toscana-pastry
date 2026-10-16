"use client";

import { useRouter } from "next/navigation";
import { Button, Container, Flex, Heading, Text } from "@chakra-ui/react";

export default function UnauthorizedPage() {
  const router = useRouter();

  return (
    <Container maxW="container.sm" minH="100dvh">
      <Flex direction="column" align="center" justify="center" gap={4} minH="100dvh">
        <Heading fontSize="3xl">Access denied</Heading>
        <Text color="fg.muted" textAlign="center">
          Your account does not have permission to view this page.
        </Text>
        <Flex gap={3}>
          <Button onClick={() => router.push("/")}>Go home</Button>
          <Button variant="outline" onClick={() => router.push("/login")}>
            Sign in with another account
          </Button>
        </Flex>
      </Flex>
    </Container>
  );
}
