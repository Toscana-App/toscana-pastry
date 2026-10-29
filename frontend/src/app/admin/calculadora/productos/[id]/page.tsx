"use client";

import { use, useEffect, useState } from "react";
import ProductEditor from "@/components/calc/ProductEditor";
import { calcProductsService } from "@/services/calcProductsService";
import { Spinner } from "@chakra-ui/react";
import { Flex } from "@chakra-ui/react";
import type { Product } from "@/types/calc";

export default function ProductEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProduct = async () => {
      try {
        const productData = await calcProductsService.getProduct(id);
        setProduct(productData.product);
      } catch (error) {
        console.error("Error fetching product:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchProduct();
  }, [id]);

  if (loading) {
    return (
      <Flex justify="center" align="center" minH="400px">
        <Spinner size="xl" />
      </Flex>
    );
  }

  return <ProductEditor initial={product || undefined} />;
}