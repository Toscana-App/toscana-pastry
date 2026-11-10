// Round 21: sweep de pantallas admin con navbar única + Perfil
const task = await taskSpace("qa-round-21");
const page = task.page("p1");

async function ensureLogin(googleId) {
  await page.goto("http://localhost:3000/login");
  await page.waitForLoadState();
  await page.waitForTimeout(600);
  await page.evaluate(async (id) => {
    await fetch("http://localhost:8000/api/v1/auth/login", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ google_id: id }),
    });
  }, googleId);
}

await ensureLogin("google_test_id");

const SCREENS = [
  { name: "home", url: "/"},
  { name: "pedidos", url: "/pedidos" },
  { name: "presupuestos", url: "/presupuestos" },
  { name: "catalogo", url: "/products" },
  { name: "productos", url: "/productos" },
  { name: "ingredientes", url: "/admin/ingredients" },
  { name: "calculator", url: "/admin/calculator/products" },
  { name: "panel", url: "/admin" },
  { name: "settings", url: "/admin/settings" },
  { name: "perfil", url: "/profile" },
];

const out = [];
for (const s of SCREENS) {
  await page.goto("http://localhost:3000" + s.url);
  await page.waitForLoadState();
  await page.waitForTimeout(3200);
  const info = await page.evaluate(() => {
    const navs = [...document.querySelectorAll("nav")].map(n =>
      [...n.querySelectorAll("a,button")].map(a => a.textContent.trim()).filter(Boolean).slice(0, 16)
    );
    const skeleton = document.querySelectorAll(".skeleton, [class*=skeleton], [class*=Skeleton]").length;
    const toasts = [...document.querySelectorAll("[data-sonner-toast]")].map(t => t.textContent.trim().slice(0, 100));
    const chakraToasts = document.querySelectorAll("[data-chakra-toast]").length;
    const err = document.querySelector("main [role=alert]")?.textContent?.trim().slice(0, 120) || null;
    return {
      url: location.href,
      h1: document.querySelector("h1,h2")?.textContent?.trim()?.slice(0, 60) || null,
      navCount: navs.length,
      nav0: navs[0] || [],
      skeleton,
      toasts,
      chakraToasts,
      err,
    };
  });
  out.push({ ...s, ...info });
  console.log(`[${s.name}] url=${info.url} h1="${info.h1}" navs=${info.navCount} skel=${info.skeleton} chakra=${info.chakraToasts} err=${info.err}`);
}
console.log("DONE");
