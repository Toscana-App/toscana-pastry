import { describe, expect, it } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { GoogleIcon } from "./google-icon";

describe("GoogleIcon", () => {
  it("renders the four distinct Google G segments", () => {
    const { container } = renderWithProviders(<GoogleIcon />);
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    const paths = [...(svg as SVGSVGElement).querySelectorAll("path")];
    expect(paths).toHaveLength(4);
    const fills = paths.map((p) => p.getAttribute("fill"));
    expect(new Set(fills).size).toBe(4);
    expect(fills).toContain("#4285F4");
    expect(fills).toContain("#34A853");
    expect(fills).toContain("#FBBC05");
    expect(fills).toContain("#EA4335");
    const dValues = paths.map((p) => p.getAttribute("d"));
    expect(new Set(dValues).size).toBe(4);
  });
});
