"use client"

import { Button, Container, Heading, Text, VStack } from "@chakra-ui/react"
import Link from "next/link"

export default function Home() {
  return (
    <Container maxW="container.md" py={20}>
      <VStack gap={6} align="center">
        <Heading as="h1" fontSize="4xl" color="brand.600">
          Toscana Pastry
        </Heading>
        <Text fontSize="xl">
          Delicious handmade pastries delivered to your doorstep.
        </Text>
        <div className="flex gap-4">
          <Button colorPalette="brand" size="lg" asChild>
            <Link href="/login">Login</Link>
          </Button>
          <Button variant="outline" size="lg" asChild>
            <Link href="#">Get Started</Link>
          </Button>
        </div>
      </VStack>
    </Container>
  )
}
