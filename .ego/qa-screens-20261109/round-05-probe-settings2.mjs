const task = await taskSpace(1);
const page = task.page("p1");

await page.goto("http://localhost:3000/admin/settings");
await page.waitForLoadState();
await page.waitForTimeout(600);

const probe = await page.evaluate(() =>
  Promise.allSettled([
    fetch("http://localhost:8000/api/v1/tenant/settings", { credentials: "include" })
      .then(async (r) => ["/tenant/settings GET", r.status, (await r.text()).slice(0, 120)]),
    fetch("http://localhost:8000/api/v1/tenant/order-window", { credentials: "include" })
      .then(async (r) => ["/tenant/order-window GET", r.status, (await r.text()).slice(0, 120)]),
  ]).then((rs) => rs.map((r) => (r.status === "fulfilled" ? r.value : ["error", 0, String(r.reason)])))
);
console.log("PROBE:", JSON.stringify(probe, null, 1));
