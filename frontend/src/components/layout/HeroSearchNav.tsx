"use client";

import { Box, Container } from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { isPortalRole } from "@/lib/portalRoutes";
import { PortalSearch } from "./PortalSearch";

/**
 * Search-only navbar row owned by the home hero.
 *
 * The global `Navbar` never renders the search bar; only the hero
 * (public home page) shows it, via this decoupled component.
 */
export function HeroSearchNav() {
  const { user } = useAuth();

  if (!isPortalRole(user?.role)) {
    return null;
  }

  return (
    <Box pt={{ base: 4, md: 6 }} pb={2}>
      <Container maxW="container.xl">
        <Box display="flex" justifyContent="center" w="full">
          <PortalSearch />
        </Box>
      </Container>
    </Box>
  );
}
