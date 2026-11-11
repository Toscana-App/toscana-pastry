const task = await taskSpace("toscana-qa-screens");
const page = task.page("p1");
console.log({ spaceId: task.spaceId });

// 1) Login page (unauthenticated)
await page.goto("http://localhost:3000/login");
await page.waitForLoadState();
console.log("== /login snapshot ==");
console.log(await page.snapshot());
