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
        <Heading as="h1" fontSize="2xl">Iniciar sesión</Heading>
        <Text color="fg.muted" textAlign="center">
          Continúa con tu cuenta de Google
        </Text>
        <Separator />
        <Button variant="outline" size="lg" width="full" disabled>
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
      maxW="2xl"
      py={20}
      display="flex"
      alignItems="center"
      justifyContent="center"
      minH="100dvh"
    >
      <VStack gap={8} width="full" align="center">
        <BrandLogo variant="vertical" height={150} priority />
        <Suspense fallback={<LoginFormPlaceholder />}>
          <LoginForm />
        </Suspense>
      </VStack>
    </Container>
  )
}
