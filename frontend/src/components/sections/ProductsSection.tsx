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
import { PackageIcon, CoffeeIcon, TrendingUpIcon } from "./icons";
import { motion } from "framer-motion";

const CORAL = "#ff7078";
const SAGE = "#cce0c9";
const TEAL = "#75bda3";

const ProductsSection = () => {

  const productCategories = [
    {
      id: "pastries",
      title: "Pasteles",
      description: "Selección de pasteles artesanales para cada ocasión",
      Icon: PackageIcon,
      color: CORAL,
      priceRange: "$15.00 - $45.00",
      itemCount: 24,
    },
    {
      id: "cookies",
      title: "Galletas Artesanales",
      description: "Galletas especiales con recetas clásicas y toques únicos",
      Icon: TrendingUpIcon,
      color: TEAL,
      priceRange: "$8.00 - $25.00",
      itemCount: 36,
    },
    {
      id: "drinks",
      title: "Bebidas Selectas",
      description: "Complementos para tus momentos especiales",
      Icon: CoffeeIcon,
      color: SAGE,
      priceRange: "$5.00 - $20.00",
      itemCount: 18,
    },
  ];

  return (
    <Box as="section" py={{ base: 12, md: 16 }} bg="bg">
      <Container maxW="container.xl">
        {/* Section header — impuestito pattern: badge + heading + description, centered */}
        <Flex
          flexDirection="column"
          gap={4}
          mb={{ base: 10, md: 14 }}
          align="center"
          textAlign="center"
        >
          <Badge colorPalette="brand" variant="subtle" px={3} py={1} fontSize="sm" borderRadius="full">
            {productCategories.length} categorías
          </Badge>

          <Heading as="h2" size={{ base: "2xl", md: "3xl" }} color="fg" maxW="2xl" lineHeight="1.2">
            Nuestros Productos
          </Heading>

          <Text color="fg.muted" fontSize={{ base: "sm", md: "base" }} maxW="xl" lineHeight="1.5">
            Delicias artesanales hechas con ingredientes seleccionados, perfectas para cada momento
          </Text>
        </Flex>

        {/* Product grid — impuestito card: outline, radius lg, subtle hover */}
        <SimpleGrid columns={{ base: 1, sm: 2, lg: 3 }} gap={{ base: 6, md: 8 }} mb={12}>
          {productCategories.map((category, index) => (
            <motion.div
              key={category.id}
              initial={{ opacity: 0, y: 20 }}
              whileHover={{ y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
            >
              <Card.Root
                variant="outline"
                size="lg"
                borderRadius="lg"
                height="full"
                transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
                _hover={{ boxShadow: "lg", borderColor: "border.emphasized" }}
              >
                <Card.Body gap={3} p={{ base: 5, md: 6 }} flex="1" display="flex" flexDirection="column">
                  {/* Icon — impuestito pattern: colored bg, radius md */}
                  <Flex
                    w={12}
                    h={12}
                    bg={`${category.color}15`}
                    borderRadius="md"
                    align="center"
                    justify="center"
                    mb={2}
                  >
                    <category.Icon size={6} color={category.color} />
                  </Flex>

                  <Card.Title fontSize="lg" fontWeight="semibold" color="fg">
                    {category.title}
                  </Card.Title>

                  <Card.Description fontSize="sm" color="fg.muted" lineHeight="1.5">
                    {category.description}
                  </Card.Description>

                  {/* Meta row */}
                  <HStack
                    justify="space-between"
                    align="center"
                    mt="auto"
                    pt={4}
                    borderTopWidth="1px"
                    borderColor="border.muted"
                  >
                    <Text fontSize="xs" color="fg.muted">
                      {category.itemCount} productos
                    </Text>
                    <Badge colorPalette="gray" variant="subtle" borderRadius="full" fontSize="xs">
                      {category.priceRange}
                    </Badge>
                  </HStack>
                </Card.Body>

                <Card.Footer justifyContent="flex-end" pt={0}>
                  <Button size="sm" colorPalette="brand" variant="outline" borderRadius="sm">
                    Ver productos
                  </Button>
                </Card.Footer>
              </Card.Root>
            </motion.div>
          ))}
        </SimpleGrid>

        {/* Action bar */}
        <Flex justify="center" gap={4} mt={4} flexWrap="wrap">
          <Button
            colorPalette="brand"
            size="lg"
            borderRadius="sm"
            px={8}
            py={5}
            _hover={{ transform: "translateY(-2px)", boxShadow: "lg" }}
            transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
          >
            Ver Catálogo Completo
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
            Cotizar Pedido
          </Button>
        </Flex>
      </Container>
    </Box>
  );
};

export default ProductsSection;
