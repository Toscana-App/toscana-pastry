"use client"

import { Button, Container, Heading, Text, VStack } from "@chakra-ui/react"
import Link from "next/link"

export default function Home() {
  return (
    <Container maxW="container.md" py={20}>
      <VStack gap={6} align="center">
        <Heading as="h1" size="3xl" color="brand.600">
          Toscana Pastry
        </Heading>
        <Text fontSize="xl">
          Delicious handmade pastries delivered to your doorstep.
        </Text>
        <div className="flex gap-4">
          <Button colorScheme="brand" size="lg" as={Link} href="/login">
            Login
          </Button>
          <Button variant="outline" size="lg" as={Link} href="#">
            Get Started
          </Button>
        </div>
      </VStack>
    </Container>
  )
}
