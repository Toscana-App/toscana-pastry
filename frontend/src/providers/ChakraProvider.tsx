"use client"

import { ChakraProvider } from "@chakra-ui/react"
import { system } from "@/components/ui/theme"
import { ColorModeProvider } from "@/components/ui/color-mode"

export function Provider({ children }: { children: React.ReactNode }) {
  return (
    <ColorModeProvider>
      <ChakraProvider value={system}>{children}</ChakraProvider>
    </ColorModeProvider>
  )
}
