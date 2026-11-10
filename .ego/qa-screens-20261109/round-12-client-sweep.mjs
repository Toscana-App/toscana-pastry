const task = await taskSpace(1);
const page = task.page("p1");

// switch session to customer via backend login (sets :8000 cookies)
const who = await page.evaluate(async () => {
  const r = await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_id: "cliente_test_id" }),
  });
  const b = await r.json().catch(() => null);
  return { status: r.status, role: b && b.role };
});
console.log("login as customer:", JSON.stringify(who));

const urls = [
  "/",
  "/tienda",
  "/tienda/83db6568-88f8-438b-9719-f34c05226f8c",
  "/carrito",
  "/checkout",
  "/my-orders",
  "/profile",
  "/admin", // should NOT be accessible as customer
];

const results = [];
for (const path of urls) {
  const t0 = Date.now();
  try {
    await page.goto("http://localhost:3000" + path);
    await page.waitForLoadState();
    await page.waitForTimeout(1200);
    const info = await page.evaluate(() => {
      const text = document.body.innerText;
      const errs = [];
      if (text.includes("Failed to fetch")) errs.push("Failed to fetch");
      const m = text.match(/No se pudo[^\n]*/);
      if (m) errs.push(m[0].slice(0, 60));
      const h = document.querySelector("h1, h2");
      return { heading: h ? h.textContent.trim().slice(0, 60) : null, errors: errs, finalPath: location.pathname };
    });
    results.push([path, Date.now() - t0 + "ms", "-> " + info.finalPath, info.heading, info.errors.length ? "ERRORS: " + info.errors.join(" | ") : "OK"]);
  } catch (e) {
    results.push([path, Date.now() - t0 + "ms", "NAV FAIL: " + String(e).slice(0, 80)]);
  }
}
console.log("CLIENT SWEEP:");
for (const r of results) console.log(r.join(" :: "));
