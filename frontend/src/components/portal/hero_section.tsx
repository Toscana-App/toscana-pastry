"use client"

import { Box, Button, Flex, Grid, GridItem, Heading, Icon, Link, Text } from "@chakra-ui/react"
import NextLink from "next/link"
import { BrandLogo } from "@/components/layout/BrandLogo"

/** One row of the hero ledger panel: an attribute and what it means for the buyer. */
interface HeroAttribute {
  label: string
  status: string
}

export const HERO_ATTRIBUTES: readonly HeroAttribute[] = [
  { label: "Sin TACC", status: "Apto celíacos" },
  { label: "100% Natural", status: "Sin conservantes" },
  { label: "Keto & Paleo", status: "Compatible" },
]

/** Anchor of the catalog rendered right below the hero on the portal home. */
export const CATALOG_ANCHOR = "catalogo"

// Entrance: opacity + transform only (compositor), expo-out, disabled under
// prefers-reduced-motion. Keyframes live in components/ui/theme.ts.
const ENTRANCE = "600ms cubic-bezier(0.16, 1, 0.3, 1) both"
const PANEL_DELAY_MS = 150
const ROW_BASE_DELAY_MS = 300
const ROW_STAGGER_MS = 80

// Ledger ruling: a faint 40px grid in the muted rule token, so it follows the mode.
const LEDGER_GRID = {
  backgroundImage:
    "linear-gradient(var(--chakra-colors-border-muted) 1px, transparent 1px), linear-gradient(90deg, var(--chakra-colors-border-muted) 1px, transparent 1px)",
  backgroundSize: "40px 40px",
}

/**
 * Portal home hero. Layout and motion follow the djangoblaze.com hero
 * (copy + one action on the left, an evidence panel on the right, rise/slide
 * entrance with staggered rows); every color, type and shape comes from the
 * Toscana design system (DESIGN.md): flat surfaces, 1px rules, coral as the
 * only action accent, positive state in green.fg. No product photography.
 */
export function HeroSection() {
  return (
    <Box as="section" aria-labelledby="hero-title" bg="bg" css={LEDGER_GRID} borderBottomWidth="1px" borderColor="border.muted">
      <Box maxW="6xl" mx="auto" px={{ base: 6, sm: 8 }} pt={{ base: 14, md: 20 }} pb={{ base: 14, md: 16 }}>
        <Grid templateColumns={{ base: "1fr", lg: "repeat(12, minmax(0, 1fr))" }} gap={{ base: 12, lg: 14 }} alignItems="start">
          <GridItem colSpan={{ base: 1, lg: 6 }} animation={`hero-rise ${ENTRANCE}`} _motionReduce={{ animation: "none" }}>
            <Text fontSize="sm" fontWeight="semibold" color="brand.fg" mb={6}>
              Horneando momentos
            </Text>

            <Heading
              as="h1"
              id="hero-title"
              fontSize={{ base: "2.5rem", sm: "3rem", lg: "3.75rem" }}
              fontWeight="extrabold"
              lineHeight="1.05"
              color="fg"
              css={{ textWrap: "balance" }}
            >
              Pastelería natural,{" "}
              <Box as="span" display="block" color="brand.fg">
                para cada momento.
              </Box>
            </Heading>

            <Text mt={7} maxW="xl" fontSize={{ base: "md", sm: "lg" }} lineHeight="tall" color="fg.muted" css={{ textWrap: "pretty" }}>
              Elegí del catálogo con los precios de tu lista, armá tu pedido y seguilo hasta que llega.
            </Text>

            <Box mt={9}>
              <Button asChild colorPalette="brand" h="56px" px={9} w={{ base: "full", sm: "auto" }} fontSize="md" fontWeight="bold" className="group">
                <a href={`#${CATALOG_ANCHOR}`}>
                  Ver el catálogo
                  <Icon
                    asChild
                    boxSize={4}
                    ml={1}
                    transition="transform 200ms ease-out"
                    _groupHover={{ transform: "translateX(4px)" }}
                    _motionReduce={{ transition: "none" }}
                  >
                    <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                  </Icon>
                </a>
              </Button>

              <Text mt={5} fontSize="md" lineHeight="tall" color="fg.muted">
                ¿Ya pediste?{" "}
                <Link asChild color="brand.fg" fontWeight="semibold" textDecoration="underline" textUnderlineOffset="3px">
                  <NextLink href="/my-orders">Mirá tus pedidos</NextLink>
                </Link>{" "}
                y en qué estado está cada uno.
              </Text>
            </Box>
          </GridItem>

          <GridItem
            colSpan={{ base: 1, lg: 6 }}
            animation={{ base: `hero-rise ${ENTRANCE}`, lg: `hero-slide ${ENTRANCE}` }}
            animationDelay={`${PANEL_DELAY_MS}ms`}
            _motionReduce={{ animation: "none" }}
          >
            <Box borderWidth="1px" borderColor="border" bg="bg.panel" rounded="lg" overflow="hidden">
              <Flex align="center" justify="space-between" h="44px" px={{ base: 4, sm: 5 }} bg="bg.muted" borderBottomWidth="1px" borderColor="border">
                <Text id="hero-attributes" fontSize="sm" fontWeight="semibold" color="fg">
                  Etiquetas del catálogo
                </Text>
                <Text fontSize="xs" color="fg.muted">
                  En cada producto
                </Text>
              </Flex>

              <Box as="ul" aria-labelledby="hero-attributes" listStyleType="none" px={{ base: 4, sm: 5 }} py={2}>
                {HERO_ATTRIBUTES.map(({ label, status }, index) => (
                  <Flex
                    as="li"
                    key={label}
                    align="center"
                    justify="space-between"
                    gap={4}
                    minH="52px"
                    borderBottomWidth={index < HERO_ATTRIBUTES.length - 1 ? "1px" : "0"}
                    borderColor="border.muted"
                    animation={`hero-rise ${ENTRANCE}`}
                    animationDelay={`${PANEL_DELAY_MS + ROW_BASE_DELAY_MS + index * ROW_STAGGER_MS}ms`}
                    _motionReduce={{ animation: "none" }}
                  >
                    <Text fontSize={{ base: "md", sm: "lg" }} fontWeight="semibold" color="fg">
                      {label}
                    </Text>
                    <Text fontSize="sm" fontWeight="medium" color="green.fg" textAlign="right">
                      {status}
                    </Text>
                  </Flex>
                ))}
              </Box>

              <Flex align="center" justify="space-between" gap={4} px={{ base: 4, sm: 5 }} py={4} borderTopWidth="1px" borderColor="border">
                <BrandLogo variant="horizontal" height={28} />
                <Text fontSize="sm" color="fg.muted" textAlign="right">
                  Pastelería artesanal
                </Text>
              </Flex>
            </Box>
          </GridItem>
        </Grid>
      </Box>
    </Box>
  )
}
