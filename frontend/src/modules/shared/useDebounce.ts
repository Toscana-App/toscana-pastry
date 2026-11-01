"use client";

import { useEffect, useState } from "react";

/**
 * Debounce de valores (Fase 4, RF-P2-01: 250 ms en la búsqueda de ingredientes).
 *
 * Retorna el valor estable: solo cambia tras `delayMs` sin nuevas escrituras.
 * Se usa para no disparar una request por cada tecla del input de búsqueda.
 */
export function useDebounce<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
