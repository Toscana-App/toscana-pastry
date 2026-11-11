"use client";

import { useEffect, useState } from "react";
import { Badge, Card, Flex, Heading, Stack, Table, Text } from "@chakra-ui/react";
import { AdminUsersSkeleton } from "@/components/ui/skeleton";

import CouponsAdmin from "@/components/admin/CouponsAdmin";
import LeadAdmin from "@/components/admin/LeadAdmin";
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
          title: "¡Ups!",
          description:
            error instanceof Error
              ? error.message
              : "No se pudieron cargar los usuarios.",
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
    return <AdminUsersSkeleton />;
  }

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={4}>
          <Text color="fg.muted" fontVariantNumeric="tabular-nums" aria-live="polite">
            {data?.total ?? 0} usuario{data?.total === 1 ? "" : "s"} registrado
            {data?.total === 1 ? "" : "s"}
          </Text>
          {data && data.users.length === 0 ? (
            <Text fontSize="sm" color="fg.muted">
              Todavía no hay usuarios registrados.
            </Text>
          ) : (
            <Table.ScrollArea rounded="md">
              <Table.Root size="sm" variant="outline" stickyHeader>
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Correo</Table.ColumnHeader>
                    <Table.ColumnHeader>Rol</Table.ColumnHeader>
                    <Table.ColumnHeader>Autenticación</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {(data?.users ?? []).map((user) => (
                    <Table.Row key={user.user_id}>
                      <Table.Cell overflowWrap="anywhere">{user.email}</Table.Cell>
                      <Table.Cell>
                        <Badge
                          colorPalette={user.role === "admin" ? "red" : "brand"}
                          variant="subtle"
                        >
                          {user.role}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        {user.google_id ? "Google" : "Enlace mágico"}
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          )}
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export default function AdminPage() {
  return (
    <Flex direction="column" gap={6}>
      <Heading as="h1" fontSize="2xl" textWrap="balance">Usuarios</Heading>
      <AdminUsers />
      <CouponsAdmin />
      <LeadAdmin />
    </Flex>
  );
}
