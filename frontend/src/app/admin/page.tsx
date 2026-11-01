"use client";

import { useEffect, useState } from "react";
import { Badge, Flex, Heading, Spinner, Table, Text } from "@chakra-ui/react";
import { apiFetch } from "@/lib/api";
import { toaster } from "@/lib/toaster";
import type { UserRole } from "@/types/auth";

interface AdminUserItem {
  user_id: string;
  email: string;
  role: UserRole;
  google_id?: string | null;
}

interface UserListResponse {
  total: number;
  users: AdminUserItem[];
}

function AdminUsers() {
  const [data, setData] = useState<UserListResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchUsers() {
      try {
        const response = await apiFetch<UserListResponse>("/admin/users");
        if (!cancelled) setData(response);
      } catch (error) {
        if (cancelled) return;
        toaster.create({
          title: "Error",
          description: error instanceof Error ? error.message : "Could not load users.",
          type: "error",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchUsers();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <Flex align="center" justify="center" py={16}>
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={4}>
      <Text color="fg.muted">{data?.total ?? 0} registered users</Text>
      <Table.ScrollArea borderWidth="1px" rounded="md">
        <Table.Root size="sm" stickyHeader>
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Email</Table.ColumnHeader>
              <Table.ColumnHeader>Role</Table.ColumnHeader>
              <Table.ColumnHeader>Auth</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {(data?.users ?? []).map((user) => (
              <Table.Row key={user.user_id}>
                <Table.Cell>{user.email}</Table.Cell>
                <Table.Cell>
                  <Badge colorPalette={user.role === "admin" ? "red" : "gray"}>
                    {user.role}
                  </Badge>
                </Table.Cell>
                <Table.Cell>{user.google_id ? "Google" : "Magic link"}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Table.ScrollArea>
    </Flex>
  );
}

export default function AdminPage() {
  return (
    <Flex direction="column" gap={6}>
      <Heading fontSize="2xl">Usuarios</Heading>
      <AdminUsers />
    </Flex>
  );
}
