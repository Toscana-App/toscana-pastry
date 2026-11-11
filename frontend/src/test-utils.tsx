import { ChakraProvider, LocaleProvider } from "@chakra-ui/react";
import { render } from "@testing-library/react";
import type { RenderOptions } from "@testing-library/react";
import { system } from "@/components/ui/theme";

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  return render(
    <ChakraProvider value={system}>
      <LocaleProvider locale="es-AR">{ui}</LocaleProvider>
    </ChakraProvider>,
    options
  );
}
