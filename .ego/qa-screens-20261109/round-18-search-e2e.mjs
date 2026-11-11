// E2E search del hero: cliente ve, admin no; filtra catálogo; botón fuera con gap 12px
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

const typeSearch = async (term) => {
  await page.click('form[role="search"] input', { label: "focus search input" });
  await page.evaluate(() => {
    const el = document.querySelector('form[role="search"] input');
    el.focus();
    el.select();
  });
  await page.keyboard.press("Backspace");
  if (term) await page.keyboard.type(term);
  await page.waitForTimeout(1500);
};

// --- Cliente ---
await login("cliente_test_id");
await page.goto("http://localhost:3000/");
await page.waitForLoadState();
await page.waitForTimeout(2000);

const all = await catalogNames();
console.log("CATALOGO COMPLETO:", all.slice(0, 350));

const geo = await page.evaluate(() => {
  const form = document.querySelector('form[role="search"]');
  if (!form) return null;
  const input = form.querySelector("input");
  const btn = form.querySelector("button");
  const ir = input.getBoundingClientRect(), br = btn.getBoundingClientRect();
  return { btnOutside: !input.parentElement.contains(btn), gap: +(br.x - ir.right).toFixed(1) };
});
console.log("GEO:", JSON.stringify(geo));

await typeSearch("torta");
console.log("FILTRO 'torta':", await catalogNames(), "->", await page.url());

await typeSearch("chocolate");
console.log("FILTRO 'chocolate':", (await catalogNames()).slice(0, 250));

await typeSearch("limón");
console.log("FILTRO 'limón':", (await catalogNames()).slice(0, 250));

await typeSearch("zzz");
console.log("FILTRO 'zzz':", (await catalogNames()).slice(0, 200));

// limpiar -> vuelve al catálogo completo
await typeSearch("");
console.log("SIN FILTRO:", (await catalogNames()).slice(0, 120));

// --- Admin: sin search en el hero ---
await login("admin_test_id");
await page.goto("http://localhost:3000/");
await page.waitForLoadState();
await page.waitForTimeout(1800);
const adminHasSearch = await page.evaluate(() => !!document.querySelector('form[role="search"]'));
console.log("ADMIN home search visible:", adminHasSearch);
