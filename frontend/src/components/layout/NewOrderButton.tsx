"use client";

import { Button } from "@chakra-ui/react";
import NextLink from "next/link";
import { NEW_ORDER_HREF } from "@/lib/portalRoutes";

/**
 * CTA "Nuevo pedido" of the portal shell (p11 UI).
 *
 * Single CTA per screen (RNF-P11-04); points at the 5-step checkout
 * (F2). Touch target ≥ 44 px.
 */
export function NewOrderButton() {
  return (
    <Button colorPalette="brand" size="sm" minH="44px" asChild>
      <NextLink href={NEW_ORDER_HREF}>Nuevo pedido</NextLink>
    </Button>
  );
}
