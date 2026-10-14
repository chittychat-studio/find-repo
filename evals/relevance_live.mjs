// SPEC RS34/RS34a: score the LIVE relevance check (the deployed /api/relevance — Workers AI first, then any fallback)
// against evals/relevance_set.json (91 hand-labelled repos, 11 queries). No key needed: it calls the public endpoint
// exactly like the web page does. Spends one AI check per query (9) from the site's free daily allowance.
//   node evals/relevance_live.mjs [https://replore.cardzo.co.in/api/relevance]
// Same pass bar as relevance_llm.mjs: keep >= 95% of relevant repos AND drop >= 80% of off-topic ones.
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const ENDPOINT = args.find(a => a.startsWith("http")) || process.env.RELEVANCE_ENDPOINT || "https://replore.cardzo.co.in/api/relevance";
const MODELS = [null];   // scores the endpoint's own chain (the model override used for the 2026-10-14 comparison is gone)
const { items } = JSON.parse(readFileSync(new URL("./relevance_set.json", import.meta.url)));
const byQuery = new Map();
for (const it of items) { if (!byQuery.has(it.query)) byQuery.set(it.query, []); byQuery.get(it.query).push(it); }

async function runOne(model) {
let keptRel = 0, rel = 0, droppedOff = 0, off = 0, totalMs = 0, okN = 0; const misses = [], failed = [];
for (const [query, group] of byQuery) {
  const repos = group.map(g => ({ name: g.name, description: g.text, topics: [] }));
  let res, body; const t0 = Date.now();
  try {
    res = await fetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json", "X-Replore-Diag": "1" },
      body: JSON.stringify(model ? { query, repos, model } : { query, repos }) });
    body = await res.json();
  } catch (e) { body = { error: "unreachable: " + e.message }; res = { ok: false, status: 0 }; }
  const ms = Date.now() - t0;
  const diag = (body && body.diag || []).map(d => `${(d.model || d.p).replace("@cf/", "")} ${d.ms}ms ${d.code}`).join(" → ");
  if (!res.ok || !Array.isArray(body.drop)) {
    failed.push(`${query} — HTTP ${res.status} ${body && body.error || ""} after ${ms} ms (${group.length} repos)${diag ? " [" + diag + "]" : ""}`);
    console.log(`FAILED : ${query} (${group.length} repos) — HTTP ${res.status} ${body && body.error || ""} after ${ms} ms ${diag ? "[" + diag + "]" : ""}`);
    await new Promise(r => setTimeout(r, 1500)); continue;
  }
  okN++; totalMs += ms;
  const dropped = new Map(body.drop.map(d => [d.i, d.why]));
  group.forEach((g, i) => {
    if (g.rel) { rel++; if (!dropped.has(i)) keptRel++; else misses.push(`WRONGLY DROPPED  ${g.name} | ${query}`); }
    else { off++; if (dropped.has(i)) droppedOff++; else misses.push(`WRONGLY KEPT     ${g.name} | ${query}`); }
  });
  console.log(`checked: ${query} (${group.length} repos, ${body.drop.length} dropped) in ${ms} ms ${diag ? "[" + diag + "]" : ""}`);
  await new Promise(r => setTimeout(r, 1500));
}
const k = rel ? keptRel / rel : 0, d = off ? droppedOff / off : 0, pass = !failed.length && k >= 0.95 && d >= 0.80;
console.log(`\nmodel: ${model || "(production chain)"}   endpoint: ${ENDPOINT}`);
console.log(`queries checked: ${byQuery.size - failed.length}/${byQuery.size}` + (failed.length ? "  — INCOMPLETE, the score below covers only the checked ones" : ""));
failed.forEach(f => console.log("  CHECK DID NOT RUN  " + f));
console.log(`relevant kept: ${keptRel}/${rel} (${(100 * k).toFixed(0)}%)   off-topic dropped: ${droppedOff}/${off} (${(100 * d).toFixed(0)}%)   avg ${okN ? Math.round(totalMs / okN) : "-"} ms`);
misses.forEach(m => console.log("  " + m));
console.log(pass ? "PASS — meets the RS34 bar" : failed.length ? "FAIL — some checks did not run (see above)" : "FAIL — below the bar (keep >= 95% relevant, drop >= 80% off-topic)");
return { model: model || "(production chain)", pass, checked: byQuery.size - failed.length, kept: k, dropped: d, avgMs: okN ? Math.round(totalMs / okN) : null };
}
const results = [];
for (const m of MODELS) { console.log("\n=== " + (m || "production chain") + " ==="); results.push(await runOne(m)); }
if (results.length > 1) {
  console.log("\n=== SUMMARY ===");
  results.forEach(r => console.log(`${r.pass ? "PASS" : "fail"}  ${r.model.padEnd(48)} checked ${r.checked}/${byQuery.size}  kept ${(100 * r.kept).toFixed(0)}%  dropped ${(100 * r.dropped).toFixed(0)}%  avg ${r.avgMs ?? "-"} ms`));
}
const pass = results.some(r => r.pass);
process.exit(pass ? 0 : 1);
