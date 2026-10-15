"use client"

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Container,
  Heading,
  Text,
  Spinner,
  useToast,
  Box,
  Flex,
} from "@chakra-ui/react";
import { authService } from "@/services/authService";
import { ProfileCard } from "@/components/profile/ProfileCard";
import { User } from "@/types/auth";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();
  const router = useRouter();

  useEffect(() => {
    async function fetchProfile() {
      try {
        const response = await authService.getUser();
        const userInfo: User = {
          id: response.user_id,
          email: response.email,
          googleId: response.google_id,
        };
        setUser(userInfo);
      } catch (error: any) {
        console.error("Failed to fetch profile:", error);
        toast({
          title: "Error",
          description: "Could not load profile information.",
          status: "error",
          duration: 3000,
          isClosable: true,
        });
        router.push("/login");
      } finally {
        setLoading(false);
      }
    }

    fetchProfile();
  }, [router, toast]);

  if (loading || !user) {
    return (
      <Flex align="center" justify="center" minH="100dvh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <ProtectedRoute>
      <Container py={10} maxW="container.sm">
        <Flex direction="column" align="center" gap={6}>
          <Heading size="2xl">My Profile</Heading>
          <ProfileCard user={user} />
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
