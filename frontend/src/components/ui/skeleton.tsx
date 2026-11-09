"use client";

import type { ReactNode } from "react";
import {
  Box,
  Card,
  Flex,
  Heading,
  SimpleGrid,
  Skeleton,
  SkeletonCircle,
  Stack,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react";

export function SkeletonLine({ w = "100%", h = "4" }: { w?: string; h?: string }) {
  return <Skeleton height={h} width={w} />;
}

export function FieldSkeleton({
  labelWidth = "45%",
  inputHeight = "2.5rem",
}: {
  labelWidth?: string;
  inputHeight?: string;
}) {
  return (
    <Flex direction="column" gap="1" width="full">
      <SkeletonLine w={labelWidth} h="3" />
      <Skeleton height={inputHeight} borderRadius="lg" />
    </Flex>
  );
}

export function SkeletonTable({
  rows = 6,
  cols,
  withHeader = true,
}: {
  rows?: number;
  cols: string[];
  withHeader?: boolean;
}) {
  return (
    <Box
      borderWidth="1px"
      borderColor="border.muted"
      borderRadius="md"
      overflow="hidden"
      width="full"
    >
      <Table.Root variant="line" size="sm">
        {withHeader ? (
          <Table.Header>
            <Table.Row
              bg="bg.subtle"
              borderBottomWidth="1px"
              borderColor="border.muted"
            >
              {cols.map((w, i) => (
                <Table.ColumnHeader key={i} width={w} color="transparent">
                  <SkeletonLine h="3" />
                </Table.ColumnHeader>
              ))}
            </Table.Row>
          </Table.Header>
        ) : null}
        <Table.Body>
          {Array.from({ length: rows }).map((_, r) => (
            <Table.Row key={r}>
              {cols.map((_, c) => (
                <Table.Cell key={c}>
                  <SkeletonLine
                    h="3"
                    w={c === cols.length - 1 ? "45%" : "70%"}
                  />
                </Table.Cell>
              ))}
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  );
}

export function SkeletonCard({
  height,
  children,
}: {
  height?: string;
  children?: ReactNode;
}) {
  return (
    <Card.Root>
      <Card.Body h={height} py={4}>
        {children}
      </Card.Body>
    </Card.Root>
  );
}

export function ShimmerDot({ size = "16px" }: { size?: string }) {
  return <Skeleton width={size} height={size} borderRadius="full" />;
}

export function FullPageSkeleton() {
  return (
    <Flex
      direction="column"
      minH="100dvh"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Skeleton h="4rem" w="full" />
      <Box
        w="full"
        display="flex"
        justifyContent="center"
        pt="10"
        px="4"
        pb="8"
      >
        <Stack width="full" maxW="container.sm" gap="4">
          <Skeleton h="10" w="45%" alignSelf="center" />
          <Skeleton h="12" w="100%" borderRadius="xl" />
          <Skeleton h="12" w="100%" borderRadius="xl" />
          <Skeleton h="12" w="100%" borderRadius="xl" />
        </Stack>
      </Box>
    </Flex>
  );
}

export function ProfileSkeleton() {
  return (
    <Flex
      direction="column"
      align="center"
      gap={6}
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Heading fontSize="3xl">Mi cuenta</Heading>
      <Box
        width="full"
        maxW="450px"
        p={8}
        borderRadius="xl"
        borderWidth="1px"
        borderColor="border"
        bg="bg.panel"
        boxShadow="lg"
      >
        <VStack gap={6} align="center" width="full">
          {}
          <SkeletonCircle size="64px" />
          <VStack gap={1} align="center">
            <SkeletonLine w="170px" h="5" />
            <Skeleton h="6" w="64px" borderRadius="full" />
          </VStack>
          <Skeleton h="1px" w="100%" />
          <VStack width="full" align="start" gap={3} pt="2">
            <SkeletonLine h="5" w="92%" />
            <SkeletonLine h="5" w="78%" />
            <SkeletonLine h="5" w="85%" />
          </VStack>
        </VStack>
      </Box>
      {}
      <Box w="full">
        <AddressBookLoadingSkeleton />
      </Box>
    </Flex>
  );
}

export function AddressBookLoadingSkeleton() {
  return (
    <Card.Root role="status" aria-label="Cargando">
      <Card.Body>
        <Stack gap={2} py={4}>
          <Text fontWeight="semibold">Libro de direcciones</Text>
          <AddressBookSkeleton />
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export function AdminUsersSkeleton() {
  return (
    <Stack width="full" gap="4" role="status" aria-label="Cargando">
      <SkeletonLine w="45%" h="3" />
      <SkeletonTable rows={8} cols={["45%", "25%", "30%"]} />
    </Stack>
  );
}

export function ListCardSkeleton({
  titleWidth = "30%",
  buttonWidth = "120px",
  cols,
  rows = 6,
  withSearch = false,
}: {
  titleWidth?: string;
  buttonWidth?: string;
  cols: string[];
  rows?: number;
  withSearch?: boolean;
}) {
  return (
    <Stack gap="4" width="full" role="status" aria-label="Cargando">
      <Flex justify="space-between" align="center" wrap="wrap" gap="3">
        <SkeletonLine w={titleWidth} h="4" />
        <Skeleton h="2.5rem" w={buttonWidth} borderRadius="lg" />
      </Flex>
      {withSearch ? (
        <Flex gap="2" wrap="wrap">
          <Skeleton h="2.5rem" flex="1" minW="160px" borderRadius="md" />
          <Skeleton h="2.5rem" w="100px" borderRadius="lg" />
        </Flex>
      ) : null}
      <SkeletonTable rows={rows} cols={cols} />
    </Stack>
  );
}

export function AbmListSkeleton({
  cols,
  rows = 6,
  withCreate = false,
  selects = 0,
}: {
  cols: string[];
  rows?: number;
  withCreate?: boolean;
  selects?: number;
}) {
  return (
    <Flex
      direction="column"
      gap="4"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      {withCreate ? (
        <Box
          borderWidth="1px"
          borderColor="border.muted"
          borderRadius="lg"
          p="4"
        >
          <Stack gap="3">
            <SkeletonLine w="25%" h="3" />
            <SimpleGrid columns={{ base: 1, md: 3 }} gap="3">
              <FieldSkeleton labelWidth="60%" inputHeight="2rem" />
              <FieldSkeleton labelWidth="60%" inputHeight="2rem" />
              <FieldSkeleton labelWidth="60%" inputHeight="2rem" />
            </SimpleGrid>
          </Stack>
        </Box>
      ) : null}
      <Flex gap="3" wrap="wrap" align="center">
        <Skeleton h="2.5rem" flex="1" minW="180px" borderRadius="md" />
        {Array.from({ length: selects }).map((_, i) => (
          <Skeleton key={i} h="2.5rem" minW="10rem" borderRadius="md" />
        ))}
      </Flex>
      <SkeletonTable rows={rows} cols={cols} />
    </Flex>
  );
}

export function CalcDashboardSkeleton() {
  const section = (key: string) => (
    <Box
      key={key}
      p="4"
      bg="white"
      borderRadius="md"
      shadow="sm"
      border="1px solid"
      borderColor="gray.200"
    >
      <Stack gap="3">
        <SkeletonLine w="50%" h="4" />
        <SkeletonTable rows={4} cols={["40%", "20%", "20%", "20%"]} />
      </Stack>
    </Box>
  );
  return (
    <Flex
      direction="column"
      gap="6"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Box
            key={i}
            p={4}
            bg="white"
            borderRadius="md"
            shadow="sm"
            border="1px solid"
            borderColor="gray.200"
          >
            <Stack gap="2">
              <SkeletonLine w="60%" h="3" />
              <SkeletonLine w="45%" h="8" />
              <SkeletonLine w="70%" h="2.5" />
            </Stack>
          </Box>
        ))}
      </SimpleGrid>
      <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
        {section("a")}
        {section("b")}
      </SimpleGrid>
    </Flex>
  );
}

export function CalcProductListSkeleton() {
  return (
    <Flex
      direction="column"
      gap="4"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex
        direction={{ base: "column", lg: "row" }}
        gap="4"
        p="4"
        bg="gray.50"
        borderRadius="md"
        align="end"
      >
        <Flex direction="column" flex="1" gap="2">
          <SkeletonLine w="20%" h="3" />
          <Skeleton h="2.5rem" borderRadius="md" />
        </Flex>
        <Skeleton h="2.5rem" minW="10rem" borderRadius="md" />
        <Skeleton h="2.5rem" w="140px" borderRadius="lg" />
      </Flex>
      <SkeletonTable rows={8} cols={["35%", "20%", "25%", "20%"]} />
      <Flex justify="center" mt="2">
        <Skeleton h="2.5rem" w="240px" borderRadius="md" />
      </Flex>
    </Flex>
  );
}

export function CalcFormSkeleton() {
  return (
    <Flex
      direction="column"
      gap="6"
      maxW="1200px"
      mx="auto"
      p="6"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex justify="space-between" align="center" gap="3" wrap="wrap">
        <SkeletonLine w="35%" h="8" />
        <Skeleton h="2.5rem" w="110px" borderRadius="lg" />
      </Flex>
      <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
        <Box
          borderWidth="1px"
          borderColor="border.muted"
          borderRadius="md"
          p="4"
        >
          <Stack gap="3">
            <SkeletonLine w="40%" h="4" />
            <FieldSkeleton />
            <FieldSkeleton />
            <FieldSkeleton labelWidth="40%" inputHeight="2rem" />
          </Stack>
        </Box>
        <Box
          borderWidth="1px"
          borderColor="border.muted"
          borderRadius="md"
          p="4"
        >
          <Stack gap="3">
            <SkeletonLine w="40%" h="4" />
            <FieldSkeleton />
            <FieldSkeleton inputHeight="2rem" />
            <Skeleton h="2.5rem" w="120px" borderRadius="lg" />
          </Stack>
        </Box>
      </SimpleGrid>
    </Flex>
  );
}

export function CatalogSkeleton() {
  return (
    <Flex
      direction="column"
      gap="4"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex gap="3" wrap="wrap" align="center">
        <Skeleton h="6" w="110px" borderRadius="full" />
        <Flex gap="3" wrap="wrap">
          <Skeleton h="2.5rem" w="120px" borderRadius="lg" />
          <Skeleton h="2.5rem" w="120px" borderRadius="lg" />
        </Flex>
      </Flex>
      <SkeletonTable rows={8} cols={["40%", "18%", "18%", "24%"]} />
    </Flex>
  );
}

export function IngredientsSkeleton() {
  return (
    <Flex
      direction="column"
      gap="4"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex gap="3" wrap="wrap" align="center">
        <Skeleton h="2.5rem" flex="1" minW="200px" borderRadius="md" />
        <Skeleton h="2.5rem" w="150px" borderRadius="lg" />
      </Flex>
      <SkeletonTable rows={8} cols={["35%", "20%", "20%", "25%"]} />
    </Flex>
  );
}

export function DetailPageSkeleton({
  tabs = 2,
  dataRows = 4,
}: {
  tabs?: number;
  dataRows?: number;
}) {
  return (
    <Flex
      direction="column"
      gap="5"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <SkeletonLine w="100px" h="3" />
      <Flex justify="space-between" align="center" wrap="wrap" gap="3">
        <Flex gap="3" align="center" wrap="wrap">
          <SkeletonLine w="40%" h="8" />
          <Skeleton h="5" w="80px" borderRadius="full" />
        </Flex>
        <Flex gap="2" wrap="wrap">
          <Skeleton h="2.5rem" w="100px" borderRadius="lg" />
          <Skeleton h="2.5rem" w="100px" borderRadius="lg" />
          <Skeleton h="2.5rem" w="110px" borderRadius="lg" />
        </Flex>
      </Flex>
      <Flex
        gap="6"
        borderBottomWidth="1px"
        borderColor="border.muted"
        pb="2"
        wrap="wrap"
      >
        {Array.from({ length: tabs }).map((_, i) => (
          <Skeleton key={i} h="4" w={i === 0 ? "130px" : "110px"} />
        ))}
      </Flex>
      <SkeletonTable rows={dataRows} cols={["30%", "23%", "23%", "24%"]} />
    </Flex>
  );
}

export function FormSkeleton({
  fields = 5,
  titleWidth = "45%",
  withSubtitle = true,
}: {
  fields?: number;
  titleWidth?: string;
  withSubtitle?: boolean;
}) {
  return (
    <Stack width="full" gap="4" role="status" aria-label="Cargando">
      <Stack gap="1" w="full">
        <SkeletonLine w={titleWidth} h="8" />
        {withSubtitle ? <SkeletonLine w="65%" h="3" /> : null}
      </Stack>
      {Array.from({ length: fields }).map((_, i) => (
        <FieldSkeleton key={i} labelWidth={i % 2 ? "35%" : "45%"} />
      ))}
      <Flex justify="flex-end">
        <Skeleton h="2.5rem" w="130px" borderRadius="lg" />
      </Flex>
    </Stack>
  );
}

export function SettingsSkeleton() {
  return (
    <Flex
      direction="column"
      gap="6"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Stack gap="1" w="full">
        <SkeletonLine w="30%" h="8" />
        <SkeletonLine w="55%" h="3" />
      </Stack>
      {[2, 2, 3].map((n, i) => (
        <Box
          key={i}
          borderWidth="1px"
          borderColor="border.muted"
          borderRadius="md"
          p="5"
        >
          <Stack gap="3">
            <SkeletonLine w="45%" h="4" />
            <SimpleGrid columns={{ base: 1, sm: 2 }} gap="3">
              {Array.from({ length: n }).map((_, j) => (
                <FieldSkeleton key={j} labelWidth="70%" inputHeight="2rem" />
              ))}
            </SimpleGrid>
          </Stack>
        </Box>
      ))}
      <Flex justify="flex-end">
        <Skeleton h="2.5rem" w="130px" borderRadius="lg" />
      </Flex>
    </Flex>
  );
}

export function ProductFormSkeleton() {
  return (
    <Flex
      direction="column"
      gap="5"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex align="flex-start" justify="space-between" gap="3" flexWrap="wrap">
        <Stack gap="1" w="full">
          <SkeletonLine w="35%" h="8" />
          <SkeletonLine w="50%" h="3" />
        </Stack>
        <Skeleton h="2.5rem" w="110px" borderRadius="lg" />
      </Flex>
      <Flex
        gap="6"
        borderBottomWidth="1px"
        borderColor="border.muted"
        pb="2"
        wrap="wrap"
      >
        <Skeleton h="4" w="120px" />
        <Skeleton h="4" w="110px" />
        <Skeleton h="4" w="120px" />
      </Flex>
      <Stack gap="4" w="full">
        <FieldSkeleton />
        <FieldSkeleton />
        <FieldSkeleton labelWidth="40%" />
        <FieldSkeleton inputHeight="6rem" />
      </Stack>
    </Flex>
  );
}

export function OrderListSkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <Stack gap="3" width="full" role="status" aria-label="Cargando">
      {Array.from({ length: cards }).map((_, i) => (
        <Card.Root key={i}>
          <Card.Header>
            <Flex justify="space-between" align="center" gap="2">
              <Flex gap="2" align="baseline">
                <SkeletonLine w="38%" h="5" />
                <SkeletonLine w="16%" h="3" />
              </Flex>
              <Skeleton h="5" w="72px" borderRadius="full" />
            </Flex>
          </Card.Header>
          <Card.Body>
            <Flex justify="space-between" align="center">
              <SkeletonLine w="22%" h="3" />
              <SkeletonLine w="16%" h="4" />
            </Flex>
          </Card.Body>
        </Card.Root>
      ))}
    </Stack>
  );
}

export function CheckoutSkeleton() {
  return (
    <Flex
      direction="column"
      gap="6"
      width="full"
      role="status"
      aria-label="Cargando"
    >
      <Flex gap={{ base: "3", md: "8" }} wrap="wrap">
        {Array.from({ length: 4 }).map((_, i) => (
          <Flex key={i} gap="2" align="center" flex="1" minW="120px">
            <SkeletonCircle size="6" />
            <Stack gap="1" flex="1">
              <SkeletonLine h="3" />
              <SkeletonLine h="2.5" w="55%" />
            </Stack>
          </Flex>
        ))}
      </Flex>
      <Skeleton h="1px" w="100%" />
      <Stack width="full" maxW="26rem" gap="4">
        <FieldSkeleton labelWidth="80%" />
        <FieldSkeleton labelWidth="60%" />
        <Skeleton h="9" borderRadius="lg" w="100%" />
      </Stack>
    </Flex>
  );
}

export function BudgetRowsSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <Stack gap="2" width="full" role="status" aria-label="Cargando">
      {Array.from({ length: rows }).map((_, i) => (
        <Flex key={i} gap="3" align="center" wrap="wrap">
          <Skeleton h="2.5rem" flex="1" minW="180px" borderRadius="md" />
          <Skeleton h="2.5rem" w="70px" borderRadius="md" />
          <Skeleton h="2.5rem" w="90px" borderRadius="md" />
        </Flex>
      ))}
    </Stack>
  );
}

export function AddressBookSkeleton() {
  return (
    <Stack gap="3" width="full" role="status" aria-label="Cargando">
      <Skeleton h="16" w="100%" borderRadius="md" />
      <Skeleton h="16" w="100%" borderRadius="md" />
    </Stack>
  );
}

export function RecipeLinesSkeleton({ rows = 2 }: { rows?: number }) {
  return (
    <Stack gap="3" width="full" role="status" aria-label="Cargando">
      {Array.from({ length: rows }).map((_, i) => (
        <Flex key={i} gap="2" align="flex-end" flexWrap="wrap">
          <Box flex="2 1 12rem">
            <SkeletonLine w="100%" h="1.25rem" />
            <Skeleton h="2.5rem" w="100%" borderRadius="md" />
          </Box>
          <Box flex="0 1 7rem">
            <SkeletonLine w="100%" h="1.25rem" />
            <Skeleton h="2.5rem" w="100%" borderRadius="md" />
          </Box>
          <Box flex="0 1 6.5rem">
            <SkeletonLine w="100%" h="1.25rem" />
            <Skeleton h="2.5rem" w="100%" borderRadius="md" />
          </Box>
          <Skeleton h="2.5rem" w="2.5rem" borderRadius="md" />
        </Flex>
      ))}
    </Stack>
  );
}
