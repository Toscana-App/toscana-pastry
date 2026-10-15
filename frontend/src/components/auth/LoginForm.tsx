"use client"

import { useState } from "react";
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  Stack,
  Heading,
  Text,
  useToast,
  Divider,
} from "@chakra-ui/react";
import { authService } from "@/services/authService";
import { GoogleIcon } from "@/components/ui/google-icon";
import { setCookie } from "@/lib/cookies";
import { useRouter } from "next/navigation";

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const router = useRouter();

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await authService.loginWithMagicLink(email);
      setCookie("auth_token", data.token, 7);
      toast({
        title: "Magic link sent!",
        description: "Check your email to log in.",
        status: "success",
        duration: 5000,
        isClosable: true,
      });
      router.push("/");
    } catch (error: any) {
      toast({
        title: "Login failed",
        description: error.message || "Please try again",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      const data = await authService.loginWithGoogle("google_test_id");
      setCookie("auth_token", data.token, 7);
      toast({
        title: "Logged in!",
        status: "success",
        duration: 3000,
        isClosable: true,
      });
      router.push("/");
    } catch (error: any) {
      toast({
        title: "Google login failed",
        description: error.message,
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false}
    }
  };

  return (
    <Box
      width="100%"
      maxW="400px"
      p={8}
      borderRadius="lg"
      borderWidth="1px"
      boxShadow="lg"
      bg="white"
    >
      <Stack spacing={6} align="center">
        <Heading size="lg" color="brand.600">
          Sign In
        </Heading>
        <Text color="gray.500" textAlign="center">
          Choose a method to continue
        </Text>
        <Divider />

        <form onSubmit={handleMagicLink} style={{ width: "100%" }}>
          <Stack spacing={4}>
            <FormControl isRequired>
              <FormLabel>Email Address</FormLabel>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </FormControl>
            <Button
              type="submit"
              colorScheme="brand"
              loading={loading}
              width="full"
            >
              Send Magic Link
            </Button>
          </Stack>
        </form>

        <Text fontSize="sm" color="gray.500">or</Text>

        <Button
          onClick={handleGoogleLogin}
          loading={loading}
          variant="outline"
          width="full"
          leftIcon={<GoogleIcon />}
        >
          Continue with Google
        </Button>
      </Stack>
    </Box>
  );
}
