"use client";

import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { Flex, Text } from "@chakra-ui/react";

/**
 * Navegación de la sección admin (Fase 4, WU3).
 *
 * Tres secciones: Usuarios (/admin, exacta), Ingredientes (/admin/ingredients,
 * prefix) y Configuración (/admin/settings, exacta). La sección activa se
 * marca por pathname: /admin/ingredients/* resalta "Ingredientes".
 */
const SECTIONS = [
  { href: "/admin", label: "Usuarios", exact: true },
  { href: "/admin/ingredients", label: "Ingredientes", exact: false },
  { href: "/admin/settings", label: "Configuración", exact: false },
] as const;

export function AdminNav() {
  const pathname = usePathname();

  return (
    <Flex as="nav" gap={1} mb={6} borderBottomWidth="1px" overflowX="auto">
      {SECTIONS.map((section) => {
        const active = section.exact
          ? pathname === section.href
          : pathname.startsWith(section.href);
        return (
          <NextLink key={section.href} href={section.href}>
            <Text
              px={3}
              py={2}
              fontWeight={active ? "600" : "400"}
              color={active ? "brand.fg" : "fg.muted"}
              borderBottomWidth="2px"
              borderColor={active ? "brand.solid" : "transparent"}
              whiteSpace="nowrap"
            >
              {section.label}
            </Text>
          </NextLink>
        );
      })}
    </Flex>
  );
}
