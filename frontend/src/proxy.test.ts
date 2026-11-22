import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { config, proxy } from "./proxy";

function makeRequest(path: string, cookie?: string): NextRequest {
  const headers = new Headers();
  if (cookie) headers.set("cookie", cookie);
  return new NextRequest(`http://localhost:3000${path}`, { headers });
}

describe("proxy", () => {
  it("redirects an authenticated /login to /", () => {
    const response = proxy(makeRequest("/login", "auth_token=tok123"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("lets an unauthenticated /login pass through", () => {
    const response = proxy(makeRequest("/login"));
    expect(response.status).toBe(200);
  });

  it("redirects unauthenticated protected routes to /login with from", () => {
    const response = proxy(makeRequest("/products"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?from=%2Fproducts",
    );
  });

  it("lets an authenticated protected route pass through", () => {
    const response = proxy(makeRequest("/products", "auth_token=tok123"));
    expect(response.status).toBe(200);
  });

  it("matcher includes /login", () => {
    expect(config.matcher).toContain("/login");
  });
});
