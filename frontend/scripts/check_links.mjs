import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    base: { type: "string", default: "http://localhost:3111" },
    routes: { type: "string", default: "/,/contact" },
  },
  allowPositionals: false,
});

const baseUrl = values.base.replace(/\/+$/, "");
const origin = new URL(baseUrl).origin;
const routes = values.routes
  .split(",")
  .map((route) => route.trim().replace(/\/+$/, ""))
  .map((route) => (route === "" ? "/" : route));

const ANCHOR_RE = /<a\s[^>]*?href\s*=\s*(["'])([^"']*)\1/gi;
const SKIPPED_SCHEMES = ["mailto:", "tel:", "javascript:", "data:"];

function extractAnchors(html) {
  const targets = new Set();
  for (const match of html.matchAll(ANCHOR_RE)) {
    const href = match[2].trim();
    if (!href || href.startsWith("#")) continue;
    if (SKIPPED_SCHEMES.some((scheme) => href.toLowerCase().startsWith(scheme))) continue;
    let url;
    try {
      url = new URL(href, baseUrl);
    } catch {
      continue;
    }
    if (url.origin !== origin) continue;
    url.hash = "";
    targets.add(url.pathname + url.search);
  }
  return targets;
}

async function statusOf(path) {
  try {
    const response = await fetch(`${baseUrl}${path}`, { redirect: "follow" });
    return response.status;
  } catch (error) {
    return `network error: ${error.message}`;
  }
}

const broken = [];
const checked = new Set();

async function crawl(route) {
  const response = await fetch(`${baseUrl}${route}`, { redirect: "follow" });
  if (response.status !== 200) {
    broken.push({ route, target: route, status: response.status });
    return;
  }
  const html = await response.text();
  for (const target of extractAnchors(html)) {
    if (checked.has(target)) continue;
    checked.add(target);
    const status = await statusOf(target);
    if (status !== 200) {
      broken.push({ route, target, status });
    }
  }
}

for (const route of routes) {
  await crawl(route);
}

if (broken.length > 0) {
  console.error(`Broken links (${broken.length}):`);
  for (const item of broken) {
    console.error(`  ${item.route} -> ${item.target} [${item.status}]`);
  }
  process.exit(1);
}

console.log(`OK: ${checked.size} unique links from ${routes.length} routes, none broken.`);
