"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Flex,
  Image,
  SegmentGroup,
  Table,
  Text,
} from "@chakra-ui/react";
import { useRouter, useSearchParams } from "next/navigation";
import NextLink from "next/link";
import { CatalogSkeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/AuthContext";
import { gooeyToast } from "goey-toast";
import { isPortalRole } from "@/lib/portalRoutes";
import {
  canSwitchAudience,
  roleAllowedAudiences,
  roleDefaultDisplayAudience,
} from "@/lib/roleAudience";
import { addCartItem } from "@/services/cartService";
import { fetchStoreList } from "@/services/storeService";
import { downloadPricelistCSV, downloadPricelistPDF } from "@/services/pricingService";
import type { Audience, Product } from "@/types/pricing";

function audienceLabel(audience: Audience): string {
  return audience === "revendedores" ? "Revendedores" : "Consumidor final";
}

function formatPrice(value: string | null): string {
  if (value === null) return "—";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return parsed.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function ProductsCatalog() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [audience, setAudience] = useState<Audience>("revendedores");
  const [addingId, setAddingId] = useState<string | null>(null);

  const q = (searchParams.get("q") ?? "").trim().slice(0, 120);

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

  const processedRoleRef = useRef<string | null>(null);

  useEffect(() => {
    if (processedRoleRef.current === role) return;
    processedRoleRef.current = role;
    const defaultAud = roleDefaultDisplayAudience(role);
    if (allowedAudiences.includes(defaultAud)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAudience(defaultAud);
    }
  }, [role, allowedAudiences]);

  useEffect(() => {
    let cancelled = false;

    if (!allowedAudiences.includes(audience)) return;

    async function load() {
      try {
        const response = await fetchStoreList(audience, q || undefined);
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

    load();
    return () => {
      cancelled = true;
    };
  }, [audience, allowedAudiences, q]);

  if (loading) {
    return <CatalogSkeleton />;
  }

  return (
    <Flex direction="column" gap={4}>
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
          <Badge colorPalette="brand" size="lg">{audienceLabel(audience)}</Badge>
        )}

        <Flex gap={2} align="center" wrap="wrap">
          {q && (
            <Badge colorPalette="brand" variant="subtle" size="lg" px={3} py={1}>
              Búsqueda: {q}
            </Badge>
          )}
          {q && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.replace("/")}
              aria-label={`Quitar búsqueda ${q}`}
            >
              Quitar
            </Button>
          )}
          {role === "admin" && (
            <>
              <Button variant="outline" size="sm" onClick={() => downloadPricelistCSV(audience)}>
                Exportar CSV
              </Button>
              <Button variant="outline" size="sm" onClick={() => downloadPricelistPDF(audience)}>
                Exportar PDF
              </Button>
            </>
          )}
        </Flex>
      </Flex>

      {products.length === 0 ? (
        <Box
          border="1px"
          borderColor="border.muted"
          rounded="md"
          py={10}
          textAlign="center"
        >
          <Text color="fg.muted">
            {q
              ? `No hay productos que coincidan con «${q}».`
              : "No hay productos para esta audiencia."}
          </Text>
        </Box>
      ) : (
        <Table.ScrollArea rounded="md">
          <Table.Root size="md" variant="outline" interactive>
            <Table.Header>
              <Table.Row bg="bg.muted">
                <Table.ColumnHeader>Producto</Table.ColumnHeader>
                <Table.ColumnHeader w="11rem" textAlign="end">Precio</Table.ColumnHeader>
                {showCart && <Table.ColumnHeader srOnly>Agregar</Table.ColumnHeader>}
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {products.map((product) => (
                <Table.Row key={product.id}>
                  <Table.Cell>
                    <Flex align="center" gap={3}>
                      <Box
                        boxSize="2.5rem"
                        rounded="md"
                        overflow="hidden"
                        bg="bg.muted"
                        flexShrink={0}
                      >
                        {product.image_url ? (
                          <Image
                            src={product.image_url}
                            alt={`Imagen de ${product.name}`}
                            boxSize="100%"
                            objectFit="cover"
                          />
                        ) : null}
                      </Box>
                      <Flex direction="column" gap={1}>
                        <NextLink
                          href={`/productos/${product.id}`}
                          style={{
                            color: "inherit",
                            fontWeight: 500,
                            textDecoration: "none",
                          }}
                        >
                          {product.name}
                        </NextLink>
                        <Text fontSize="sm" color="fg.muted">
                          {product.category}
                        </Text>
                      </Flex>
                    </Flex>
                  </Table.Cell>
                  <Table.Cell textAlign="end" fontVariantNumeric="tabular-nums">
                    <Flex direction="column" gap={0.5} align="flex-end">
                      <Text fontWeight="medium">${formatPrice(product.price)}</Text>
                      {product.price_per_serving && (
                        <Text fontSize="xs" color="fg.muted">
                          ${formatPrice(product.price_per_serving)} por porción
                        </Text>
                      )}
                    </Flex>
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
