const task = await taskSpace(1);
const page = task.page("p1");

const urls = [
  "/pedidos/22222222-2222-4222-8222-222222222222",
  "/pedidos/22222222-2222-4222-8222-222222222222/editar",
  "/productos/11111111-1111-4111-8111-111111111111",
  "/productos/11111111-1111-4111-8111-111111111111/edit",
  "/admin/ingredients/7e13aeae-50ce-45e1-8add-17c91a1f8ddb",
  "/admin/ingredients/7e13aeae-50ce-45e1-8add-17c91a1f8ddb/edit",
  "/admin/calculator/products/83db6568-88f8-438b-9719-f34c05226f8c",
];

const results = [];
for (const path of urls) {
  const t0 = Date.now();
  try {
    await page.goto("http://localhost:3000" + path);
    await page.waitForLoadState();
    await page.waitForTimeout(1000);
    const info = await page.evaluate(() => {
      const text = document.body.innerText;
      const errs = [];
      if (text.includes("Failed to fetch")) errs.push("Failed to fetch");
      const m = text.match(/No se pudo[^\n]*/);
      if (m) errs.push(m[0].slice(0, 60));
      const h = document.querySelector("h1, h2");
      return { heading: h ? h.textContent.trim().slice(0, 60) : null, errors: errs, url: location.pathname };
    });
    results.push([path, Date.now() - t0 + "ms", info.heading, info.errors.length ? "ERRORS: " + info.errors.join(" | ") : "OK"]);
  } catch (e) {
    results.push([path, Date.now() - t0 + "ms", "NAV FAIL: " + String(e).slice(0, 80)]);
  }
}
console.log("DETAIL SWEEP:");
for (const r of results) console.log(r.join(" :: "));
