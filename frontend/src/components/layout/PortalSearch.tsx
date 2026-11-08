"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Box, Button, Input, InputGroup } from "@chakra-ui/react";
import { SearchIcon } from "@/components/ui/search-icon";

/**
 * Search grande del portal (estilo ancestral.com.ar): busca productos por
 * nombre sobre la colección base del REST —
 * `GET /api/v1/products?audience=...&q=<term>&page=1&page_size=20` —
 * navegando a la home del portal con el filtro en la URL (`?q=term`), que
 * el catálogo lee y aplica.
 *
 * Debounce: la navegación se dispara sola 400 ms después de que el usuario
 * deja de escribir (cada pausa, no cada tecla); Enter/Buscar saltan el
 * timer y filtran de inmediato. Se usa `router.replace` para no inundar el
 * historial con una entrada por tecla.
 *
 * `useSearchParams` rompe el prerender de client components: `PortalSearch`
 * se renderiza dentro de un `<Suspense>` (patrón del skill toscana-pastry)
 * y el componente interno hace el trabajo.
 */
const DEBOUNCE_MS = 400;

function PortalSearchInner() {
  const router = useRouter();
  const params = useSearchParams();
  const urlQ = params.get("q") ?? "";
  const [term, setTerm] = useState(urlQ);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const navigate = useCallback(
    (value: string) => {
      const q = value.trim();
      router.replace(q ? `/?q=${encodeURIComponent(q)}` : "/");
    },
    [router]
  );

  // term -> URL, con debounce: 400 ms de pausa tras el último carácter.
  // Si la URL ya refleja el término (navegación externa o propia), no hace
  // nada — eso evita el loop input->URL->input.
  useEffect(() => {
    const q = term.trim();
    if (q === urlQ) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => navigate(q), DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [term, urlQ, navigate]);

  // URL -> input: la q de la URL cambió por fuera (p. ej. el botón
  // "Quitar" del catálogo) y el input la refleja.
  useEffect(() => {
    setTerm(urlQ);
  }, [urlQ]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    navigate(term);
  };

  return (
    <form role="search" onSubmit={submit} aria-label="Buscar productos">
      <InputGroup
        w="full"
        maxW="560px"
        borderRadius="full"
        startElement={<SearchIcon />}
        endElement={
          <Button
            type="submit"
            size="sm"
            px={5}
            fontWeight="600"
            colorPalette="brand"
            borderRadius="full"
            mr="1px"
          >
            Buscar
          </Button>
        }
      >
        <Input
          type="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="¿Qué producto buscás?"
          aria-label="Buscar productos"
          borderRadius="full"
          fontSize="sm"
          maxLength={120}
        />
      </InputGroup>
    </form>
  );
}

export function PortalSearch() {
  return (
    <Suspense
      fallback={
        <Box w="full" maxW="560px" h="2.5rem" borderRadius="full" bg="bg.muted" />
      }
    >
      <PortalSearchInner />
    </Suspense>
  );
}
