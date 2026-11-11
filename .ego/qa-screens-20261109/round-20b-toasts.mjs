// Round 20b: toasts goey vs chakra en flujos reales de error/exito
const task = await takeOverTaskSpace(1).catch(async () => taskSpace(1));
const page = task.page("p1");

const toastAudit = async (label) => {
  const info = await page.evaluate(() => {
    const goey = [...document.querySelectorAll("[data-sonner-toast]")].map(t => t.textContent?.trim().slice(0, 90));
    const chakra = document.querySelectorAll('[data-chakra-toast], .c-toast, [data-part="root"][data-chakra-component="ToastRoot"]').length;
    return { goey, chakra };
  });
  console.log(`TOAST ${label} :: goey=${JSON.stringify(info.goey)} chakra=${info.chakra}`);
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

// ---- A. ProductEditor: crear producto -> toast exito (con accion) ----
await page.goto("http://localhost:3000/admin/calculator/products/new");
await page.waitForLoadState();
await page.waitForTimeout(1800);
const saveDisabled = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar/i.test(b.textContent || ""));
  return btn ? btn.disabled : "no btn";
});
console.log("A1 save disabled sin nombre:", saveDisabled);

await page.fill('input[placeholder="Nombre del producto"]', "QA E2E Toast");
await page.waitForTimeout(300);
const saveState = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar/i.test(b.textContent || ""));
  return btn ? { text: btn.textContent.trim(), disabled: btn.disabled } : null;
});
console.log("A2 save con nombre:", JSON.stringify(saveState));
await page.click('button:has-text("Guardar")');
await page.waitForTimeout(2500);
await toastAudit("A3 crear-exito");

// ---- B. Settings: percent invalido (150) -> button disabled ----
await page.goto("http://localhost:3000/admin/calculator/settings");
await page.waitForLoadState();
await page.waitForTimeout(1800);
const before = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar/i.test(b.textContent || ""));
  return btn ? btn.disabled : "no btn";
});
console.log("B1 save disabled (estado actual):", before);
const setInvalid = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll('input[type="number"]')];
  if (!inputs.length) return "no number inputs";
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  inputs[0].focus();
  nativeSetter.call(inputs[0], "150");
  inputs[0].dispatchEvent(new Event("input", { bubbles: true }));
  inputs[0].dispatchEvent(new Event("change", { bubbles: true }));
  return "set 150 in " + (inputs[0].name || inputs[0].id || "first number input");
});
console.log("B2 invalido:", setInvalid);
await page.waitForTimeout(600);
const after = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar/i.test(b.textContent || ""));
  return btn ? btn.disabled : "no btn";
});
console.log("B3 save disabled con 150%:", after);
await toastAudit("B4 sin toast esperado");

// ---- C. Ingredients new: submit vacio -> errores inline ----
await page.goto("http://localhost:3000/admin/ingredients/new");
await page.waitForLoadState();
await page.waitForTimeout(1800);
const cInputs = await page.evaluate(() => {
  const inputs = [...document.querySelectorAll("input,select,textarea")];
  return inputs.map(i => ({ tag: i.tagName, type: i.type || null, ph: (i.placeholder || "").slice(0, 25), req: i.required })).slice(0, 14);
});
console.log("C1 inputs:", JSON.stringify(cInputs));
const cSubmit = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")].find(b => /guardar|crear|agregar/i.test(b.textContent || ""));
  if (btn) { const d = btn.disabled; btn.click(); return { text: btn.textContent.trim(), wasDisabled: d }; }
  return null;
});
console.log("C2 submit:", JSON.stringify(cSubmit));
await page.waitForTimeout(1500);
const cErrors = await page.evaluate(() =>
  [...document.querySelectorAll('[aria-invalid="true"], [role="alert"], [data-part="error-text"], [class*="error-text"]')]
    .map(e => e.textContent?.trim()).filter(Boolean).slice(0, 6)
);
console.log("C3 inline errors:", JSON.stringify(cErrors));
await toastAudit("C4 toast ingredients");

console.log("DONE-20B");
