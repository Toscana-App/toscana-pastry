"use client"

import { Suspense } from "react"
import {
  Box,
  Button,
  Container,
  Heading,
  Separator,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";

import LoginForm from "@/components/auth/LoginForm"
import { BrandLogo } from "@/components/layout/BrandLogo"
import { GoogleIcon } from "@/components/ui/google-icon"

/**
 * Static stand-in for the login card while Next hydrates the form
 * (Suspense is required because LoginForm uses `useSearchParams`).
 * The form is fully static — no endpoint data — so the fallback mirrors
 * the real card one-to-one (same heading and button with the same size) instead of a skeleton: nothing on this screen loads from an
 * endpoint, so no element here may shimmer.
 */
function LoginFormPlaceholder() {
  return (
    <Box
      width="100%"
      maxW="400px"
      p={8}
      borderRadius="lg"
      borderWidth="1px"
      borderColor="border"
      boxShadow="lg"
      bg="bg.panel"
    >
      <Stack gap={6} align="center">
        <Heading fontSize="2xl">Iniciar sesión</Heading>
        <Text color="fg.muted" textAlign="center">
          Continúa con tu cuenta de Google
        </Text>
        <Separator />
        <Button variant="outline" width="full" disabled aria-hidden="true">
          <GoogleIcon />
          Continuar con Google
        </Button>
      </Stack>
    </Box>
  )
}

export default function LoginPage() {
  return (
    <Container
      maxW="container.md"
      py={20}
      display="flex"
      alignItems="center"
      justifyContent="center"
      minH="100dvh"
    >
      <VStack gap={8} width="full" align="center">
        <BrandLogo variant="vertical" height={150} priority />
        {/* Suspense obligatorio: LoginForm usa useSearchParams (requisito de prerender de Next). */}
        <Suspense fallback={<LoginFormPlaceholder />}>
          <LoginForm />
        </Suspense>
      </VStack>
    </Container>
  )
}
