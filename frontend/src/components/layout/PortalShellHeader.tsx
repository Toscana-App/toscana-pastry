"use client";

import { Flex } from "@chakra-ui/react";
import { usePathname } from "next/navigation";
import { PortalTabsNav } from "./PortalTabsNav";
import { NewOrderButton } from "./NewOrderButton";

/**
 * Portal shell header: tab bar (Inicio · Mis pedidos · Carrito · Cuenta)
 * + CTA "Nuevo pedido" (p11 "UI — Shell del portal").
 *
 * Rendered below the global Navbar on every portal page via the
 * `(portal)` route group layout.
 */
export function PortalShellHeader() {
  const pathname = usePathname();

  return (
    <Flex
      as="header"
      align="center"
      justify="space-between"
      gap={3}
      wrap="wrap"
      px={4}
      py={2}
      bg="bg"
      borderBottomWidth="1px"
      borderColor="border.muted"
      w="full"
    >
      <PortalTabsNav pathname={pathname} />
      <NewOrderButton />
    </Flex>
  );
}
