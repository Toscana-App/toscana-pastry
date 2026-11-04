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
  VStack,
  Text,
  Heading,
} from "@chakra-ui/react";
import { HeartIcon, CrownIcon, ZapIcon, CheckIcon, XIcon } from "./icons";
import { motion } from "framer-motion";

/** Brand color constants — avoids useToken type inference issues. */
const CORAL = "#ff7078";
const PEACH = "#f5ccad";
const TEAL = "#75bda3";

/** Simple div-based progress bar (Chakra v3 Progress is a namespace). */
const PlanProgress = ({ value, highlight }: { value: number; highlight: boolean }) => (
  <Box h="6px" bg="border.muted" borderRadius="full" overflow="hidden" w="full">
    <Box
      h="full"
      w={`${value}%`}
      bg={highlight ? TEAL : "border.emphasized"}
      borderRadius="full"
      transition="width 0.4s ease"
    />
  </Box>
);

const PricingSection = () => {
  const pricingPlans = [
    {
      id: "basic",
      name: "Cocina Casera",
      subtitle: "Para empezar tu experiencia pastelería",
      Icon: HeartIcon,
      color: CORAL,
      price: "129",
      period: "/mes",
      description: "Perfecto para quienes comienzan su aventura con pasteles caseros",
      features: [
        { name: "Acceso a 5 recetas básicas", included: true },
        { name: "Videos tutoriales paso a paso", included: true },
        { name: "Soporte por email", included: true },
        { name: "Acceso a comunidad básica", included: false },
        { name: "Recetas exclusivas semanales", included: false },
        { name: "Asesoría personalizada 1x1", included: false },
      ],
      popular: false,
      badge: "Principiante",
      badgeColor: "brand" as const,
    },
    {
      id: "pro",
      name: "Maestro Pastelero",
      subtitle: "Para los apasionados de la repostería",
      Icon: CrownIcon,
      color: TEAL,
      price: "249",
      period: "/mes",
      description: "Nivel intermedio con acceso completo a contenido premium",
      features: [
        { name: "Acceso ilimitado a 50+ recetas", included: true },
        { name: "Videos tutoriales avanzados", included: true },
        { name: "Soporte prioritario 24/7", included: true },
        { name: "Acceso a comunidad premium", included: true },
        { name: "Recetas exclusivas semanales", included: true },
        { name: "Asesoría personalizada 2x1", included: false },
      ],
      popular: true,
      badge: "Más popular",
      badgeColor: "green" as const,
    },
    {
      id: "elite",
      name: "Maestro Artesano",
      subtitle: "Para los expertos en repostería",
      Icon: ZapIcon,
      color: PEACH,
      price: "399",
      period: "/mes",
      description: "Acceso completo con beneficios exclusivos y servicios premium",
      features: [
        { name: "Acceso ilimitado a 200+ recetas", included: true },
        { name: "Videos tutoriales profesionales", included: true },
        { name: "Soporte VIP prioritario", included: true },
        { name: "Acceso a comunidad elite", included: true },
        { name: "Recetas exclusivas diarias", included: true },
        { name: "Asesoría personalizada mensual", included: true },
      ],
      popular: false,
      badge: "Máximo valor",
      badgeColor: "purple" as const,
    },
  ];

  return (
    <Box as="section" py={{ base: 12, md: 16 }} bg="bg">
      <Container maxW="container.xl">
        {/* Section header */}
        <Flex
          flexDirection="column"
          gap={4}
          mb={{ base: 10, md: 14 }}
          align="center"
          textAlign="center"
        >
          <Badge colorPalette="green" variant="subtle" px={3} py={1} fontSize="sm" borderRadius="full">
            Planes desde $129/mes
          </Badge>

          <Heading as="h2" size={{ base: "2xl", md: "3xl" }} color="fg" maxW="2xl" lineHeight="1.2">
            Elige el Plan Perfecto
          </Heading>

          <Text color="fg.muted" fontSize={{ base: "sm", md: "base" }} maxW="xl" lineHeight="1.5">
            Desde recetas básicas hasta maestría profesional, cada plan te lleva desde principiante hasta maestro
          </Text>
        </Flex>

        {/* Pricing grid */}
        <SimpleGrid columns={{ base: 1, md: 3 }} gap={{ base: 6, md: 8 }}>
          {pricingPlans.map((plan, index) => (
            <motion.div
              key={plan.id}
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
                borderWidth={plan.popular ? "2px" : "1px"}
                borderColor={plan.popular ? "brand.muted" : "border"}
                boxShadow={plan.popular ? "lg" : "none"}
                position="relative"
                transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
                _hover={{
                  boxShadow: plan.popular ? "xl" : "lg",
                  borderColor: plan.popular ? "brand.solid" : "border.emphasized",
                }}
              >
                {plan.popular && (
                  <Box
                    position="absolute"
                    top="-12px"
                    left="50%"
                    transform="translateX(-50%)"
                    zIndex={1}
                  >
                    <Badge
                      colorPalette="green"
                      variant="solid"
                      px={4}
                      py={1}
                      fontSize="xs"
                      fontWeight="bold"
                      borderRadius="full"
                      boxShadow="md"
                    >
                      {plan.badge}
                    </Badge>
                  </Box>
                )}

                <Card.Body
                  p={{ base: 6, md: 8 }}
                  flex="1"
                  display="flex"
                  flexDirection="column"
                  gap={5}
                >
                  {/* Icon + badge */}
                  <Flex align="start" justify="space-between">
                    <Flex
                      w={12}
                      h={12}
                      bg={`${plan.color}15`}
                      borderRadius="md"
                      align="center"
                      justify="center"
                    >
                      <plan.Icon size={6} color={plan.color} />
                    </Flex>
                    {!plan.popular && (
                      <Badge
                        colorPalette={plan.badgeColor}
                        variant="subtle"
                        fontSize="xs"
                        borderRadius="full"
                      >
                        {plan.badge}
                      </Badge>
                    )}
                  </Flex>

                  {/* Title */}
                  <Box>
                    <Card.Title fontSize="lg" fontWeight="semibold" color="fg">
                      {plan.name}
                    </Card.Title>
                    <Text fontSize="sm" color="fg.muted" mt={0.5}>
                      {plan.subtitle}
                    </Text>
                  </Box>

                  {/* Price */}
                  <HStack align="baseline" gap={1}>
                    <Text fontSize="sm" color="fg.muted" fontWeight="normal">
                      $
                    </Text>
                    <Text fontSize="4xl" fontWeight="bold" color="fg">
                      {plan.price}
                    </Text>
                    <Text fontSize="sm" color="fg.muted">
                      {plan.period}
                    </Text>
                  </HStack>

                  {/* Features */}
                  <VStack
                    align="start"
                    flex="1"
                    pt={4}
                    borderTopWidth="1px"
                    borderColor="border.muted"
                    gap={3}
                  >
                    {plan.features.map((feature, idx) => (
                      <HStack key={idx} gap={3} w="full">
                        <Box
                          p={1}
                          bg={feature.included ? "green.subtle" : "transparent"}
                          borderRadius="full"
                        >
                          {feature.included ? (
                            <CheckIcon size={3} color="green.fg" />
                          ) : (
                            <XIcon size={3} color="fg.subtle" />
                          )}
                        </Box>
                        <Text
                          fontSize="sm"
                          color={feature.included ? "fg" : "fg.subtle"}
                        >
                          {feature.name}
                        </Text>
                      </HStack>
                    ))}
                  </VStack>

                  {/* Progress */}
                  <Box>
                    <HStack justify="space-between" mb={2}>
                      <Text fontSize="xs" color="fg.muted">
                        Cobertura del plan
                      </Text>
                      <Text fontSize="xs" color="fg.muted">
                        {plan.features.filter((f) => f.included).length}/
                        {plan.features.length}
                      </Text>
                    </HStack>
                    <PlanProgress
                      value={
                        (plan.features.filter((f) => f.included).length /
                          plan.features.length) *
                        100
                      }
                      highlight={plan.popular}
                    />
                  </Box>

                  {/* CTA */}
                  <Button
                    w="full"
                    size="lg"
                    colorPalette={plan.popular ? "brand" : "gray"}
                    variant={plan.popular ? "solid" : "outline"}
                    borderRadius="sm"
                    py={4}
                    _hover={{ transform: "translateY(-2px)", boxShadow: "lg" }}
                    transition="all 0.15s cubic-bezier(0.4, 0, 0.2, 1)"
                  >
                    {plan.popular ? "Comenzar Ahora" : "Seleccionar Plan"}
                  </Button>
                </Card.Body>
              </Card.Root>
            </motion.div>
          ))}
        </SimpleGrid>
      </Container>
    </Box>
  );
};

export default PricingSection;
