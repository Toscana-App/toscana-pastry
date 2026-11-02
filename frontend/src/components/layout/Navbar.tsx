"use client";

import { Badge, Box, Button, Container, Flex } from "@chakra-ui/react";
import NextLink from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { ColorModeButton } from "@/components/ui/color-mode";
import { BrandLogo } from "./BrandLogo";

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  negocio: "Negocio",
  customer: "Cliente",
};

/**
 * Global navbar with the visible role (p11 "UI — portal shell").
 *
 * - admin: Productos / Pedidos / Presupuestos / Catálogo / Admin / Settings / Profile
 * - portal (business/customer): Profile + Logout — portal navigation
 *   lives in the tab bar of the `(portal)` route group; no access to /admin.
 * - no session: Login.
 */
export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();

  const role = user?.role;
  const isAdmin = role === "admin";

  return (
    <Box
      as="nav"
      px={4}
      py={3}
      bg="bg"
      borderBottomWidth={1}
      borderColor="border"
      position="sticky"
      top={0}
      zIndex={50}
      w="full"
    >
      <Container maxW="container.xl">
        <Flex h="auto" align="center" justify="space-between" gap={3} wrap="wrap">
          <Flex align="center" gap={3}>
            <NextLink href="/">
              <BrandLogo variant="horizontal" height={36} priority />
            </NextLink>
            {isAuthenticated && (
              <Badge colorPalette={isAdmin ? "red" : "brand"}>
                {ROLE_LABELS[role ?? ""] ?? role}
              </Badge>
            )}
          </Flex>

          <Flex align="center" gap={2} wrap="wrap">
            {isAuthenticated ? (
              <>
                {isAdmin && (
                  <>
                    <Button variant="ghost" asChild>
                      <NextLink href="/productos">Productos</NextLink>
                    </Button>
                    <Button variant="ghost" asChild>
                      <NextLink href="/pedidos">Pedidos</NextLink>
                    </Button>
                    <Button variant="ghost" asChild>
                      <NextLink href="/presupuestos">Presupuestos</NextLink>
                    </Button>
                    <Button variant="ghost" asChild>
                      <NextLink href="/products">Catálogo</NextLink>
                    </Button>
                    <Button variant="ghost" asChild>
                      <NextLink href="/admin">Admin</NextLink>
                    </Button>
                    <Button variant="ghost" asChild>
                      <NextLink href="/admin/settings">Settings</NextLink>
                    </Button>
                  </>
                )}
                {!isPortalRole(role) && !isAdmin && null}
                <Button variant="ghost" asChild>
                  <NextLink href="/profile">Profile</NextLink>
                </Button>
                <Button onClick={logout} colorPalette="red" size="sm" variant="outline">
                  Logout
                </Button>
              </>
            ) : (
              <Button colorPalette="brand" asChild>
                <NextLink href="/login">Login</NextLink>
              </Button>
            )}
            <ColorModeButton />
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
