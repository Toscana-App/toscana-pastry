import { describe, expect, it, vi, beforeEach } from "vitest"
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { renderWithProviders } from "@/test-utils"
import { ProductsCatalog } from "./ProductsCatalog"

const auth = vi.hoisted(() => ({ role: "admin" }))
const pricing = vi.hoisted(() => ({ csv: vi.fn(), pdf: vi.fn() }))

vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: { role: auth.role } }) }))
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async () => ({
    products: [{ id: "p1", name: "Harina 000", unit: "kg", price_per_unit: "2.50", tags: [] }],
    total: 1,
  })),
}))
vi.mock("@/services/pricingService", () => ({
  downloadPricelistCSV: pricing.csv,
  downloadPricelistPDF: pricing.pdf,
}))
vi.mock("@/services/cartService", () => ({ addCartItem: vi.fn() }))
vi.mock("goey-toast", () => ({ gooeyToast: { success: vi.fn(), error: vi.fn() } }))

describe("ProductsCatalog", () => {
  beforeEach(() => {
    pricing.csv.mockClear()
    pricing.pdf.mockClear()
  })

  it("shows one export pair for the selected audience and exports that audience (admin)", async () => {
    auth.role = "admin"
    const user = userEvent.setup()
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Harina 000")
    expect(screen.getAllByRole("button", { name: "Exportar CSV" })).toHaveLength(1)
    expect(screen.getAllByRole("button", { name: "Exportar PDF" })).toHaveLength(1)

    await user.click(screen.getByText("Consumidor final"))
    await user.click(screen.getByRole("button", { name: "Exportar CSV" }))
    expect(pricing.csv).toHaveBeenCalledWith("consumidor_final")
  })

  it("does not repeat the selected audience as a badge when the switcher is shown (admin)", async () => {
    auth.role = "admin"
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Harina 000")
    expect(screen.getAllByText("Revendedores")).toHaveLength(1)
  })

  it("labels the only list a business can see (negocio)", async () => {
    auth.role = "negocio"
    renderWithProviders(<ProductsCatalog />)

    await screen.findByText("Harina 000")
    expect(screen.getByText("Revendedores")).toBeInTheDocument()
    expect(screen.queryByText("Consumidor final")).not.toBeInTheDocument()
  })
})
