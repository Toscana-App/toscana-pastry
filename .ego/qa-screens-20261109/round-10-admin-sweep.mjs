const task = await taskSpace(1);
const page = task.page("p1");

const urls = [
  "/admin",
  "/pedidos",
  "/pedidos/nuevo",
  "/presupuestos",
  "/presupuestos/nuevo",
  "/products",
  "/productos",
  "/productos/new",
  "/admin/ingredients",
  "/admin/ingredients/new",
  "/admin/calculator/materials",
  "/admin/calculator/products",
  "/admin/calculator/products/new",
  "/admin/calculator/settings",
  "/admin/settings",
  "/contact",
];

const results = [];
for (const path of urls) {
  const t0 = Date.now();
  try {
    await page.goto("http://localhost:3000" + path);
    await page.waitForLoadState();
    await page.waitForTimeout(900);
    const info = await page.evaluate(() => {
      const text = document.body.innerText;
      const errs = [];
      if (text.includes("Failed to fetch")) errs.push("Failed to fetch");
      const m = text.match(/No se pudo[^\n]*/);
      if (m) errs.push(m[0].slice(0, 60));
      const h1 = document.querySelector("h1, h2");
      return {
        title: document.title,
        heading: h1 ? h1.textContent.trim().slice(0, 60) : null,
        errors: errs,
        chars: text.length,
      };
    });
    results.push([path, Date.now() - t0 + "ms", info.heading, info.errors.length ? "ERRORS: " + info.errors.join(" | ") : "OK"]);
  } catch (e) {
    results.push([path, Date.now() - t0 + "ms", "NAV FAIL: " + String(e).slice(0, 80)]);
  }
}
console.log("SWEEP RESULTS:");
for (const r of results) console.log(r.join(" :: "));
