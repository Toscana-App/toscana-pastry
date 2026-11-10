const task = await taskSpace(1);
const page = task.page("p1");

// customer session (re-login to be sure)
await page.evaluate(async () => {
  await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_id: "cliente_test_id" }),
  });
});

await page.goto("http://localhost:3000/tienda/11111111-1111-4111-8111-111111111111");
await page.waitForLoadState();
await page.waitForTimeout(800);
await page.click("text=Agregar al carrito", { label: "add product to cart" });
await page.waitForTimeout(1500);

await page.goto("http://localhost:3000/carrito");
await page.waitForLoadState();
await page.waitForTimeout(1200);
const cart = await page.evaluate(() => document.body.innerText.slice(0, 400).replace(/\n+/g, " | "));
console.log("CART:", cart);

await page.goto("http://localhost:3000/checkout");
await page.waitForLoadState();
await page.waitForTimeout(1500);
const co = await page.evaluate(() => document.body.innerText.slice(0, 400).replace(/\n+/g, " | "));
console.log("CHECKOUT:", co);
