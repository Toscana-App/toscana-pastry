"use client"

import { Container, VStack, Heading, Text } from "@chakra-ui/react"
import LoginForm from "@/components/auth/LoginForm"

export default function LoginPage() {
  return (
    <Container maxW="container.md" py={20} display="flex" alignItems="center" justifyContent="center" minH="100dvh">
      <VStack spacing={8} width="full" align="center">
        <LoginForm />
      </VStack>
    </Container>
  )
}
