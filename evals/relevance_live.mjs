// SPEC RS34/RS34a: score the LIVE relevance check (the deployed /api/relevance — Workers AI first, then any fallback)
// against evals/relevance_set.json (84 hand-labelled repos, 9 queries). No key needed: it calls the public endpoint
// exactly like the web page does. Spends one AI check per query (9) from the site's free daily allowance.
//   node evals/relevance_live.mjs [https://replore.pages.dev/api/relevance]
// Same pass bar as relevance_llm.mjs: keep >= 95% of relevant repos AND drop >= 80% of off-topic ones.
import { readFileSync } from "node:fs";

const ENDPOINT = process.argv[2] || process.env.RELEVANCE_ENDPOINT || "https://replore.pages.dev/api/relevance";
const { items } = JSON.parse(readFileSync(new URL("./relevance_set.json", import.meta.url)));
const byQuery = new Map();
for (const it of items) { if (!byQuery.has(it.query)) byQuery.set(it.query, []); byQuery.get(it.query).push(it); }

let keptRel = 0, rel = 0, droppedOff = 0, off = 0; const misses = [];
for (const [query, group] of byQuery) {
  const repos = group.map(g => ({ name: g.name, description: g.text, topics: [] }));
  let res, body;
  try {
    res = await fetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, repos }) });
    body = await res.json();
  } catch (e) { console.error(`"${query}": endpoint unreachable (${e.message})`); process.exit(1); }
  if (!res.ok || !Array.isArray(body.drop)) {          // fail closed: a check that didn't run can't be scored
    console.error(`"${query}": check failed (HTTP ${res.status} ${body && body.error || ""}) — fix this before trusting the score`);
    process.exit(1);
  }
  const dropped = new Map(body.drop.map(d => [d.i, d.why]));
  group.forEach((g, i) => {
    if (g.rel) { rel++; if (!dropped.has(i)) keptRel++; else misses.push(`WRONGLY DROPPED  ${g.name} (${dropped.get(i)}) | ${query}`); }
    else { off++; if (dropped.has(i)) droppedOff++; else misses.push(`WRONGLY KEPT     ${g.name} | ${query}`); }
  });
  console.log(`checked: ${query} (${group.length} repos, ${body.drop.length} dropped)`);
  await new Promise(r => setTimeout(r, 3000));          // gentle on the shared allowance
}
const k = keptRel / rel, d = droppedOff / off, pass = k >= 0.95 && d >= 0.80;
console.log(`\nendpoint: ${ENDPOINT}`);
console.log(`relevant kept: ${keptRel}/${rel} (${(100 * k).toFixed(0)}%)   off-topic dropped: ${droppedOff}/${off} (${(100 * d).toFixed(0)}%)`);
misses.forEach(m => console.log("  " + m));
console.log(pass ? "PASS — meets the RS34 bar" : "FAIL — below the bar (keep >= 95% relevant, drop >= 80% off-topic)");
process.exit(pass ? 0 : 1);
