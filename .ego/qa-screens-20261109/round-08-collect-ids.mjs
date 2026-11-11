const task = await taskSpace(1);
const page = task.page("p1");

// collect real ids from the API for detail screens
const ids = await page.evaluate(() =>
  Promise.all(
    ["/orders", "/ingredients", "/products", "/calc/products", "/budgets"].map((ep) =>
      fetch("http://localhost:8000/api/v1" + ep, { credentials: "include" })
        .then(async (r) => ({ ep, status: r.status, body: (await r.text()).slice(0, 400) }))
    )
  )
);
console.log("IDS:", JSON.stringify(ids, null, 1));
