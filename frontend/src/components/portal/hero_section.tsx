"use client"

import { Box, Button, Flex, Grid, Heading, Icon, Link, Text } from "@chakra-ui/react"
import NextLink from "next/link"

interface HeroAttribute {
  label: string
  status: string
}

export const HERO_ATTRIBUTES: readonly HeroAttribute[] = [
  { label: "Sin gluten", status: "100% harina de almendras" },
  { label: "100% Natural", status: "Sin conservantes" },
  { label: "Ricos", status: "Pastelería artesanal" },
]

export const CATALOG_ANCHOR = "catalogo"

const ENTRANCE = "600ms cubic-bezier(0.16, 1, 0.3, 1) both"
const WELCOME_DELAY_MS = 0
const CARD_BASE_DELAY_MS = 200
const CARD_STAGGER_MS = 90

export function HeroSection() {
  return (
    <Box as="section" aria-labelledby="hero-title" bg="bg" borderBottomWidth="1px" borderColor="border.muted">
      <Box maxW="6xl" mx="auto" px={{ base: 6, sm: 8 }} pt={{ base: 14, md: 20 }} pb={{ base: 14, md: 16 }}>
        <Box
          textAlign="center"
          maxW="3xl"
          mx="auto"
          animation={`hero-rise ${ENTRANCE}`}
          animationDelay={`${WELCOME_DELAY_MS}ms`}
          _motionReduce={{ animation: "none" }}
        >
          <Text fontSize="sm" fontWeight="semibold" color="brand.fg" mb={5}>
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

          <Text mt={7} fontSize={{ base: "md", sm: "lg" }} lineHeight="tall" color="fg.muted" css={{ textWrap: "pretty" }}>
            Sin gluten, sanos y ricos. Elegí del catálogo con los precios de tu lista, armá tu pedido y seguilo hasta que llega.
          </Text>

          <Box mt={9} display="flex" flexDirection="column" alignItems="center" gap={5}>
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

            <Text fontSize="md" lineHeight="tall" color="fg.muted">
              ¿Ya pediste?{" "}
              <Link asChild color="brand.fg" fontWeight="semibold" textDecoration="underline" textUnderlineOffset="3px">
                <NextLink href="/my-orders">Mirá tus pedidos</NextLink>
              </Link>{" "}
              y en qué estado está cada uno.
            </Text>
          </Box>
        </Box>

        <Box
          as="ul"
          aria-label="Etiquetas del catálogo"
          listStyleType="none"
          mt={{ base: 10, md: 12 }}
          display="grid"
          gridTemplateColumns={{ base: "1fr", sm: "repeat(3, minmax(0, 1fr))" }}
          gap={4}
        >
          {HERO_ATTRIBUTES.map(({ label, status }, index) => (
            <Box
              as="li"
              key={label}
              borderWidth="1px"
              borderColor="border"
              bg="bg.panel"
              rounded="lg"
              p={{ base: 5, sm: 6 }}
              textAlign="center"
              animation={`hero-rise ${ENTRANCE}`}
              animationDelay={`${CARD_BASE_DELAY_MS + index * CARD_STAGGER_MS}ms`}
              _motionReduce={{ animation: "none" }}
            >
              <Text fontSize={{ base: "md", sm: "lg" }} fontWeight="semibold" color="fg">
                {label}
              </Text>
              <Text mt={1} fontSize="sm" fontWeight="medium" color="green.fg">
                {status}
              </Text>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  )
}
