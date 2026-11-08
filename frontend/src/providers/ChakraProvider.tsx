"use client"

import { ChakraProvider } from "@chakra-ui/react"
import { system } from "@/components/ui/theme"
import { ColorModeProvider } from "@/components/ui/color-mode"

// ColorModeProvider wraps Chakra (not the reverse): next-themes renders an
// inline <script> as its first child, and Emotion's injected <style> tags
// inside ChakraProvider would otherwise shift it and break hydration.
export function Provider({ children }: { children: React.ReactNode }) {
  return (
    <ColorModeProvider>
      <ChakraProvider value={system}>{children}</ChakraProvider>
    </ColorModeProvider>
  )
}
