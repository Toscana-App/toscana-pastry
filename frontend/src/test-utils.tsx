import { ChakraProvider } from "@chakra-ui/react";
import { render } from "@testing-library/react";
import type { RenderOptions } from "@testing-library/react";
import { system } from "@/components/ui/theme";

// Mismo provider de Chakra v3 que usa la app (src/providers/ChakraProvider.tsx):
// los componentes no resuelven tokens de estilo fuera de <ChakraProvider>.
export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  return render(<ChakraProvider value={system}>{ui}</ChakraProvider>, options);
}
