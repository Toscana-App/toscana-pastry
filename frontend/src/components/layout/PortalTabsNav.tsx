"use client";

import { Flex } from "@chakra-ui/react";
import { TabLink } from "./TabLink";
import { PORTAL_TABS } from "@/lib/portalRoutes";

/**
 * The portal tab bar: Inicio · Mis pedidos · Carrito · Cuenta.
 *
 * The active tab is derived from the current pathname. This is a nav of
 * real routes (not in-page tabs) so each step is shareable and the back
 * button works (p11 RF-P11-01/02).
 */
export function PortalTabsNav({ pathname }: { pathname: string }) {
  return (
    <Flex
      as="nav"
      aria-label="Secciones del portal"
      align="center"
      gap={1}
      overflowX="auto"
    >
      {PORTAL_TABS.map((tab) => (
        <TabLink
          key={tab.href}
          href={tab.href}
          label={tab.label}
          active={isActive(pathname, tab.href)}
        />
      ))}
    </Flex>
  );
}

/** True when ``pathname`` is (or is nested under) the tab's route. */
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
