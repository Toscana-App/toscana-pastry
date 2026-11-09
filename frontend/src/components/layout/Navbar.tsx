"use client";

import { Box, Button, Container, Flex } from "@chakra-ui/react";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { useCartCount } from "@/hooks/useCartCount";
import { ColorModeButton } from "@/components/ui/color-mode";
import { PortalSearch } from "@/components/layout/PortalSearch";
import { BrandLogo } from "./BrandLogo";

function CartButton() {
  const count = useCartCount();
  return (
    <Button variant="ghost" size="sm" px={3} asChild aria-label="Carrito">
      <NextLink href="/carrito">
        <Box position="relative" display="inline-flex" alignItems="center">
          <svg className="icon-inline" width={22} height={22} aria-hidden="true">
            <use xlinkHref="#cart" />
          </svg>
          {count > 0 && (
            <Box
              as="span"
              position="absolute"
              top={-2}
              right={-6}
              minW="16px"
              h="16px"
              px="4px"
              borderRadius="full"
              bg="brand.400"
              color="white"
              fontSize="10px"
              fontWeight="bold"
              display="inline-flex"
              alignItems="center"
              justifyContent="center"
              aria-hidden="true"
            >
              {count > 99 ? "99+" : count}
            </Box>
          )}
        </Box>
      </NextLink>
    </Button>
  );
}

export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();

  const role = user?.role;
  const isAdmin = role === "admin";
  const isPortal = isPortalRole(role);

  // /login is a standalone screen with its own centered brand lockup:
  // rendering the navbar there duplicates the logo and adds a
  // redundant "Login" link to a page that already IS the login.
  if (pathname === "/login") {
    return null;
  }

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
        <Flex h="auto" align="center" justify="space-between" gap={4} wrap="wrap">
          <Box flexShrink={0} display="inline-flex">
            <NextLink href="/">
              <BrandLogo variant="horizontal" height={36} priority />
            </NextLink>
          </Box>

          {isPortal && (
            <Box as="div" flex="1" minW="240px" display="flex" justifyContent="center">
              <PortalSearch />
            </Box>
          )}

          <Flex align="center" gap={2} wrap="wrap" flexShrink={0}>
            {isAuthenticated ? (
              <>
                {isAdmin && (
                  <>
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
                    <Button variant="ghost" asChild>
                      <NextLink href="/profile">Profile</NextLink>
                    </Button>
                  </>
                )}
                {isPortal && (
                  <>
                    <Button variant="ghost" size="sm" asChild>
                      <NextLink href="/profile">
                        <svg className="icon-inline" width={18} height={18} aria-hidden="true">
                          <use xlinkHref="#user" />
                        </svg>
                        Mi cuenta
                      </NextLink>
                    </Button>
                    <CartButton />
                  </>
                )}
                {isAdmin && (
                  <Button onClick={logout} colorPalette="red" size="sm" variant="outline">
                    Logout
                  </Button>
                )}
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
