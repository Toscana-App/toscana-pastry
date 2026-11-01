"use client"

import { Suspense } from "react"
import { Container, Spinner, VStack } from "@chakra-ui/react"
import LoginForm from "@/components/auth/LoginForm"

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
        {/* Suspense obligatorio: LoginForm usa useSearchParams (requisito de prerender de Next). */}
        <Suspense fallback={<Spinner size="xl" />}>
          <LoginForm />
        </Suspense>
      </VStack>
    </Container>
  )
}
