"use client"

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Container, Heading, Spinner, Flex } from "@chakra-ui/react";
import { authService } from "@/services/authService";
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
          description: "Could not load profile information.",
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
          <Heading fontSize="3xl">My Profile</Heading>
          <ProfileCard user={user} />
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
