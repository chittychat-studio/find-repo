// SPEC RS34: score the live relevance check against evals/relevance_set.json (91 hand-labelled repos).
// Spends a few LLM calls on YOUR key — run by the maintainer, never in CI:
//   LLM_API_KEY=... [LLM_BASE_URL=...] [LLM_MODEL=...] node evals/relevance_llm.mjs
// Pass bar (same as the browser-model test): keep >= 95% of relevant repos AND drop >= 80% of off-topic ones.
import { readFileSync } from "node:fs";
import { judge } from "../functions/api/relevance.js";

const env = { LLM_API_KEY: process.env.LLM_API_KEY, LLM_BASE_URL: process.env.LLM_BASE_URL, LLM_MODEL: process.env.LLM_MODEL };
if (!env.LLM_API_KEY) { console.error("Set LLM_API_KEY first (it is only sent to the provider)."); process.exit(2); }
const { items } = JSON.parse(readFileSync(new URL("./relevance_set.json", import.meta.url)));
const byQuery = new Map();
for (const it of items) { if (!byQuery.has(it.query)) byQuery.set(it.query, []); byQuery.get(it.query).push(it); }

let keptRel = 0, rel = 0, droppedOff = 0, off = 0; const misses = [];
for (const [query, group] of byQuery) {
  const repos = group.map(g => ({ name: g.name, description: g.text, topics: [] }));
  const out = await judge(query, repos, env);
  if (out.status !== 200) { console.error(`"${query}": check failed (${out.error}) — fix this before trusting the score`); process.exit(1); }
  const dropped = new Map(out.body.drop.map(d => [d.i, d.why]));
  group.forEach((g, i) => {
    if (g.rel) { rel++; if (!dropped.has(i)) keptRel++; else misses.push(`WRONGLY DROPPED  ${g.name} (${dropped.get(i)}) | ${query}`); }
    else { off++; if (dropped.has(i)) droppedOff++; else misses.push(`WRONGLY KEPT     ${g.name} | ${query}`); }
  });
  await new Promise(r => setTimeout(r, 2500));   // stay under free-tier rate limits
}
const k = keptRel / rel, d = droppedOff / off, pass = k >= 0.95 && d >= 0.80;
console.log(`relevant kept: ${keptRel}/${rel} (${(100 * k).toFixed(0)}%)   off-topic dropped: ${droppedOff}/${off} (${(100 * d).toFixed(0)}%)`);
misses.forEach(m => console.log("  " + m));
console.log(pass ? "PASS — meets the RS34 bar" : "FAIL — below the bar (keep >= 95% relevant, drop >= 80% off-topic)");
process.exit(pass ? 0 : 1);
