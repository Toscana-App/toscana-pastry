import { createTaskSpace, openBrowser } from "@egoist/browser";

const space = await createTaskSpace("impeccable-coordinator-smoke");
const { page } = await openBrowser(space);

const res = await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ google_id: "google_test_id" }),
});
const setCookie = res.headers.get("set-cookie") || "";
const cookie = setCookie.split(";")[0];
console.log("cookie:", cookie ? cookie.slice(0, 30) + "..." : "NONE");

// set cookie via CDP
try {
  const cdp = page.cdp ? await page.cdp() : (page.context ? await page.context.newCDPSession(page) : null);
  const name = cookie.split("=")[0];
  const value = cookie.slice(name.length + 1);
  await cdp.send("Network.setCookie", {
    name, value, domain: "localhost", path: "/", httpOnly: true, secure: false,
  });
  console.log("cdp cookie set");
} catch (e) {
  console.log("cdp failed:", e.message?.slice(0, 120));
}

const routes = ["/", "/login", "/admin", "/admin/calculator/settings", "/unauthorized", "/contact", "/products", "/carrito"];
for (const r of routes) {
  await page.goto("http://localhost:3000" + r, { waitUntil: "networkidle" }).catch(async () => { await page.goto("http://localhost:3000" + r); });
  await new Promise(s => setTimeout(s, 800));
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
