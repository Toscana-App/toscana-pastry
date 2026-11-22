"use client";

import { Avatar, Box, Button, Circle, Container, Flex, Float, Menu, Portal } from "@chakra-ui/react";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { useCartCount } from "@/hooks/useCartCount";
import { ColorModeButton } from "@/components/ui/color-mode";
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
            <Float placement="top-end">
              <Circle
                minW="16px"
                h="16px"
                px="4px"
                bg="brand.400"
                color="white"
                fontSize="10px"
                fontWeight="bold"
                aria-hidden="true"
              >
                {count > 99 ? "99+" : count}
              </Circle>
            </Float>
          )}
        </Box>
      </NextLink>
    </Button>
  );
}

const ADMIN_LINKS = [
  { value: "orders", href: "/pedidos", label: "Pedidos" },
  { value: "quotes", href: "/presupuestos", label: "Presupuestos" },
  { value: "catalog", href: "/products", label: "Catálogo" },
  { value: "products", href: "/productos", label: "Productos" },
  { value: "ingredients", href: "/admin/ingredients", label: "Ingredientes" },
  { value: "calculator", href: "/admin/calculator/products", label: "Calculator" },
  { value: "dashboard", href: "/admin", label: "Panel de control" },
  { value: "settings", href: "/admin/settings", label: "Settings" },
] as const;

function AdminMenu() {
  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <Button variant="ghost" size="sm" h="44px" aria-label="Menú">
          Menú
        </Button>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content>
            {ADMIN_LINKS.map((link) => (
              <Menu.Item key={link.value} value={link.value} asChild>
                <NextLink href={link.href}>{link.label}</NextLink>
              </Menu.Item>
            ))}
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}

function ProfileMenu({
  label,
  name,
  onLogout,
}: {
  label: string;
  name: string;
  onLogout?: () => void;
}) {
  return (
    <Menu.Root positioning={{ placement: "bottom-end" }}>
      <Menu.Trigger
        rounded="full"
        focusRing="outside"
        aria-label={label}
        minH="44px"
        minW="44px"
        display="grid"
        placeItems="center"
      >
        <Avatar.Root size="sm">
          <Avatar.Fallback name={name} />
          <Avatar.Image alt="" />
        </Avatar.Root>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content>
            <Menu.Item value="profile" asChild>
              <NextLink href="/profile">{label}</NextLink>
            </Menu.Item>
            {onLogout && (
              <Menu.Item
                value="logout"
                color="fg.error"
                _hover={{ bg: "bg.error", color: "fg.error" }}
                onClick={onLogout}
              >
                Logout
              </Menu.Item>
            )}
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}

export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();

  const role = user?.role;
  const isAdmin = role === "admin";
  const isPortal = isPortalRole(role);

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
      <Container maxW="6xl">
        <Flex h="auto" align="center" justify="space-between" gap={4} wrap="wrap">
          <Box flexShrink={0} display="inline-flex">
            <NextLink href="/">
              <BrandLogo variant="horizontal" height={36} priority />
            </NextLink>
          </Box>

          <Flex align="center" gap={2} wrap="wrap" flexShrink={0}>
            {isAuthenticated ? (
              <>
                {isAdmin && <AdminMenu />}
                {isPortal && <CartButton />}
                {(isAdmin || isPortal) && (
                  <ProfileMenu
                    label={isAdmin ? "Perfil" : "Mi cuenta"}
                    name={user?.email ?? ""}
                    onLogout={isAdmin ? logout : undefined}
                  />
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
