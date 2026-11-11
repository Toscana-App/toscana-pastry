const task = await taskSpace(1);
const page = task.page("p1");

async function visit(url, note) {
  await page.goto(url);
  await page.waitForLoadState();
  await page.waitForTimeout(1200);
  console.log(`== ${note} :: ${url} ==`);
  console.log(await page.snapshot());
}

await visit("http://localhost:3000/admin/ingredients", "admin ingredients list");
await visit("http://localhost:3000/admin/ingredients/new", "admin ingredient new");
await visit("http://localhost:3000/admin/settings", "admin settings");
