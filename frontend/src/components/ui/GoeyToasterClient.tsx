"use client";

import { GooeyToaster } from "goey-toast";
import { useColorMode } from "@/components/ui/color-mode";

/**
 * Client wrapper for <GooeyToaster /> (goey-toast ships without a
 * "use client" banner, so it must be wrapped before use in a Server
 * Component like the root layout).
 */
export function AppGooeyToaster() {
  const { colorMode } = useColorMode();
  return <GooeyToaster position="bottom-right" theme={colorMode === "dark" ? "dark" : "light"} />;
}
