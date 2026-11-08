"use client"

import { Suspense } from "react"
import { Container, VStack } from "@chakra-ui/react";
import { LoginFormSkeleton } from "@/components/ui/skeleton";

import LoginForm from "@/components/auth/LoginForm"
import { BrandLogo } from "@/components/layout/BrandLogo"

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
        <Suspense fallback={<LoginFormSkeleton />}>
          <LoginForm />
        </Suspense>
      </VStack>
    </Container>
  )
}
