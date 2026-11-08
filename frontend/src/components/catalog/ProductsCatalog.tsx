"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Flex,
  SegmentGroup,
  Table,
  Text,
} from "@chakra-ui/react";
import { CatalogSkeleton } from "@/components/ui/skeleton";

import { useAuth } from "@/contexts/AuthContext";
import { apiFetch } from "@/lib/api";
import { gooeyToast } from "goey-toast";
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

/** Prices arrive as decimal strings ("4.34"); render with locale grouping. */
function formatPrice(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return parsed.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Product catalog with the price derived from the role's audience
 * (T5 — dual roles) + restriction tags "when present" (p11 UC-02).
 *
 * Reused by:
 * - the portal ("Inicio" tab, route "/") for business/customer
 * - the admin "/products" page (same component, no second pricing path
 *   — RNF-P11-03).
 *
 * The price always comes from the backend (`/products?audience=`): the
 * client never recalculates or persists prices.
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
        gooeyToast.success("¡Agregado al carrito!", { description: name });
      } catch (error) {
        gooeyToast.error("¡Ups! No se pudo agregar al carrito", {
          description:
            error instanceof Error ? error.message : "Intenta de nuevo",
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

  // Fetch products for the selected audience. Until the auth role is known
  // (or the role does not allow the current audience) no request is fired:
  // otherwise a customer mounting the page would trigger a guaranteed-403
  // fetch against "revendedores" before the role effect switches the audience.
  useEffect(() => {
    let cancelled = false;

    if (!allowedAudiences.includes(audience)) return;

    async function fetchProducts() {
      try {
        const response = await apiFetch<ProductListResponse>(
          `/products?audience=${audience}`
        );
        if (!cancelled) setProducts(response.products ?? []);
      } catch (error) {
        if (cancelled) return;
        gooeyToast.error("¡Ups! No se pudieron cargar los productos", {
          description:
            error instanceof Error ? error.message : "Intenta de nuevo.",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchProducts();
    return () => {
      cancelled = true;
    };
  }, [audience, allowedAudiences]);

  if (loading) {
    return <CatalogSkeleton />;
  }

  return (
    <Flex direction="column" gap={4}>
      {/* Toolbar: which list (switcher for admin, label for portal roles)
          + export of that same list. */}
      <Flex align="center" justify="space-between" gap={3} wrap="wrap">
        {canSwitch ? (
          <SegmentGroup.Root
            size="sm"
            value={audience}
            onValueChange={(details) => setAudience(details.value as Audience)}
          >
            <SegmentGroup.Indicator />
            <SegmentGroup.Items
              items={allowedAudiences.map((aud) => ({
                value: aud,
                label: audienceLabel(aud),
              }))}
            />
          </SegmentGroup.Root>
        ) : (
          // Restriction tag: this list is ONLY for the role's audience.
          <Badge colorPalette="brand" size="lg">{audienceLabel(audience)}</Badge>
        )}

        <Flex gap={2}>
          <Button variant="outline" size="sm" onClick={() => downloadPricelistCSV(audience)}>
            Exportar CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => downloadPricelistPDF(audience)}>
            Exportar PDF
          </Button>
        </Flex>
      </Flex>

      {/* Product table */}
      {products.length === 0 ? (
        <Box
          border="1px"
          borderColor="border.muted"
          rounded="md"
          py={10}
          textAlign="center"
        >
          <Text color="fg.muted">No hay productos para esta audiencia.</Text>
        </Box>
      ) : (
        <Table.ScrollArea rounded="md">
          <Table.Root size="md" variant="outline" interactive>
            <Table.Header>
              <Table.Row bg="bg.muted">
                <Table.ColumnHeader>Producto</Table.ColumnHeader>
                <Table.ColumnHeader w="8rem">Unidad</Table.ColumnHeader>
                <Table.ColumnHeader w="9rem" textAlign="end">Precio</Table.ColumnHeader>
                {showCart && <Table.ColumnHeader srOnly>Agregar</Table.ColumnHeader>}
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {products.map((product: Product) => (
                <Table.Row key={product.id}>
                  <Table.Cell>
                    <Flex direction="column" gap={1}>
                      <Text>{product.name}</Text>
                      {/* Restriction tags (gluten-free, etc.) — when present. */}
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
                  <Table.Cell color="fg.muted">{product.unit}</Table.Cell>
                  <Table.Cell textAlign="end" fontWeight="medium" fontVariantNumeric="tabular-nums">
                    ${formatPrice(product.price_per_unit)}
                  </Table.Cell>
                  {showCart && (
                    <Table.Cell textAlign="end">
                      <Button
                        size="sm"
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
