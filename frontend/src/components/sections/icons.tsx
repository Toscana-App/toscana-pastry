import { Icon } from "@chakra-ui/react";

/**
 * Inline SVG icon set (Feather-style, 24x24 viewBox).
 * Matches the project's existing pattern (search-icon.tsx, hero_section.tsx).
 * No external icon library dependency.
 *
 * Usage: <PackageIcon size={6} color="#ff7078" />
 */

type IconProps = {
  size?: number;
  color?: string;
};

const svgBase = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const px = (n: number) => `${n * 4}px`;

export const PackageIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <path d="M16.5 9.4L7.5 4.21" />
    <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </Icon>
);

export const CoffeeIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <path d="M18 8h1a4 4 0 010 8h-1" />
    <path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z" />
    <line x1="6" y1="1" x2="6" y2="4" />
    <line x1="10" y1="1" x2="10" y2="4" />
    <line x1="14" y1="1" x2="14" y2="4" />
  </Icon>
);

export const TrendingUpIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
    <polyline points="17 6 23 6 23 12" />
  </Icon>
);

export const GiftIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <polyline points="20 12 20 22 4 22 4 12" />
    <rect x="2" y="7" width="20" height="5" />
    <line x1="12" y1="22" x2="12" y2="7" />
    <path d="M12 7H7.5a2.5 2.5 0 010-5C11 2 12 7 12 7z" />
    <path d="M12 7h4.5a2.5 2.5 0 000-5C13 2 12 7 12 7z" />
  </Icon>
);

export const CookieIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <circle cx="12" cy="12" r="10" />
    <circle cx="8.5" cy="8" r="1.5" fill="currentColor" stroke="none" />
    <circle cx="15.5" cy="10" r="1.5" fill="currentColor" stroke="none" />
    <circle cx="10" cy="15" r="1.5" fill="currentColor" stroke="none" />
    <circle cx="15" cy="16.5" r="1.5" fill="currentColor" stroke="none" />
  </Icon>
);

export const UsersIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 00-3-3.87" />
    <path d="M16 3.13a4 4 0 010 7.75" />
  </Icon>
);

export const HeartIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
  </Icon>
);

export const StarIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
  </Icon>
);

export const CheckIcon = ({ size = 3, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <polyline points="20 6 9 17 4 12" />
  </Icon>
);

export const XIcon = ({ size = 3, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </Icon>
);

export const CrownIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7z" />
    <path d="M5 20h14" />
  </Icon>
);

export const ZapIcon = ({ size = 6, color }: IconProps) => (
  <Icon as="svg" viewBox="0 0 24 24" w={px(size)} h={px(size)} color={color} {...svgBase}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </Icon>
);
