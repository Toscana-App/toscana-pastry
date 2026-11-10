const task = await taskSpace(1);
const page = task.page("p1");
console.log("page url:", await page.url());

const probe = await page.evaluate(async () => {
  const out = [];
  for (const ep of ["/orders", "/ingredients", "/products", "/calc/products", "/budgets", "/auth/me"]) {
    const t0 = performance.now();
    try {
      const r = await fetch("http://localhost:8000/api/v1" + ep, { credentials: "include" });
      const b = await r.text();
      out.push([ep, r.status, Math.round(performance.now() - t0) + "ms", b.slice(0, 80).replace(/\s+/g, " ")]);
    } catch (e) {
      out.push([ep, "FAIL " + (performance.now() - t0).toFixed(0) + "ms", String(e).slice(0, 80)]);
    }
  }
  return out;
});
console.log("SEQ PROBE:");
for (const row of probe) console.log(JSON.stringify(row));
