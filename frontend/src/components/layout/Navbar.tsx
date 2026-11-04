"use client";

import { Suspense, useState } from "react";
import { usePress } from "@react-aria/interactions";
import { Box, Container, Flex, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { ColorModeButton } from "@/components/ui/color-mode";
import { BrandLogo } from "./BrandLogo";

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  negocio: "Negocio",
  customer: "Cliente",
};

type NavItem = {
  label: string;
  sublabel?: string;
  href: string;
  roles?: string[];
};

const NAV_ITEMS: NavItem[] = [
  { label: "Inicio", sublabel: "Página principal", href: "/" },
  { label: "Catálogo", sublabel: "Productos y precios", href: "/products" },
  { label: "Pedidos", sublabel: "Gestionar pedidos", href: "/pedidos", roles: ["admin"] },
  { label: "Presupuestos", sublabel: "Cotizaciones", href: "/presupuestos", roles: ["admin"] },
  { label: "Admin", sublabel: "Panel de administración", href: "/admin", roles: ["admin"] },
];

/**
 * Global navbar — impuestito pattern + React Aria accessibility:
 * - usePress for hamburger toggle (keyboard, touch, pointer)
 * - useFocusRing for visible keyboard focus on nav items
 * - aria-current="page" for active nav item
 * - aria-expanded on mobile menu trigger
 * - Mobile: stacked full-width with border-b
 * - Desktop: horizontal, rounded-lg hover
 */
export function Navbar() {
  return (
    <Suspense fallback={<NavFallback />}>
      <NavbarInner />
    </Suspense>
  );
}

function NavFallback() {
  return (
    <Box as="nav" bg="bg" borderBottomWidth={1} borderColor="border" position="sticky" top={0} zIndex={50} w="full" py={4} px={4}>
      <Container maxW="container.xl">
        <BrandLogo variant="horizontal" height={32} />
      </Container>
    </Box>
  );
}

/**
 * Nav link with React Aria focus ring + aria-current.
 */
function NavLink({
  href,
  label,
  sublabel,
  isActive,
  isMobile,
}: {
  href: string;
  label: string;
  sublabel?: string;
  isActive: boolean;
  isMobile: boolean;
}) {
  return (
    <NextLink href={href} style={{ width: isMobile ? "100%" : undefined }} aria-current={isActive ? "page" : undefined}>
      <Flex
        align="center"
        gap={2}
        px={4}
        py={isMobile ? "3.5" : 2}
        borderRadius={isMobile ? "none" : "lg"}
        borderBottomWidth={isMobile ? (isActive ? "2px" : "1px") : 0}
        borderColor={isActive ? "brand.solid" : isMobile ? "border" : "transparent"}
        bg={isActive ? "brand.subtle" : "transparent"}
        outline="none"
        _focusVisible={{ outline: "2px solid", outlineColor: "brand.solid", outlineOffset: "-2px" }}
        _hover={{ bg: isActive ? "brand.subtle" : "bg.muted" }}
        transition="background-color 0.15s ease"
        cursor="pointer"
      >
        <Text
          fontSize="sm"
          fontWeight={isActive ? "semibold" : "medium"}
          color={isActive ? "brand.solid" : "fg"}
        >
          {label}
        </Text>
        {sublabel && (
          <Text fontSize="xs" color="fg.muted" fontWeight="normal" ml={1}>
            {sublabel}
          </Text>
        )}
      </Flex>
    </NextLink>
  );
}

/**
 * Hamburger button with React Aria usePress (keyboard, touch, pointer).
 */
function MenuToggle({ isOpen, onToggle }: { isOpen: boolean; onToggle: () => void }) {
  const { pressProps } = usePress({
    onPress: onToggle,
  });

  return (
    <button
      type="button"
      aria-label={isOpen ? "Cerrar navegación" : "Mostrar navegación"}
      aria-expanded={isOpen}
      aria-controls="mobile-nav"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 36,
        height: 36,
        borderRadius: 8,
        cursor: "pointer",
        outline: "none",
        border: "none",
        background: "transparent",
      }}
      className="max-md:inline-flex md:hidden"
      onFocus={(e) => {
        if (e.target.matches(":focus-visible")) {
          e.target.style.outline = "2px solid var(--chakra-colors-brand-solid)";
          e.target.style.outlineOffset = "2px";
        }
      }}
      onBlur={(e) => {
        e.target.style.outline = "none";
      }}
      {...pressProps}
    >
      <Flex direction="column" align="center" justify="center" gap={isOpen ? 1.5 : 5}>
        <Box
          w={5}
          h="1.5px"
          bg="fg"
          borderRadius="full"
          transform={isOpen ? "rotate(45deg) translate(3px, 3px)" : "none"}
          transition="transform 0.2s ease"
        />
        <Box
          w={5}
          h="1.5px"
          bg="fg"
          borderRadius="full"
          opacity={isOpen ? 0 : 1}
          transition="opacity 0.15s ease"
        />
        <Box
          w={5}
          h="1.5px"
          bg="fg"
          borderRadius="full"
          transform={isOpen ? "rotate(-45deg) translate(3px, -3px)" : "none"}
          transition="transform 0.2s ease"
        />
      </Flex>
    </button>
  );
}

function NavbarInner() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const role = user?.role;
  const isAdmin = role === "admin";

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (role && item.roles.includes(role))
  );

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <Box
      as="nav"
      aria-label="Navegación principal"
      bg="bg"
      borderBottomWidth={1}
      borderColor="border"
      position="sticky"
      top={0}
      zIndex={50}
      w="full"
    >
      <Container maxW="container.xl" py={0}>
        <Flex
          direction={{ base: "column", md: "row" }}
          align={{ base: "stretch", md: "center" }}
          justify="space-between"
          gap={0}
        >
          {/* Top row: logo + hamburger (mobile) / auth (desktop) */}
          <Flex
            align="center"
            justify="space-between"
            px={4}
            py={{ base: 3, md: 4 }}
            w="full"
            gap={3}
          >
            <Flex align="center" gap={3}>
              <NextLink href="/" style={{ display: "contents" }}>
                <BrandLogo variant="horizontal" height={32} priority />
              </NextLink>
              {isAuthenticated && (
                <Text
                  as="span"
                  fontSize="xs"
                  fontWeight="semibold"
                  color={isAdmin ? "red" : "brand.solid"}
                  bg={isAdmin ? "red.subtle" : "brand.subtle"}
                  px={2}
                  py={0.5}
                  borderRadius="full"
                >
                  {ROLE_LABELS[role ?? ""] ?? role}
                </Text>
              )}
            </Flex>

            <Flex align="center" gap={2}>
              <MenuToggle isOpen={mobileOpen} onToggle={() => setMobileOpen(!mobileOpen)} />
              <Flex align="center" gap={2} display={{ base: "none", md: "flex" }}>
                {isAuthenticated ? (
                  <>
                    <NextLink href="/profile" style={{ display: "block" }}>
                      <Box
                        px={3}
                        py={2}
                        borderRadius="lg"
                        fontSize="sm"
                        fontWeight="medium"
                        color="fg"
                        _hover={{ bg: "bg.muted" }}
                        transition="background-color 0.15s ease"
                        cursor="pointer"
                      >
                        Profile
                      </Box>
                    </NextLink>
                    <Box
                      as="button"
                      onClick={logout}
                      px={3}
                      py={2}
                      borderRadius="lg"
                      fontSize="sm"
                      fontWeight="medium"
                      color="red"
                      border="1px solid"
                      borderColor="red.subtle"
                      _hover={{ bg: "red.subtle" }}
                      transition="background-color 0.15s ease"
                      cursor="pointer"
                    >
                      Logout
                    </Box>
                  </>
                ) : (
                  <NextLink href="/login" style={{ display: "block" }}>
                    <Box
                      px={4}
                      py={2}
                      borderRadius="lg"
                      fontSize="sm"
                      fontWeight="medium"
                      color="white"
                      bg="brand.solid"
                      _hover={{ bg: "brand.muted" }}
                      transition="background-color 0.15s ease"
                      cursor="pointer"
                    >
                      Login
                    </Box>
                  </NextLink>
                )}
                <ColorModeButton />
              </Flex>
            </Flex>
          </Flex>

          {/* Desktop nav links */}
          <Flex
            direction="row"
            gap={0}
            display={{ base: "none", md: "flex" }}
            align="center"
            px={2}
            py={2}
          >
            {visibleItems.map((item) => (
              <NavLink
                key={item.href}
                href={item.href}
                label={item.label}
                sublabel={item.sublabel}
                isActive={isActive(item.href)}
                isMobile={false}
              />
            ))}
          </Flex>

          {/* Mobile nav panel */}
          {mobileOpen && (
            <Box
              id="mobile-nav"
              as="div"
              display={{ base: "block", md: "none" }}
              bg="bg"
              borderTopWidth={1}
              borderColor="border"
            >
              <Flex direction="column" gap={0} px={2} py={2}>
                {visibleItems.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    sublabel={item.sublabel}
                    isActive={isActive(item.href)}
                    isMobile={true}
                  />
                ))}
                <Flex direction="column" gap={2} pt={3} mt={2} borderTopWidth={1} borderColor="border" px={2}>
                  {isAuthenticated ? (
                    <>
                      <NextLink href="/profile" style={{ display: "block" }}>
                        <Box px={3} py={2.5} fontSize="sm" fontWeight="medium" color="fg" _hover={{ bg: "bg.muted" }} borderRadius="lg">
                          Profile
                        </Box>
                      </NextLink>
                      <Box
                        as="button"
                        onClick={logout}
                        px={3}
                        py={2.5}
                        fontSize="sm"
                        fontWeight="medium"
                        color="red"
                        textAlign="left"
                        border="none"
                        bg="none"
                        cursor="pointer"
                        _hover={{ bg: "red.subtle" }}
                        borderRadius="lg"
                      >
                        Logout
                      </Box>
                    </>
                  ) : (
                    <NextLink href="/login" style={{ display: "block" }}>
                      <Box
                        px={4}
                        py={2.5}
                        borderRadius="lg"
                        fontSize="sm"
                        fontWeight="medium"
                        color="white"
                        bg="brand.solid"
                        textAlign="center"
                      >
                        Login
                      </Box>
                    </NextLink>
                  )}
                  <ColorModeButton />
                </Flex>
              </Flex>
            </Box>
          )}
        </Flex>
      </Container>
    </Box>
  );
}
