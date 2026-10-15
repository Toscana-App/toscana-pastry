"use client"

import { ChakraProvider } from "@chakra-ui/react"
import { config } from "@/components/ui/theme"

export function Provider({ children }: { children: React.ReactNode }) {
  return <ChakraProvider value={config}>{children}</ChakraProvider>
}
