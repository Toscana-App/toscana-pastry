import { describe, expect, it, vi, beforeEach } from "vitest"
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { renderWithProviders } from "@/test-utils"
import { ProductsCatalog } from "./ProductsCatalog"

const auth = vi.hoisted(() => ({ role: "admin" }))
const store = vi.hoisted(() => ({ list: vi.fn() }))
const pricing = vi.hoisted(() => ({ csv: vi.fn(), pdf: vi.fn() }))

vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: { role: auth.role } }) }))
vi.mock("@/services/storeService", () => ({
  fetchStoreList: store.list,
}))
vi.mock("@/services/pricingService", () => ({
  downloadPricelistCSV: pricing.csv,
  downloadPricelistPDF: pricing.pdf,
}))
vi.mock("@/services/cartService", () => ({ addCartItem: vi.fn() }))
vi.mock("goey-toast", () => ({ gooeyToast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
  useSearchParams: vi.fn(() => new URLSearchParams()),
}))
vi.mock("next/link", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/link")>()
  return {
    ...actual,
    default: ({ href, children, ...rest }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
      <a href={href} {...rest}>{children}</a>
    ),
  }
})

const ROW = {
  id: "p1",
  name: "Torta de chocolate",
  category: "Tortas",
  description: "",
  image_url: null,
  price: "17500",
  price_per_serving: "1458.33",
  complete: true,
}

describe("ProductsCatalog (contrato de tienda T3)", () => {
  beforeEach(() => {
    auth.role = "customer"
    store.list.mockReset()
    store.list.mockResolvedValue({
      audience: "consumidor_final",
      products: [ROW],
      total: 1,
      categories: ["Tortas"],
    })
    pricing.csv.mockClear()
    pricing.pdf.mockClear()
  })

  it("renderiza categoría y precio (sin unidad ni tags) para el rol portal", async () => {
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Torta de chocolate")
    expect(screen.getByText("Tortas")).toBeInTheDocument()
    expect(screen.getByText(/17.500/)).toBeInTheDocument()
    expect(screen.getByText(/1.458,33/)).toBeInTheDocument()
    expect(screen.queryByText("Unidad")).not.toBeInTheDocument()
    expect(screen.queryByText("kg")).not.toBeInTheDocument()
    expect(store.list).toHaveBeenCalledWith("consumidor_final", undefined)
  })

  it("el nombre del producto enlaza al detalle de la tienda (portal)", async () => {
    renderWithProviders(<ProductsCatalog />)

    const link = await screen.findByRole("link", { name: "Torta de chocolate" })
    expect(link).toHaveAttribute("href", "/tienda/p1")
  })

  it("muestra el precio de la audiencia elegida y pide esa lista (admin)", async () => {
    auth.role = "admin"
    const user = userEvent.setup()
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Torta de chocolate")
    expect(store.list).toHaveBeenCalledWith("revendedores", undefined)

    await user.click(screen.getByText("Consumidor final"))
    await screen.findAllByText("Torta de chocolate")
    expect(store.list).toHaveBeenCalledWith("consumidor_final", undefined)
  })

  it("exporta CSV/PDF de la audiencia seleccionada (admin)", async () => {
    auth.role = "admin"
    const user = userEvent.setup()
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Torta de chocolate")
    await user.click(screen.getByRole("button", { name: "Exportar CSV" }))
    expect(pricing.csv).toHaveBeenCalledWith("revendedores")
    await user.click(screen.getByRole("button", { name: "Exportar PDF" }))
    expect(pricing.pdf).toHaveBeenCalledWith("revendedores")
  })

  it("sin sesión no carga precios y muestra la invitación a iniciar sesión", async () => {
    auth.role = ""
    renderWithProviders(<ProductsCatalog />)

    const link = await screen.findByRole("link", { name: /iniciar sesión/i })
    expect(link).toHaveAttribute("href", "/login")
    expect(screen.queryByRole("status", { name: "Cargando" })).not.toBeInTheDocument()
    expect(store.list).not.toHaveBeenCalled()
  })

  it("si falla la carga muestra un error con reintento y reintenta", async () => {
    auth.role = "customer"
    store.list.mockRejectedValueOnce(new Error("Sin conexión"))
    const user = userEvent.setup()
    renderWithProviders(<ProductsCatalog />)

    expect(
      await screen.findByText("No se pudieron cargar los productos"),
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(store.list).toHaveBeenCalledTimes(2)

    await screen.findByText("Torta de chocolate")
  })

  it("el botón Agregar declara min-height 44px para el pulgar (portal)", async () => {
    auth.role = "customer"
    renderWithProviders(<ProductsCatalog />)

    const button = await screen.findByRole("button", { name: /agregar torta de chocolate/i })
    const cssName = (button.getAttribute("class") ?? "").split(/\s+/).pop() ?? ""
    let hasMinHeight44 = false
    for (const sheet of Array.from(document.styleSheets)) {
      let rules: CSSRuleList | null = null
      try {
        rules = sheet.cssRules
      } catch {
        continue
      }
      // Las reglas pueden estar anidadas en @layer, se busca en el texto
      // completo de cada regla.
      for (const rule of Array.from(rules ?? [])) {
        if (
          rule.cssText?.includes(cssName) &&
          /min-height:\s*44px/.test(rule.cssText ?? "")
        ) {
          hasMinHeight44 = true
        }
      }
    }
    expect(hasMinHeight44).toBe(true)
  })
})
