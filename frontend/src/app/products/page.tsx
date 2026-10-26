"use client";

import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Container,
  Flex,
  Heading,
  SegmentGroup,
  Spinner,
  Table,
  Text,
} from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { toaster } from "@/lib/toaster";
import { Audience, Product } from "@/types/pricing";
import {
  canSwitchAudience,
  roleAllowedAudiences,
  roleDefaultDisplayAudience,
} from "@/lib/roleAudience";
import { downloadPricelistCSV, downloadPricelistPDF } from "@/services/pricingService";

interface ProductListResponse {
  products: Product[];
  total: number;
}

/** Audience label for display. */
function audienceLabel(audience: Audience): string {
  return audience === "revendedores" ? "Revendedores" : "Consumidor final";
}

export default function ProductsPage() {
  const { user } = useAuth();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [audience, setAudience] = useState<Audience>("revendedores");

  const role = user?.role ?? "";
  const allowedAudiences = roleAllowedAudiences(role);
  const canSwitch = canSwitchAudience(role);

  // Track the last role we processed to avoid duplicate initializations.
  const processedRoleRef = useRef<string | null>(null);

  // Pick the default audience for the role on mount / role change.
  useEffect(() => {
    if (processedRoleRef.current === role) return;
    processedRoleRef.current = role;
    const defaultAud = roleDefaultDisplayAudience(role);
    if (allowedAudiences.includes(defaultAud)) {
      // Synchronous setState is intentional here — role is an external
      // system change (auth context), not a React state cascade.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAudience(defaultAud);
    }
  }, [role, allowedAudiences]);

  // Fetch products for the selected audience.
  useEffect(() => {
    let cancelled = false;

    async function fetchProducts() {
      try {
        const response = await apiFetch<ProductListResponse>(
          `/products?audience=${audience}`
        );
        if (!cancelled) setProducts(response.products ?? []);
      } catch (error) {
        if (cancelled) return;
        toaster.create({
          title: "Error",
          description:
            error instanceof Error ? error.message : "Could not load products.",
          type: "error",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchProducts();
    return () => {
      cancelled = true;
    };
  }, [audience]);

  if (loading) {
    return (
      <Flex align="center" justify="center" py={16}>
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Container py={10} maxW="container.md">
      <Flex direction="column" gap={6}>
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Heading size="3xl">Price List</Heading>

          <Flex align="center" gap={3} wrap="wrap">
            {canSwitch && (
              <SegmentGroup.Root
                size="sm"
                value={audience}
                onValueChange={(details) =>
                  setAudience(details.value as Audience)
                }
              >
                <SegmentGroup.Items
                  items={allowedAudiences.map((aud) => ({
                    value: aud,
                    label: audienceLabel(aud),
                  }))}
                />
              </SegmentGroup.Root>
            )}

            <Badge colorPalette="brand">{audienceLabel(audience)}</Badge>
          </Flex>
        </Flex>

        {/* Export CTAs — only for allowed audiences */}
        {allowedAudiences.map((aud) => (
          <Flex key={aud} gap={3} wrap="wrap">
            <Button
              colorPalette="brand"
              size="sm"
              onClick={() => downloadPricelistCSV(aud)}
            >
              Export CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadPricelistPDF(aud)}
            >
              Export PDF
            </Button>
          </Flex>
        ))}

        {/* Product table */}
        {products.length === 0 ? (
          <Box
            border="1px"
            borderColor="border.muted"
            rounded="md"
            py={10}
            textAlign="center"
          >
            <Text color="fg.muted">
              No products found for this audience.
            </Text>
          </Box>
        ) : (
          <Table.ScrollArea rounded="md">
            <Table.Root size="sm" variant="outline" striped>
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader>Product</Table.ColumnHeader>
                  <Table.ColumnHeader>Unit</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">
                    Price
                  </Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {products.map((product: Product) => (
                  <Table.Row key={product.id}>
                    <Table.Cell>{product.name}</Table.Cell>
                    <Table.Cell>{product.unit}</Table.Cell>
                    <Table.Cell textAlign="end">
                      ${product.price_per_unit}
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          </Table.ScrollArea>
        )}
      </Flex>
    </Container>
  );
}
