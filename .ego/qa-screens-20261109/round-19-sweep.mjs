// Sweep e2e: pantallas, skeletons, toasts (goey vs chakra), validacion de formularios
const task = await takeOverTaskSpace(1).catch(async () => taskSpace(1));
const page = task.page("p1");

const login = async (googleId) => {
  await page.goto("http://localhost:3000/login");
  await page.waitForLoadState();
  await page.waitForTimeout(800);
  const status = await page.evaluate(async (id) => {
    const r = await fetch("http://localhost:8000/api/v1/auth/login", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ google_id: id }),
    });
    return r.status;
  }, googleId);
  return status;
};

const audit = async (label) => {
  const info = await page.evaluate(() => {
    const skeletons = document.querySelectorAll(".animate-pulse, [data-skeleton], .c-skeleton").length;
    const goey = document.querySelectorAll('[data-sonner-toast]').length;
    const chakra = document.querySelectorAll('[data-chakra-toast], [role="status"][data-part="root"]').length;
    const errors = [...document.querySelectorAll('[aria-invalid="true"], [role="alert"]')]
      .map(e => e.textContent?.trim()).filter(Boolean).slice(0, 3);
    const headings = [...document.querySelectorAll("h1,h2")].map(h => h.textContent?.trim()).slice(0, 2);
    return { skeletons, goey, chakra, errors, headings };
  });
  console.log(`SCREEN ${label} ::`, JSON.stringify(info));
  return info;
};

const visit = async (path, label) => {
  await page.goto(`http://localhost:3000${path}`);
  await page.waitForLoadState();
  await page.waitForTimeout(2200);
  await audit(label);
};

// ---- CLIENTE ----
console.log("login cliente:", await login("cliente_test_id"));
await visit("/", "cliente-home");
await visit("/products", "cliente-products");
await visit("/products/torta-de-chocolate", "cliente-product-detail (probable 404/id slug)");
await visit("/carrito", "cliente-carrito");
await visit("/checkout", "cliente-checkout");
await visit("/my-orders", "cliente-my-orders");
await visit("/profile", "cliente-profile");
await visit("/contact", "cliente-contact");

// ---- ADMIN ----
console.log("login admin:", await login("google_test_id"));
await visit("/admin", "admin-admin");
await visit("/pedidos", "admin-pedidos");
await visit("/pedidos/nuevo", "admin-pedido-nuevo");
await visit("/presupuestos", "admin-presupuestos");
await visit("/presupuestos/nuevo", "admin-presupuesto-nuevo");
await visit("/productos", "admin-productos");
await visit("/productos/new", "admin-producto-new");
await visit("/products", "admin-products-portal");
await visit("/admin/ingredients", "admin-ingredients");
await visit("/admin/ingredients/new", "admin-ingredient-new");
await visit("/admin/calculator/materials", "admin-calc-materials");
await visit("/admin/calculator/products", "admin-calc-products");
await visit("/admin/calculator/products/new", "admin-calc-product-new");
await visit("/admin/calculator/settings", "admin-calc-settings");
await visit("/admin/settings", "admin-settings");

// ---- LOGIN anonimo ----
await visit("/login", "anon-login");
console.log("SWEEP DONE");
