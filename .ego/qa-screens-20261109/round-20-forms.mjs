// Round 20: validaciones de formularios + toasts (goey vs chakra) + skeletons
const task = await takeOverTaskSpace(1).catch(async () => taskSpace(1));
const page = task.page("p1");

const goeyCount = () => page.evaluate(() => document.querySelectorAll("[data-sonner-toast]").length);
const chakraCount = () => page.evaluate(() => {
  const toasts = document.querySelectorAll('[data-chakra-toast]');
  if (toasts.length) return toasts.length;
  // chakra v3 Toaster: region with role status containing c-toast root
  return document.querySelectorAll('.c-toaster [role="status"], .c-toast').length;
});
const goeyTexts = () => page.evaluate(() =>
  [...document.querySelectorAll("[data-sonner-toast]")].map(t => t.textContent?.trim().slice(0, 80))
);
const toastAudit = async (label) => {
  console.log(`TOAST ${label} :: goey=${await goeyCount()} chakra=${await chakraCount()} texts=${JSON.stringify(await goeyTexts())}`);
};

// login admin
await page.goto("http://localhost:3000/login");
await page.waitForLoadState();
await page.waitForTimeout(700);
await page.evaluate(async () => {
  await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_id: "google_test_id" }),
  });
});

// ---- 1. ProductEditor: guardar sin nombre -> warning toast ----
await page.goto("http://localhost:3000/admin/calculator/products/new");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const saveBtn = await page.evaluate(() => {
  const btns = [...document.querySelectorAll("button")];
  const b = btns.find(x => /guardar|save/i.test(x.textContent || ""));
  return b ? b.textContent.trim() : null;
});
console.log("PRODUCT NEW save btn:", saveBtn);
await page.click('button:has-text("Guardar")', { label: "click guardar sin nombre" });
await page.waitForTimeout(1200);
await toastAudit("product-new-empty-name");

// ---- 2. Calculator settings: percent invalido (150) ----
await page.goto("http://localhost:3000/admin/calculator/settings");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const settingsInputs = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll("input")];
  return inputs.map(i => ({ id: i.id || null, type: i.type, value: i.value.slice(0, 30) })).slice(0, 12);
});
console.log("SETTINGS inputs:", JSON.stringify(settingsInputs));

// ---- 3. Ingredients new: enviar vacio/negativo ----
await page.goto("http://localhost:8000/admin/ingredients/new");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const ingInputs = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll("input,select,textarea")];
  return inputs.map(i => ({ tag: i.tagName, type: i.type || null, id: i.id || null, name: i.name || null, placeholder: i.placeholder || null, required: i.required })).slice(0, 15);
});
console.log("INGREDIENT inputs:", JSON.stringify(ingInputs));
const ingSubmit = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button[type=submit],button")].find(b => /guardar|crear|agregar/i.test(b.textContent || ""));
  if (btn) { btn.click(); return btn.textContent.trim(); }
  return null;
});
console.log("INGREDIENT submit:", ingSubmit);
await page.waitForTimeout(1500);
await toastAudit("ingredient-new-empty");
const ingErrors = await page.evaluate(() =>
  [...document.querySelectorAll('[aria-invalid="true"], [role="alert"], .c-field__error, [class*="error"]')]
    .map(e => e.textContent?.trim()).filter(Boolean).slice(0, 5)
);
console.log("INGREDIENT inline errors:", JSON.stringify(ingErrors));

// ---- 4. Productos new (admin CRUD): enviar vacio ----
await page.goto("http://localhost:3000/productos/new");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const prodInputs = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll("input,select,textarea")];
  return inputs.map(i => ({ tag: i.tagName, type: i.type || null, placeholder: i.placeholder || null, required: i.required })).slice(0, 15);
});
console.log("PRODUCTOS inputs:", JSON.stringify(prodInputs));
const prodSubmit = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar|crear|agregar/i.test(b.textContent || ""));
  if (btn) { btn.click(); return btn.textContent.trim(); }
  return null;
});
console.log("PRODUCTOS submit:", prodSubmit);
await page.waitForTimeout(1800);
await toastAudit("productos-new-empty");
const prodErrors = await page.evaluate(() =>
  [...document.querySelectorAll('[aria-invalid="true"], [role="alert"]')]
    .map(e => e.textContent?.trim()).filter(Boolean).slice(0, 5)
);
console.log("PRODUCTOS inline errors:", JSON.stringify(prodErrors));

// ---- 5. Pedido nuevo: enviar vacio ----
await page.goto("http://localhost:3000/pedidos/nuevo");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const pedidoInputs = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll("input,select,textarea")];
  return inputs.map(i => ({ tag: i.tagName, type: i.type || null, placeholder: i.placeholder || null, required: i.required })).slice(0, 12);
});
console.log("PEDIDO inputs:", JSON.stringify(pedidoInputs));
const pedidoSubmit = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar|crear|agregar|registrar/i.test(b.textContent || ""));
  if (btn) { btn.click(); return btn.textContent.trim(); }
  return null;
});
console.log("PEDIDO submit:", pedidoSubmit);
await page.waitForTimeout(1800);
await toastAudit("pedido-nuevo-empty");

console.log("FORMS DONE");
