"use client";

import { GooeyToaster } from "goey-toast";
import { useColorMode } from "@/components/ui/color-mode";

export function AppGooeyToaster() {
  const { colorMode } = useColorMode();
  return <GooeyToaster position="bottom-right" theme={colorMode === "dark" ? "dark" : "light"} />;
}
