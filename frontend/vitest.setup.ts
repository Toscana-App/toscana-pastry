import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom no implementa scrollTo; los selects de Ark UI (zag) lo llaman al
// abrir el contenido.
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {};
}

// jsdom no implementa ResizeObserver; floating-ui (popups de Ark UI) lo usa.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  // SAFETY: el stub implementa observe/unobserve/disconnect con la misma
  // firma no-op que requiere floating-ui en jsdom; nunca se observa layout
  // real en el test.
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// jsdom no implementa matchMedia; next-themes (ColorModeProvider) lo usa
// para leer la preferencia de color del sistema. Default: modo claro.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
}

// Vitest sin `globals: true`: el auto-cleanup de Testing Library no se
// registra solo, se explicita aquí.
afterEach(() => {
  cleanup();
});
