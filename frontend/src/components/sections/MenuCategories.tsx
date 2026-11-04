"use client";

import {
  Box,
  Container,
  SimpleGrid,
  Card,
  Badge,
  Button,
  Flex,
  HStack,
  Text,
  Heading,
} from "@chakra-ui/react";
import {
  GiftIcon,
  CoffeeIcon,
  CookieIcon,
  UsersIcon,
  HeartIcon,
  StarIcon,
} from "./icons";
import { motion } from "framer-motion";

const CORAL = "#ff7078";
const SAGE = "#cce0c9";
const PEACH = "#f5ccad";
const TEAL = "#75bda3";

const MenuCategories = () => {

  const categories = [
    {
      id: "special-occasions",
      title: "Ocasiones Especiales",
      description: "Pasteles temáticos para cumpleaños, bodas y más",
      Icon: GiftIcon,
      color: CORAL,
      badge: "Popular",
      badgeColor: "brand",
      itemCount: 24,
      avgPrice: "$35.00",
    },
    {
      id: "daily-browse",
      title: "Para el Día a Día",
      description: "Nuestros favoritos diarios y cafés",
      Icon: CoffeeIcon,
      color: TEAL,
      badge: "Top ventas",
      badgeColor: "green",
      itemCount: 12,
      avgPrice: "$18.00",
    },
    {
      id: "sweet-tooth",
      title: "Tentaciones Dulces",
      description: "Galletas artesanales y postres especiales",
      Icon: CookieIcon,
      color: PEACH,
      badge: "Nuevo",
      badgeColor: "orange",
      itemCount: 18,
      avgPrice: "$12.00",
    },
    {
      id: "family-packages",
      title: "Paquetes Familiares",
      description: "Opciones perfectas para compartir en familia",
      Icon: UsersIcon,
      color: SAGE,
      badge: "Recomendado",
      badgeColor: "purple",
      itemCount: 8,
      avgPrice: "$45.00",
    },
    {
      id: "diet-friendly",
      title: "Opciones Saludables",
      description: "Delicias con ingredientes seleccionados",
      Icon: HeartIcon,
      color: CORAL,
      badge: "Premium",
      badgeColor: "brand",
      itemCount: 6,
      avgPrice: "$28.00",
    },
    {
      id: "seasonal-specials",
      title: "Especiales de Temporada",
      description: "Creaciones únicas de temporada limitada",
      Icon: StarIcon,
      color: PEACH,
      badge: "Limitado",
      badgeColor: "orange",
      itemCount: 4,
      avgPrice: "$55.00",
    },
  ];

  return (
    <Box as="section" py={{ base: 12, md: 16 }} bg="bg.subtle">
      <Container maxW="container.xl">
        {/* Section header */}
        <Flex
          flexDirection="column"
          gap={4}
          mb={{ base: 10, md: 14 }}
          align="center"
          textAlign="center"
        >
          <Badge colorPalette="brand" variant="subtle" px={3} py={1} fontSize="sm" borderRadius="full">
            {categories.length} categorías
          </Badge>

          <Heading as="h2" size={{ base: "2xl", md: "3xl" }} color="fg" maxW="2xl" lineHeight="1.2">
            Explora Nuestras Categorías
          </Heading>

          <Text color="fg.muted" fontSize={{ base: "sm", md: "base" }} maxW="xl" lineHeight="1.5">
            Selecciones organizadas para cada ocasión, desde delicias diarias hasta creaciones para momentos memorables
          </Text>
        </Flex>

        {/* Categories grid — impuestito pattern: outline cards, radius lg, clean meta row */}
        <SimpleGrid columns={{ base: 1, sm: 2, lg: 3 }} gap={{ base: 6, md: 8 }}>
          {categories.map((category, index) => (
            <motion.div
              key={category.id}
              initial={{ opacity: 0, y: 20 }}
              whileHover={{ y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.08 }}
            >
              <Card.Root
                variant="outline"
                size="lg"
                borderRadius="lg"
                height="full"
                position="relative"
                transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
                _hover={{ boxShadow: "lg", borderColor: "border.emphasized" }}
              >
                {/* Corner badge */}
                <Box position="absolute" top={4} right={4} zIndex={1}>
                  <Badge
                    colorPalette={category.badgeColor as any}
                    variant="subtle"
                    fontSize="xs"
                    borderRadius="full"
                    px={2.5}
                    py={0.5}
                  >
                    {category.badge}
                  </Badge>
                </Box>

                <Card.Body
                  p={{ base: 5, md: 6 }}
                  flex="1"
                  display="flex"
                  flexDirection="column"
                  gap={3}
                >
                  {/* Icon */}
                  <Flex
                    w={12}
                    h={12}
                    bg={`${category.color}15`}
                    borderRadius="md"
                    align="center"
                    justify="center"
                  >
                    <category.Icon size={6} color={category.color} />
                  </Flex>

                  <Box flex="1">
                    <Card.Title fontSize="lg" fontWeight="semibold" color="fg" mb={1}>
                      {category.title}
                    </Card.Title>
                    <Card.Description fontSize="sm" color="fg.muted" lineHeight="1.5">
                      {category.description}
                    </Card.Description>
                  </Box>

                  {/* Meta row */}
                  <HStack
                    justify="space-between"
                    align="center"
                    pt={4}
                    borderTopWidth="1px"
                    borderColor="border.muted"
                  >
                    <Text fontSize="xs" color="fg.muted">
                      {category.itemCount} productos, desde {category.avgPrice}
                    </Text>
                    <Button
                      size="xs"
                      colorPalette="brand"
                      variant="ghost"
                      borderRadius="sm"
                      px={3}
                    >
                      Explorar
                    </Button>
                  </HStack>
                </Card.Body>
              </Card.Root>
            </motion.div>
          ))}
        </SimpleGrid>

        {/* CTA */}
        <Flex justify="center" mt={{ base: 10, md: 14 }} gap={4} flexWrap="wrap">
          <Button
            colorPalette="brand"
            size="lg"
            borderRadius="sm"
            px={8}
            py={5}
            _hover={{ transform: "translateY(-2px)", boxShadow: "lg" }}
            transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
          >
            Ver Todo el Catálogo
          </Button>
          <Button
            variant="outline"
            size="lg"
            borderRadius="sm"
            px={8}
            py={5}
            _hover={{ bg: "bg.muted", transform: "translateY(-2px)" }}
            transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
          >
            Cotizar Personalizado
          </Button>
        </Flex>
      </Container>
    </Box>
  );
};

export default MenuCategories;
