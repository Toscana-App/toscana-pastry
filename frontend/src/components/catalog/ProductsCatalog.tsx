"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Flex,
  SegmentGroup,
  Spinner,
  Table,
  Text,
} from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { toaster } from "@/lib/toaster";
import { Audience, Product } from "@/types/pricing";
import { isPortalRole } from "@/lib/portalRoutes";
import { addCartItem } from "@/services/cartService";
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

/**
 * Catálogo de productos con el precio derivado de la audiencia del rol
 * (T5 — roles duales) + tags de restricción "si existen" (p11 UC-02).
 *
 * Reutilizado por:
 * - el portal (tab "Inicio", ruta "/") para negocio/cliente
 * - la página admin "/products" (mismo componente, sin segunda vía de
 *   cálculo — RNF-P11-03).
 *
 * El precio siempre viene del backend (`/products?audience=`): el cliente
 * nunca recalcula ni persiste precios.
 */
export function ProductsCatalog() {
  const { user } = useAuth();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [audience, setAudience] = useState<Audience>("revendedores");
  const [addingId, setAddingId] = useState<string | null>(null);

  const role = user?.role ?? "";
  const allowedAudiences = roleAllowedAudiences(role);
  const canSwitch = canSwitchAudience(role);
  const showCart = isPortalRole(user?.role);

  const addToCart = useCallback(
    async (productId: string, name: string) => {
      setAddingId(productId);
      try {
        await addCartItem(productId, 1);
        toaster.create({
          title: "Agregado al carrito",
          description: name,
          type: "success",
        });
      } catch (error) {
        toaster.create({
          title: "No se pudo agregar al carrito",
          description:
            error instanceof Error ? error.message : "Intentá de nuevo",
          type: "error",
        });
      } finally {
        setAddingId(null);
      }
    },
    []
  );

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
    <Flex direction="column" gap={4}>
      {/* Audience switcher (admin only) + restriction tag of this list */}
      <Flex align="center" gap={3} wrap="wrap">
        {canSwitch && (
          <SegmentGroup.Root
            size="sm"
            value={audience}
            onValueChange={(details) => setAudience(details.value as Audience)}
          >
            <SegmentGroup.Items
              items={allowedAudiences.map((aud) => ({
                value: aud,
                label: audienceLabel(aud),
              }))}
            />
          </SegmentGroup.Root>
        )}

        {/* Tag de restricción: esta lista es SOLO de la audiencia del rol. */}
        <Badge colorPalette="brand">{audienceLabel(audience)}</Badge>
      </Flex>

      {/* Export CTAs — only for allowed audiences */}
      {allowedAudiences.map((aud) => (
        <Flex key={aud} gap={3} wrap="wrap">
          <Button colorPalette="brand" size="sm" onClick={() => downloadPricelistCSV(aud)}>
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
          <Text color="fg.muted">No products found for this audience.</Text>
        </Box>
      ) : (
        <Table.ScrollArea rounded="md">
          <Table.Root size="sm" variant="outline" striped>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Product</Table.ColumnHeader>
                <Table.ColumnHeader>Unit</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="end">Price</Table.ColumnHeader>
                {showCart && <Table.ColumnHeader srOnly>Agregar</Table.ColumnHeader>}
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {products.map((product: Product) => (
                <Table.Row key={product.id}>
                  <Table.Cell>
                    <Flex direction="column" gap={1}>
                      <Text>{product.name}</Text>
                      {/* Tags de restricción (gluten-free, etc.) — si existen. */}
                      {product.tags && product.tags.length > 0 && (
                        <Flex gap={1} wrap="wrap">
                          {product.tags.map((tag) => (
                            <Badge key={tag} colorPalette="gray" variant="subtle">
                              {tag}
                            </Badge>
                          ))}
                        </Flex>
                      )}
                    </Flex>
                  </Table.Cell>
                  <Table.Cell>{product.unit}</Table.Cell>
                  <Table.Cell textAlign="end" fontFamily="var(--font-geist-mono)">
                    ${product.price_per_unit}
                  </Table.Cell>
                  {showCart && (
                    <Table.Cell textAlign="end">
                      <Button
                        size="xs"
                        variant="outline"
                        colorPalette="brand"
                        disabled={addingId !== null}
                        onClick={() => void addToCart(product.id, product.name)}
                        aria-label={`Agregar ${product.name} al carrito`}
                      >
                        Agregar
                      </Button>
                    </Table.Cell>
                  )}
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      )}
    </Flex>
  );
}
