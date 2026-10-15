"use client"

import { Box, Container, Flex, Button, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export function Navbar() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <Box
      as="nav"
      px={4}
      py={3}
      bg="white"
      borderBottomWidth={1}
      borderColor="gray.200"
      position="sticky"
      top={0}
      zIndex={50}
      w="full"
    >
      <Container maxW="container.xl">
        <Flex h="auto" align="center" justify="space-between">
          <NextLink href="/">
            <Text fontSize="xl" fontWeight="bold" color="brand.600" cursor="pointer">
              Toscana Pastry
            </Text>
          </NextLink>

          <Flex align="center" gap={4}>
            <Button variant="ghost" asChild>
              <NextLink href="/">Home</NextLink>
            </Button>

            {isAuthenticated ? (
              <>
                <Button variant="ghost" asChild>
                  <NextLink href="/profile">Profile</NextLink>
                </Button>
                <Button onClick={logout} colorPalette="red" size="sm" variant="outline">
                  Logout
                </Button>
              </>
            ) : (
              <Button colorPalette="brand" asChild>
                <NextLink href="/login">Login</NextLink>
              </Button>
            )}
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
