import { Box } from "@chakra-ui/react"
import Image from "next/image"

// Assets built from docs/images by scripts/build_brand_assets.mjs.
const LOGOS = {
  horizontal: { file: "logo_horizontal", ratio: 4766.81 / 1470.78, alt: "Toscana" },
  vertical: { file: "logo_vertical_tagline", ratio: 5017.02 / 4662.21, alt: "Toscana, horneando momentos" },
} as const

interface BrandLogoProps {
  variant: keyof typeof LOGOS
  /** Rendered height in px. */
  height: number
  priority?: boolean
}

/** Toscana logo in ink on light surfaces and cream on dark ones. */
export function BrandLogo({ variant, height, priority }: BrandLogoProps) {
  const { file, ratio, alt } = LOGOS[variant]
  const size = { width: Math.round(height * ratio), height }

  return (
    <>
      <Box asChild display="block" _dark={{ display: "none" }}>
        <Image src={`/brand/${file}_ink.webp`} alt={alt} priority={priority} {...size} />
      </Box>
      <Box asChild display="none" _dark={{ display: "block" }}>
        <Image src={`/brand/${file}_cream.webp`} alt={alt} priority={priority} {...size} />
      </Box>
    </>
  )
}
