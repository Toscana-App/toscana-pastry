const task = await taskSpace("toscana-qa-screens-2");
const page = task.page("p1");
console.log({ spaceId: task.spaceId });

// Re-login as admin (mock google -> u-admin-1, role admin)
await page.goto("http://localhost:3000/login");
await page.waitForLoadState();
await page.click("text=Continuar con Google", { label: "login with mock Google" });
await page.waitForURL("**/admin", { timeout: 20000 });

const probe = await page.evaluate(() =>
  Promise.allSettled([
    fetch("http://localhost:8000/api/v1/tenant/settings", { credentials: "include" })
      .then(async (r) => ["/tenant/settings GET", r.status, (await r.text()).slice(0, 150)]),
    fetch("http://localhost:8000/api/v1/tenant/order-window", { credentials: "include" })
      .then(async (r) => ["/tenant/order-window GET", r.status, (await r.text()).slice(0, 150)]),
  ]).then((rs) => rs.map((r) => (r.status === "fulfilled" ? r.value : ["error", 0, String(r.reason)])))
);
console.log("PROBE:", JSON.stringify(probe, null, 1));
