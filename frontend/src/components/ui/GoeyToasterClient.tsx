"use client";

import { GooeyToaster } from "goey-toast";

/**
 * Client wrapper for <GooeyToaster /> (goey-toast ships without a
 * "use client" banner, so it must be wrapped before use in a Server
 * Component like the root layout).
 */
export function AppGooeyToaster() {
  return <GooeyToaster position="bottom-right" />;
}
