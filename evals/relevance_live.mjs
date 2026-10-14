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

let keptRel = 0, rel = 0, droppedOff = 0, off = 0; const misses = [], failed = [];
for (const [query, group] of byQuery) {
  const repos = group.map(g => ({ name: g.name, description: g.text, topics: [] }));
  let res, body; const t0 = Date.now();
  try {
    res = await fetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, repos }) });
    body = await res.json();
  } catch (e) { body = { error: "unreachable: " + e.message }; res = { ok: false, status: 0 }; }
  const ms = Date.now() - t0;
  if (!res.ok || !Array.isArray(body.drop)) {          // record and keep going, so one slow call doesn't hide the rest
    failed.push(`${query} — HTTP ${res.status} ${body && body.error || ""} after ${ms} ms (${group.length} repos)`);
    console.log(`FAILED : ${query} (${group.length} repos) — HTTP ${res.status} ${body && body.error || ""} after ${ms} ms`);
    await new Promise(r => setTimeout(r, 3000)); continue;
  }
  const dropped = new Map(body.drop.map(d => [d.i, d.why]));
  group.forEach((g, i) => {
    if (g.rel) { rel++; if (!dropped.has(i)) keptRel++; else misses.push(`WRONGLY DROPPED  ${g.name} (${dropped.get(i)}) | ${query}`); }
    else { off++; if (dropped.has(i)) droppedOff++; else misses.push(`WRONGLY KEPT     ${g.name} | ${query}`); }
  });
  console.log(`checked: ${query} (${group.length} repos, ${body.drop.length} dropped) in ${ms} ms`);
  await new Promise(r => setTimeout(r, 3000));          // gentle on the shared allowance
}
const k = rel ? keptRel / rel : 0, d = off ? droppedOff / off : 0, pass = !failed.length && k >= 0.95 && d >= 0.80;
console.log(`\nendpoint: ${ENDPOINT}`);
console.log(`queries checked: ${byQuery.size - failed.length}/${byQuery.size}` + (failed.length ? "  — INCOMPLETE, the score below covers only the checked ones" : ""));
failed.forEach(f => console.log("  CHECK DID NOT RUN  " + f));
console.log(`relevant kept: ${keptRel}/${rel} (${(100 * k).toFixed(0)}%)   off-topic dropped: ${droppedOff}/${off} (${(100 * d).toFixed(0)}%)`);
misses.forEach(m => console.log("  " + m));
console.log(pass ? "PASS — meets the RS34 bar" : failed.length ? "FAIL — some checks did not run (see above)" : "FAIL — below the bar (keep >= 95% relevant, drop >= 80% off-topic)");
process.exit(pass ? 0 : 1);
