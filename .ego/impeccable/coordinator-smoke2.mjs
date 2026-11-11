const res = await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ google_id: "google_test_id" }),
});
const cookie = (res.headers.get("set-cookie") || "").split(";")[0];
console.log("cookie:", cookie ? "ok" : "NONE");

const task = await taskSpace("impeccable-coordinator-smoke");
const page = task.page("p1");
const name = cookie.split("=")[0];
const value = cookie.slice(name.length + 1);
await page.cdp("Network.setCookie", { name, value, domain: "localhost", path: "/", httpOnly: true });
console.log("cookie set");

const routes = ["/", "/login", "/admin", "/admin/calculator/settings", "/unauthorized", "/contact", "/products", "/carrito"];
for (const r of routes) {
  await page.goto("http://localhost:3000" + r, { waitUntil: "networkidle" });
  await new Promise(s => setTimeout(s, 900));
  const info = await page.evaluate(() => {
    const containers = [...document.querySelectorAll("div")].filter(el => (el.className?.toString() || "").includes("chakra-container")).slice(0, 2);
    return {
      h1: document.querySelector("h1")?.textContent?.slice(0, 40) || null,
      contW: containers.map(c => Math.round(c.getBoundingClientRect().width)),
      bodyW: Math.round(document.body.getBoundingClientRect().width),
    };
  });
  console.log(r, JSON.stringify(info));
}
