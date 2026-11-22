"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Box, Button, Flex, Input, InputGroup } from "@chakra-ui/react";
import { SearchIcon } from "@/components/ui/search-icon";

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

  useEffect(() => {
    const q = term.trim();
    if (q === urlQ) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => navigate(q), DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [term, urlQ, navigate]);

  const [lastUrlQ, setLastUrlQ] = useState(urlQ);
  if (urlQ !== lastUrlQ) {
    setLastUrlQ(urlQ);
    setTerm(urlQ);
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    navigate(term);
  };

  return (
    <form role="search" onSubmit={submit}>
      <Flex w="full" maxW="640px" align="center" gap="12px">
        <InputGroup
          w="full"
          borderRadius="full"
          startElement={<SearchIcon />}
        >
          <Input
            type="search"
            name="q"
            autoComplete="off"
            enterKeyHint="search"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Ej.: torta de almendras…"
            aria-label="Buscar productos"
            borderRadius="full"
            fontSize={{ base: "md", md: "sm" }}
            maxLength={120}
          />
        </InputGroup>
        <Button
          type="submit"
          size="sm"
          px={5}
          fontWeight="600"
          colorPalette="brand"
          flexShrink={0}
        >
          Buscar
        </Button>
      </Flex>
    </form>
  );
}

export function PortalSearch() {
  return (
    <Suspense
      fallback={
        <Box w="full" maxW="640px" h="2.5rem" borderRadius="full" bg="bg.muted" />
      }
    >
      <PortalSearchInner />
    </Suspense>
  );
}
