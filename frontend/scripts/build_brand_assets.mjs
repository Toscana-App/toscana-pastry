// Rasterizes the brand SVGs in docs/images into optimized WebP logos (plus the
// PNG app icon Next.js needs). Run: node scripts/build_brand_assets.mjs
import { mkdir, readFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import sharp from "sharp"

const SRC = new URL("../../docs/images/", import.meta.url)
const OUT = new URL("../public/brand/", import.meta.url)
const SOURCE_INK = "#373435"
// Ink for light surfaces; cream (DESIGN.md fg dark) for dark surfaces.
const TINTS = { ink: SOURCE_INK, cream: "#f7f1ee" }

const LOGOS = [
  // Navbar shows it 36px tall: 3x for dense screens.
  { file: "Toscana Iso Logo Hori 01.svg", name: "logo_horizontal", height: 108 },
  // Login shows it up to 220px wide.
  { file: "Toscana Iso Logo HM Vert 01.svg", name: "logo_vertical_tagline", width: 660 },
]

async function svg(file, color) {
  const text = await readFile(new URL(file, SRC), "utf8")
  return Buffer.from(text.replaceAll(SOURCE_INK, color))
}

await mkdir(OUT, { recursive: true })
for (const { file, name, width, height } of LOGOS) {
  for (const [tint, color] of Object.entries(TINTS)) {
    const out = new URL(`${name}_${tint}.webp`, OUT)
    await sharp(await svg(file, color), { density: 300 })
      .resize({ width, height })
      .webp({ quality: 90, alphaQuality: 100, effort: 6 })
      .toFile(fileURLToPath(out))
  }
}

// Favicon / app icon: the rosette on the brand peach.
await sharp(await svg("Toscana Iso 01.svg", SOURCE_INK), { density: 300 })
  .resize(400, 400)
  .extend({ top: 56, bottom: 56, left: 56, right: 56, background: "#f5ccad" })
  .flatten({ background: "#f5ccad" })
  .png({ compressionLevel: 9 })
  .toFile(fileURLToPath(new URL("../src/app/icon.png", import.meta.url)))
