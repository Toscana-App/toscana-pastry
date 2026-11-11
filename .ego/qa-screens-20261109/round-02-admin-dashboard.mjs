const task = await taskSpace(1);
const page = task.page("p1");

await page.goto("http://localhost:3000/login");
await page.waitForLoadState();
await page.click("text=Continuar con Google", { label: "login with mock Google" });
await page.waitForURL("**/admin", { timeout: 20000 });
await page.waitForTimeout(1500);
console.log("== /admin snapshot ==");
console.log(await page.snapshot({ scope: "full_page" }));
