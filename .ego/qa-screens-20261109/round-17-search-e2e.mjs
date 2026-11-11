// E2E: search del hero filtra el catálogo + botón fuera del input (gap 12px)
const task = await takeOverTaskSpace(1).catch(async () => taskSpace(1));
const page = task.page("p1");

const login = async (googleId) => {
  await page.evaluate(async (id) => {
    await fetch("http://localhost:8000/api/v1/auth/login", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ google_id: id }),
    });
  }, googleId);
};

const catalogNames = async () => await page.evaluate(() => {
  const sec = document.getElementById("catalogo");
  return sec ? sec.innerText.replace(/\n+/g, " | ") : "(sin sección catalogo)";
});

// --- Cliente: catálogo completo ---
await login("cliente_test_id");
await page.goto("http://localhost:3000/");
await page.waitForLoadState();
await page.waitForTimeout(1800);

const all = await catalogNames();
console.log("CATALOGO COMPLETO:", all.slice(0, 400));

// Geometría: botón fuera del input, gap 12px
const geo = await page.evaluate(() => {
  const form = document.querySelector('form[role="search"]');
  if (!form) return null;
  const input = form.querySelector("input");
  const btn = form.querySelector("button");
  const ib = input.closest("div");
  const ir = input.getBoundingClientRect(), br = btn.getBoundingClientRect();
  return {
    btnOutsideInput: !(input.parentElement && input.parentElement.contains(btn) && input.parentElement !== btn.parentElement),
    gap: +(br.x - ir.right).toFixed(1),
  };
});
console.log("GEO:", JSON.stringify(geo));

// --- Search: "torta" ---
await page.click('form[role="search"] input', { label: "focus search" });
await page.keyboard.type("torta");
await page.waitForTimeout(1500);
console.log("URL:", await page.url());
let filtered = await catalogNames();
console.log("FILTRO torta:", filtered.slice(0, 300));

// --- Search: "chocolate" ---
await page.click('form[role="search"] input', { label: "focus search 2" });
await page.keyboard.type("chocolate");
await page.waitForTimeout(1500);
filtered = await catalogNames();
console.log("FILTRO torta+chocolate:", filtered.slice(0, 300));

// --- Search: término sin resultados ---
await page.click('form[role="search"] input', { label: "focus search 3" });
await page.keyboard.type("zzz");
await page.waitForTimeout(1500);
filtered = await catalogNames();
console.log("FILTRO torta+chocolatezzz:", filtered.slice(0, 200));

// --- Admin: no ve el search en el hero ---
await login("admin_test_id");
await page.goto("http://localhost:3000/");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const adminHasSearch = await page.evaluate(() => !!document.querySelector('form[role="search"]'));
console.log("ADMIN home search visible:", adminHasSearch);
