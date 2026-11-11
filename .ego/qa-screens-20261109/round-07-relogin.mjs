const task = await taskSpace("toscana-qa-screens-3");
const page = task.page("p1");
console.log({ spaceId: task.spaceId });

await page.goto("http://localhost:3000/login");
await page.waitForLoadState();
await page.click("text=Continuar con Google", { label: "login mock Google as admin" });
await page.waitForURL("**/admin", { timeout: 25000 });
console.log("logged in, role target ok, now at:", await page.url());
