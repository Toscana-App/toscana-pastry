import type { Metadata } from "next";
import { StoreDetailShell } from "./StoreDetailShell";

export function generateStaticParams() {
  return [{ id: "preview" }];
}

export const metadata: Metadata = {
  title: "Producto",
};

export default async function ProductStoreRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <StoreDetailShell id={id} />;
}
