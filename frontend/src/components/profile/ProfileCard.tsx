"use client"

import {
  Box,
  Heading,
  Text,
  VStack,
  Separator,
  HStack,
  Avatar,
  Badge,
} from "@chakra-ui/react";
import { User } from "@/types/auth";

interface ProfileCardProps {
  user: User;
}

function roleColor(role: string) {
  return role === "admin" ? "red" : "blue";
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  negocio: "Negocio",
  customer: "Cliente",
};

export function ProfileCard({ user }: ProfileCardProps) {
  return (
    <Box
      width="100%"
      maxW="450px"
      p={8}
      borderRadius="xl"
      borderWidth="1px"
      borderColor="gray.200"
      bg="white"
      boxShadow="lg"
    >
      <VStack gap={6} align="center">
        <Avatar.Root size="2xl" colorPalette="brand">
          <Avatar.Fallback>{user.email.charAt(0).toUpperCase()}</Avatar.Fallback>
        </Avatar.Root>
        <VStack gap={1}>
          <Heading fontSize="xl">Perfil de usuario</Heading>
          <Badge colorPalette={roleColor(user.role)}>
            {ROLE_LABELS[user.role] ?? user.role}
          </Badge>
        </VStack>
        <Separator />
        <VStack width="full" align="start" gap={3}>
          <HStack justifyContent="space-between" width="full">
            <Text fontWeight="medium">Correo electrónico</Text>
            <Text color="gray.600" fontWeight="bold">{user.email}</Text>
          </HStack>
          {user.googleId && (
            <HStack justifyContent="space-between" width="full">
              <Text fontWeight="medium">Google ID</Text>
              <Text color="gray.600" fontWeight="bold">{user.googleId}</Text>
            </HStack>
          )}
          <HStack justifyContent="space-between" width="full">
            <Text fontWeight="medium">ID de cuenta</Text>
            <Text color="gray.600" fontWeight="bold">{user.id}</Text>
          </HStack>
        </VStack>
      </VStack>
    </Box>
  );
}
