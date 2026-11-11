// E2E sweep de todas las pantallas tras el refactor del search bar.
const task = await taskSpace(1);
const page = task.page("p1");

const login = async (googleId) => {
  await page.evaluate(async (id) => {
    await fetch("http://localhost:8000/api/v1/auth/login", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ google_id: id }),
    });
  }, googleId);
};

const check = async (label, path, { expectSearch = "absent", expectText = null, loginAs = null } = {}) => {
  if (loginAs) await login(loginAs);
  await page.goto("http://localhost:3000" + path);
  await page.waitForLoadState();
  await page.waitForTimeout(1400);
  const r = await page.evaluate(() => ({
    title: document.title,
    hasError: /Failed to fetch|Error|500/.test(document.body.innerText.slice(0, 2000)),
    search: !!document.querySelector('form[role="search"]'),
    body: document.body.innerText.slice(0, 400).replace(/\n+/g, " | "),
  }));
  const searchOk = expectSearch === "present" ? r.search : !r.search;
  const textOk = expectText ? expectText.some(t => r.body.toLowerCase().includes(t.toLowerCase())) : true;
  const status = (!r.hasError && searchOk && textOk) ? "OK" : "FAIL";
  console.log(`[${status}] ${label} ${path} search=${r.search} err=${r.hasError}`);
  if (status === "FAIL") console.log(`   body: ${r.body.slice(0, 300)}`);
  return status === "OK";
};

const results = [];

// --- Home (search debe estar SOLO aca, para portal) ---
await login("cliente_test_id");
results.push(await check("home cliente", "/", { expectSearch: "present", expectText: ["pasteler", "catalogo"] }));
results.push(await check("home con filtro ?q", "/?q=torta", { expectSearch: "present", expectText: ["torta"] }));

// --- Secciones cliente: search ausente ---
results.push(await check("tienda", "/tienda", { expectSearch: "absent", expectText: ["catalog", "producto"] }));
results.push(await check("carrito", "/carrito", { expectSearch: "absent", expectText: ["carrito"] }));
results.push(await check("checkout", "/checkout", { expectSearch: "absent", expectText: ["pago", "contacto", "entrega"] }));
results.push(await check("my-orders", "/my-orders", { expectSearch: "absent", expectText: ["pedido"] }));
results.push(await check("profile", "/profile", { expectSearch: "absent", expectText: ["cuenta", "usuario"] }));

// --- Login: navbar oculta, sin search ---
results.push(await check("login", "/login", { expectSearch: "absent", expectText: ["login", "ingresar", "google"] }));

// --- Admin: sin search en ninguna seccion ---
await login("admin_test_id");
results.push(await check("admin dashboard", "/admin", { expectSearch: "absent", expectText: ["usuario", "cupon"] }));
results.push(await check("pedidos", "/pedidos", { expectSearch: "absent", expectText: ["pedido"] }));
results.push(await check("presupuestos", "/presupuestos", { expectSearch: "absent", expectText: ["presupuesto"] }));
results.push(await check("productos", "/productos", { expectSearch: "absent", expectText: ["producto"] }));
results.push(await check("products (listas)", "/products", { expectSearch: "absent", expectText: ["precio", "lista", "producto"] }));
results.push(await check("ingredients", "/admin/ingredients", { expectSearch: "absent", expectText: ["insumo", "ingrediente"] }));
results.push(await check("calculator", "/admin/calculator", { expectSearch: "absent", expectText: ["material", "calculador"] }));
results.push(await check("settings", "/admin/settings", { expectSearch: "absent", expectText: ["configuracion", "ajuste"] }));
results.push(await check("contact", "/contact", { expectSearch: "absent", expectText: ["contacto", "whatsapp", "email"] }));

// --- home como admin: sin search (no es rol portal) ---
results.push(await check("home admin", "/", { expectSearch: "absent", expectText: ["pasteler"] }));

const passed = results.filter(Boolean).length;
console.log(`\nSUMMARY: ${passed}/${results.length} screens OK`);
