"use client"

import {
  Box,
  Container,
  Flex,
  Button,
  useColorModeValue,
  Text,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export function Navbar() {
  const { isAuthenticated, logout } = useAuth();
  const bgColor = useColorModeValue("white", "gray.900");
  const borderColor = useColorModeValue("gray.200", "gray/800"); // typo fix
  const textColor = useColorModeValue("gray.800", "white");

  return (
    <Box
      as="nav"
      px={4}
      py={3}
      bg={bgColor}
      borderBottomWidth={1}
      borderColor={borderColor}
      position="sticky"
      top={0}
      zIndex={50}
      w="full"
    >
      <Container maxW="container.xl">
        <Flex
          h="auto"
          align="center"
          justify="space-between"
        >
          <NextLink href="/" passHref>
            <Text
              fontSize="xl"
              fontWeight="bold"
              color="brand.600"
              cursor="pointer"
            >
              Toscana Pastry
            </Text>
          </NextLink>

          <Flex align="center" gap={4}>
            <NextLink href="/" passHref>
              <Button variant="ghost">Home</Button>
            </NextLink>

            {isAuthenticated ? (
              <>
                <NextLink href="/profile" passHref>
                  <Button variant="ghost">Profile</Button>
                </NextLink>
                <Button
                  onClick={logout}
                  colorScheme="red"
                  size="sm"
                  variant="outline"
                >
                  Logout
                </Button>
              </>
            ) : (
              <NextLink href="/login" passHref>
                <Button colorScheme="brand">Login</Button>
              </NextLink>
            )}
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
