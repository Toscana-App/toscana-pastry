"use client"

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Box, Container, Heading, Flex } from "@chakra-ui/react";
import { ProfileSkeleton } from "@/components/ui/skeleton";

import { authService } from "@/services/authService";
import AddressBook from "@/components/profile/AddressBook";
import { ProfileCard } from "@/components/profile/ProfileCard";
import { User } from "@/types/auth";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { toaster } from "@/lib/toaster";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;

    async function fetchProfile() {
      try {
        const response = await authService.getUser();
        if (cancelled) return;
        setUser({
          id: response.user_id,
          email: response.email,
          role: response.role,
          googleId: response.google_id,
        });
      } catch {
        if (cancelled) return;
        toaster.create({
          title: "Error",
          description: "No se pudo cargar la información de tu cuenta.",
          type: "error",
        });
        router.push("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchProfile();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (loading || !user) {
    return <ProfileSkeleton />;
  }

  return (
    <ProtectedRoute>
      <Container py={10} maxW="container.sm">
        <Flex direction="column" align="center" gap={6} width="100%">
          <Heading fontSize="3xl">Mi cuenta</Heading>
          <ProfileCard user={user} />
          <Box w="100%">
            <AddressBook />
          </Box>
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
