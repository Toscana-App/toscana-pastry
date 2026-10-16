"use client"

import {
  Box,
  Heading,
  Text,
  VStack,
  Divider,
  HStack,
  Avatar,
  useColorModeValue,
  Badge,
} from "@chakra-ui/react";
import { User } from "@/types/auth";

interface ProfileCardProps {
  user: User;
}

export function ProfileCard({ user }: ProfileCardProps) {
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  const getRoleColor = (role: string) => {
    if (role === "admin") return "red";
    return "blue";
  };

  return (
    <Box
      width="100%"
      maxW="450px"
      p={8}
      borderRadius="xl"
      borderWidth="1px"
      borderColor={borderColor}
      bg={bgColor}
      boxShadow="lg"
    >
      <VStack spacing={6} align="center">
        <Avatar
          size="2xl"
          name={user.email}
          fallback={user.email.charAt(0).toUpperCase()}
          colorScheme="brand"
        />
        <VStack spacing={1}>
          <Heading size="lg">User Profile</Heading>
          <Badge colorScheme={getRoleColor(user.role)}>
            {user.role.toUpperCase()}
          </Badge>
        </VStack>
        <Divider />
        <VStack width="full" align="start" spacing={3}>
          <HStack justifyContent="space-between" width="full">
            <Text fontWeight="medium">Email</Text>
            <Text color="gray.600" fontWeight="bold">{user.email}</Text>
          </HStack>
          {user.googleId && (
            <HStack justifyContent="space-between" width="full">
              <Text fontWeight="medium">Google ID</Text>
              <Text color="gray.600" fontWeight="bold">{user.googleId}</Text>
            </HStack>
          )}
          <HStack justifyContent="space-between" width="full">
            <Text fontWeight="medium">Account ID</Text>
            <Text color="gray.600" fontWeight="bold">{user.id}</Text>
          </HStack>
        </VStack>
      </VStack>
    </Box>
  );
}
