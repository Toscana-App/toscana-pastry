import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Vitest: runner de los unit tests de la Fase 4.
 * - jsdom: entorno DOM para los tests de componentes.
 * - alias "@" → src/: el mismo atajo de tsconfig, que Vitest no resuelve solo.
 * - include: solo tests bajo src/ (patrón *.test.{ts,tsx} de las specs).
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
