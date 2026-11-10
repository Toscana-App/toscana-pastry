import NextLink from "next/link";
import { Button, Flex, Heading, Text } from "@chakra-ui/react";

interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
}

export function EmptyState({
  title,
  description,
  actionLabel,
  actionHref,
}: EmptyStateProps) {
  return (
    <Flex direction="column" align="center" gap={3} py={16}>
      <Heading size="md" textWrap="balance">{title}</Heading>
      {description ? (
        <Text color="fg.muted" textAlign="center">
          {description}
        </Text>
      ) : null}
      {actionLabel && actionHref ? (
        <Button colorPalette="brand" asChild>
          <NextLink href={actionHref}>{actionLabel}</NextLink>
        </Button>
      ) : null}
    </Flex>
  );
}
