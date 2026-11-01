import { describe, expect, it, beforeEach, vi } from "vitest"
import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { renderWithProviders } from "@/test-utils"
import { ColorModeButton, ColorModeProvider } from "./color-mode"

// next-themes reads the OS preference through matchMedia, which jsdom lacks.
function stubMatchMedia(prefersDark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: prefersDark && query.includes("dark"),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }))
}

function renderButton() {
  return renderWithProviders(
    <ColorModeProvider>
      <ColorModeButton />
    </ColorModeProvider>
  )
}

describe("ColorModeButton", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ""
    stubMatchMedia(false)
  })

  it("switches from light to dark and back", async () => {
    const user = userEvent.setup()
    renderButton()

    const toDark = await screen.findByRole("button", { name: "Activar modo oscuro" })
    await user.click(toDark)

    await waitFor(() => expect(document.documentElement).toHaveClass("dark"))
    const toLight = screen.getByRole("button", { name: "Activar modo claro" })

    await user.click(toLight)
    await waitFor(() => expect(document.documentElement).not.toHaveClass("dark"))
    expect(screen.getByRole("button", { name: "Activar modo oscuro" })).toBeInTheDocument()
  })

  it("follows the OS preference until the user picks a mode", async () => {
    stubMatchMedia(true)
    renderButton()

    await act(async () => {})
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"))
    expect(screen.getByRole("button", { name: "Activar modo claro" })).toBeInTheDocument()
  })

  it("remembers the chosen mode across reloads", async () => {
    const user = userEvent.setup()
    const { unmount } = renderButton()
    await user.click(await screen.findByRole("button", { name: "Activar modo oscuro" }))
    unmount()

    document.documentElement.className = ""
    renderButton()
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"))
  })
})
