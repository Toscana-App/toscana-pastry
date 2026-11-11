const task = await taskSpace(1);
const page = task.page("p1");

// ensure customer session
await page.evaluate(async () => {
  await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_id: "cliente_test_id" }),
  });
});

const shots = [
  ["/", "home"],
  ["/carrito", "carrito"],
  ["/tienda", "tienda"],
];
for (const [path, name] of shots) {
  await page.goto("http://localhost:3000" + path);
  await page.waitForLoadState();
  await page.waitForTimeout(1200);
  const hasSearch = await page.evaluate(() => !!document.querySelector('form[role="search"]'));
  console.log(name, path, "search visible:", hasSearch);
  await page.screenshot({ path: "C:/Users/Usuario/toscana-pastry/.ego/qa-screens-20261109/shot-" + name + "-nav.png" });
}

// overlap analysis on home
await page.goto("http://localhost:3000/");
await page.waitForLoadState();
await page.waitForTimeout(1200);
const geo = await page.evaluate(() => {
  const form = document.querySelector('form[role="search"]');
  if (!form) return null;
  const input = form.querySelector("input");
  const btn = form.querySelector("button");
  const icon = form.querySelector("svg, [data-start]");
  const r = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), right: Math.round(b.right) }; };
  return { form: r(form), input: r(input), btn: r(btn), navH: document.querySelector("nav")?.getBoundingClientRect().height };
});
console.log("GEO:", JSON.stringify(geo, null, 1));
