const task = await taskSpace(1);
const page = task.page("p1");

await page.goto("http://localhost:3000/admin/settings");
await page.waitForLoadState();
await page.waitForTimeout(800);

const probe = await page.evaluate(() =>
  Promise.allSettled([
    fetch("http://localhost:8000/api/v1/settings", { credentials: "include" })
      .then(async (r) => ({ url: "/settings", status: r.status, body: (await r.text()).slice(0, 200) })),
    fetch("http://localhost:8000/api/v1/settings", { credentials: "include", method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(async (r) => ({ url: "POST /settings", status: r.status, body: (await r.text()).slice(0, 200) })),
  ]).then((rs) => rs.map((r) => (r.status === "fulfilled" ? r.value : { error: String(r.reason) })))
);
console.log("PROBE:", JSON.stringify(probe, null, 2));
