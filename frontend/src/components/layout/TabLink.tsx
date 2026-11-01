"use client";

import { Flex, Text } from "@chakra-ui/react";
import NextLink from "next/link";

/**
 * One portal tab: a real route link styled as a tab.
 *
 * The active state is conveyed by color + underline, never by color
 * alone (RNF-P11-04 WCAG AA).
 */
export function TabLink({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <NextLink href={href} aria-current={active ? "page" : undefined}>
      <Flex
        px={4}
        py={3}
        minH="44px"
        align="center"
        whiteSpace="nowrap"
        borderBottomWidth="2px"
        borderColor={active ? "brand.500" : "transparent"}
      >
        <Text
          fontSize="sm"
          fontWeight={active ? "bold" : "normal"}
          color={active ? "brand.600" : "fg.muted"}
        >
          {label}
        </Text>
      </Flex>
    </NextLink>
  );
}
