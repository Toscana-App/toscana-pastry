import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest corre sin globals: sin esto RTL no limpia el DOM entre tests y los
// renders se acumulan (query *By* encuentra duplicados del test anterior).
afterEach(() => {
  cleanup();
});
