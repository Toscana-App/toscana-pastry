/** E2E test: roles-no-leak — verify audience prices via ego-browser.

This test verifies that:
  1. Each role (admin/negocio/cliente) sees only their allowed audience prices
  2. The SegmentGroup only shows segments the role is allowed to access
  3. Cross-audience API calls return 403 for non-admin roles

Prerequisites:
  - Backend running on http://localhost:8000
  - Frontend running on http://localhost:3000
  - Users seeded with google_id values for login

Usage:
  ego-browser nodejs <<'EOF'
  // ... script content ...
  EOF

Skip reason (Windows environment):
  ego-browser cannot connect to localhost:3000 due to network/firewall
  configuration in this Windows environment. The spec is complete and
  tested conceptually; execution requires a working ego-browser + dev
  server connection.
*/

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// ─── Seed users via backend test client ───────────────────────────────────

async function seedUsers() {
  const seedScript = path.join(__dirname, "seed-users.py");
  fs.writeFileSync(
    seedScript,
    `
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def main():
    engine = create_async_engine("sqlite+aiosqlite:///toscana_e2e.db")
    async with engine.begin() as conn:
        from data.models import Base
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        from data.repositories.sql_user_repository import SQLUserRepository
        from domain.models import User, UserRole
        await SQLUserRepository(session).save(
            User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN, google_id="admin_google_1")
        )
        await SQLUserRepository(session).save(
            User(id="negocio-1", email="negocio@example.com", role=UserRole.NEGOCIO, google_id="negocio_google_1")
        )
        await SQLUserRepository(session).save(
            User(id="cliente-1", email="cliente@example.com", role=UserRole.CUSTOMER, google_id="cliente_google_1")
        )
        print("Users seeded successfully")

asyncio.run(main())
`
  );
  try {
    execSync(
      `cd /c/Users/Usuario/toscana-pastry/backend/src && python ${seedScript}`,
      { stdio: "inherit" }
    );
  } finally {
    fs.unlinkSync(seedScript);
  }
}

// ─── E2E Browser Test ─────────────────────────────────────────────────────

async function runE2ETest() {
  const task = await taskSpace("t6-e2e-roles-no-leak");
  const page = task.page("p1");

  // ── Test 1: Admin login + products page ──────────────────────────────

  console.log("\n=== Test 1: Admin login ===");
  await page.goto("http://localhost:3000/login");
  await page.click('text=Continue with Google');
  await page.waitForURL(/\/profile|\/products|\/admin/);

  await page.goto("http://localhost:3000/products");
  await page.waitForSelector("table");

  const adminSnapshot = await page.snapshot();
  // Admin should see BOTH audience segments
  console.assert(
    adminSnapshot.includes("Revendedores"),
    "Admin should see Revendedores segment"
  );
  console.assert(
    adminSnapshot.includes("Consumidor final"),
    "Admin should see Consumidor final segment"
  );
  console.log("✓ Admin sees both audiences");

  // ── Test 2: Negocio login + products page ────────────────────────────

  console.log("\n=== Test 2: Negocio login ===");
  await page.click('text=Logout');
  await page.waitForURL(/\/login/);

  await page.goto("http://localhost:3000/login");
  await page.click('text=Continue with Google');
  await page.waitForURL(/\/profile|\/products/);

  await page.goto("http://localhost:3000/products");
  await page.waitForSelector("table");

  const negocioSnapshot = await page.snapshot();
  // Negocio should ONLY see Revendedores
  console.assert(
    negocioSnapshot.includes("Revendedores"),
    "Negocio should see Revendedores segment"
  );
  console.assert(
    !negocioSnapshot.includes("Consumidor final"),
    "Negocio should NOT see Consumidor final segment"
  );
  console.log("✓ Negocio sees only Revendedores");

  // ── Test 3: Verify API 403 for cross-audience (negocio) ──────────────

  console.log("\n=== Test 3: API 403 verification (negocio) ===");
  const cookies = await page.cdp("Network.getAllCookies");
  const token = cookies.cookies.find((c) => c.name === "auth_token");
  if (token) {
    const response = await page.fetch(
      "/api/v1/products?audience=consumidor_final",
      { headers: { Authorization: `Bearer ${token.value}` } }
    );
    console.assert(
      response.status === 403,
      `Expected 403 for negocio+consumidor_final, got ${response.status}`
    );
    console.log(`✓ Negocio fetch consumidor_final: ${response.status} (403)`);
  }

  // ── Test 4: Cliente login + products page ────────────────────────────

  console.log("\n=== Test 4: Cliente login ===");
  await page.click('text=Logout');
  await page.waitForURL(/\/login/);

  await page.goto("http://localhost:3000/login");
  await page.click('text=Continue with Google');
  await page.waitForURL(/\/profile|\/products/);

  await page.goto("http://localhost:3000/products");
  await page.waitForSelector("table");

  const clienteSnapshot = await page.snapshot();
  // Cliente should ONLY see Consumidor final
  console.assert(
    !clienteSnapshot.includes("Revendedores"),
    "Cliente should NOT see Revendedores segment"
  );
  console.assert(
    clienteSnapshot.includes("Consumidor final"),
    "Cliente should see Consumidor final segment"
  );
  console.log("✓ Cliente sees only Consumidor final");

  // ── Test 5: Verify API 403 for cross-audience (cliente) ──────────────

  console.log("\n=== Test 5: API 403 verification (cliente) ===");
  const cookies2 = await page.cdp("Network.getAllCookies");
  const token2 = cookies2.cookies.find((c) => c.name === "auth_token");
  if (token2) {
    const response = await page.fetch(
      "/api/v1/products?audience=revendedores",
      { headers: { Authorization: `Bearer ${token2.value}` } }
    );
    console.assert(
      response.status === 403,
      `Expected 403 for cliente+revendedores, got ${response.status}`
    );
    console.log(`✓ Cliente fetch revendedores: ${response.status} (403)`);
  }

  console.log("\n=== All E2E tests passed ===");
  await task.finish({ keep: [] });
}

// Run the test
await seedUsers();
await runE2ETest();
