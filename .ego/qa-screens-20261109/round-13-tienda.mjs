const task = await taskSpace(1);
const page = task.page("p1");

const urls = [
  "/tienda",
  "/tienda/11111111-1111-4111-8111-111111111111",
];
for (const path of urls) {
  await page.goto("http://localhost:3000" + path);
  await page.waitForLoadState();
  await page.waitForTimeout(1400);
  console.log("== " + path + " ==");
  console.log(await page.snapshot());
}
