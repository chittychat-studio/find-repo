// RS22: exercise the web page's pure logic in Node (no browser, no network).
const fs = require("fs"), path = require("path"), assert = require("assert");
const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const code = html.match(/<script>([\s\S]*)<\/script>/)[1].replace('"use strict";', "");
// fake DOM: elements support the methods the page's load-time code calls (chips, modals, theme, RS21-RS24)
const el = () => ({value:"",checked:false,textContent:"",innerHTML:"",type:"",className:"",dataset:{},style:{},
                   addEventListener(){}, appendChild(){}, focus(){}, querySelector:()=>el(), querySelectorAll:()=>[],
                   classList:{add(){},remove(){},toggle(){}}, getAttribute:()=>null, setAttribute(){}, clientWidth:560});
global.document = {getElementById: el, createElement: el, querySelectorAll:()=>[], addEventListener(){},
                   documentElement: el()};
global.matchMedia = () => ({matches:false});
global.window = global;
const s = {};
new Function("document", "localStorage",
  code + "; this.keywordQueries=keywordQueries; this.rankByFit=rankByFit; this.fitScore=fitScore; this.whyRelevant=whyRelevant; this.esc=esc; this.lu=lu; this.freeText=freeText;" +
  " this.keep=keep; this.harmful=harmful; this.harmfulRepo=harmfulRepo; this.prdFeatures=prdFeatures; this.fmtWait=fmtWait; this.gateLine=gateLine;").call(s, document, global.localStorage || {getItem:()=>null,setItem(){},removeItem(){}});

// RS16: iOS excludes macOS
// RS16: expansions are specific on-topic phrases, never a bare category (live regression: "website" -> "frontend framework"
// pulled Ionic/Expo/qiankun/Luigi/choo/san/argon into a portfolio search)
{ const q = s.keywordQueries("portfolio website builder", "");
  assert.deepStrictEqual(q, ["portfolio website builder", "portfolio template", "portfolio website", "landing page template"], q);
  const bare = /^(frontend|backend|web|javascript|css|ui|mobile|game|chatbot|ai agent|ai) (framework|library|engine)s?$/;
  ["website","web","portfolio","dashboard","blog","ecommerce","game","chatbot","map","diet","powerpoint","ai","security","pdf"].forEach(w =>
    s.keywordQueries(w, "").forEach(x => assert.ok(!bare.test(x), w + " expanded to bare category: " + x))); }
// RS16 live-audit regressions (quick-picks that returned junk, 1 result or nothing)
{ const kq = t => s.keywordQueries(t, "");
  assert.ok(kq("learn web security by hacking a practice app").includes("vulnerable web application"));      // was "web app starter"
  assert.ok(!kq("learn web security by hacking a practice app").some(q => /starter/.test(q)));
  assert.ok(kq("offline maps for my trip planner app").includes("maplibre"));                               // plural "maps" -> map
  assert.ok(!kq("an ai image generator").some(q => /agent/.test(q)));                                       // was "ai agent framework"
  assert.ok(kq("a simple 2D browser game engine for beginners").includes("phaser game"));
  assert.ok(kq("a chatbot that answers questions from my PDFs, Python").includes("chat with pdf"));
  assert.ok(kq("my first iPhone app, a habit tracker").every(q => !/\bfirst\b/.test(q)));                  // filler word dropped
  ["by","from","first"].forEach(w => assert.ok(!kq("learn security by doing from first principles").some(q => q.split(" ").includes(w)), w));
  assert.ok(kq("a portfolio website with smooth scroll animations")[0].split(" ").length <= 3);            // core query <= 3 words
}
assert.ok(s.keywordQueries("a diet app for iphone", "ios").every(q => q.includes("-topic:macos")));
// RS14/RS20 labels
assert.strictEqual(s.freeText("MIT"), "Yes");
assert.strictEqual(s.freeText("AGPL-3.0"), "Free to use, but you must share your code");
assert.ok(s.lu("MPL-2.0").startsWith("OK in a paid product"));
// RS18 intent refusal + repo drops (incl. the live 'hacking of WhatsApp' repo that an earlier regex missed)
assert.ok(s.harmful("hack into my ex girlfriend account"));
assert.ok(!s.harmful("build a chat app"));
["WhatsApp Hacking Learn about ethical hacking of WhatsApp accounts", "hack instagram account tool",
 "Free robux generator", "aimbot wallhack"].forEach(d => assert.ok(s.harmfulRepo(d), "should flag: " + d));
assert.ok(!s.harmfulRepo("A privacy-focused nutrition tracker"));
// RS4a/RS3/RS4 filters + RS5 fit ranking (relevance + stars + freedom) with starter floor
const now = "2026-09-01T00:00:00Z", old = "2019-01-01T00:00:00Z";
const q1 = [{full_name:"a/big",stargazers_count:50000,license:{spdx_id:"MIT"},pushed_at:now,description:"big"},
            {full_name:"a/tpl",stargazers_count:6000,license:{spdx_id:"MIT"},pushed_at:now,is_template:true,description:"t"},
            {full_name:"a/old",stargazers_count:9000,license:{spdx_id:"MIT"},pushed_at:old,description:"o"},
            {full_name:"a/nolic",stargazers_count:9000,license:null,pushed_at:now,description:"n"},
            {full_name:"a/tiny",stargazers_count:5,license:{spdx_id:"MIT"},pushed_at:now,description:"ti"}];
const q2 = [{full_name:"b/x",stargazers_count:7000,license:{spdx_id:"MIT"},pushed_at:now,description:"x"}];
const ex = {license:0,stale:0,low:0,fork:0,harm:0};
const k1 = s.keep(q1, 50, "", ex), k2 = s.keep(q2, 50, "", ex);
assert.deepStrictEqual(k1.map(r => r.name), ["a/big", "a/tpl"]);  // old, no-license, tiny dropped
assert.strictEqual(ex.stale, 1); assert.strictEqual(ex.license, 1); assert.strictEqual(ex.low, 1);
assert.deepStrictEqual(s.rankByFit([k1, k2], true).map(r => r.name), ["a/big", "a/tpl", "b/x"]);
// RS5: a precise top-of-search match with far fewer stars can outrank a tangential giant
const rel = [{name:"tiny/exact",stars:300,spdx:"MIT",starter:false,rel:0},
             {name:"big/tangential",stars:120000,spdx:"MIT",starter:false,rel:12}];
assert.strictEqual(s.rankByFit([rel], false)[0].name, "tiny/exact", "relevance should lift a smaller exact match");
// RS5: between equally relevant, equally popular repos, the freer license wins
const lic = [{name:"a/permissive",stars:1000,spdx:"MIT",starter:false,rel:0},
             {name:"a/copyleft",stars:1000,spdx:"AGPL-3.0",starter:false,rel:0}];
assert.strictEqual(s.rankByFit([lic], false)[0].name, "a/permissive", "free-to-use should break the tie");
// RS5/RS24: every card explains why the repo is relevant, honestly (keyword match, not AI)
const w1 = s.whyRelevant({name:"me/rag-chat", desc:"A RAG chatbot over your PDFs", rel:0}, ["rag","chatbot","pdfs"]);
assert.ok(w1.startsWith("Matches your words") && w1.includes("rag"), w1);
assert.strictEqual(s.whyRelevant({name:"x/y", desc:"unrelated", rel:1}, ["zzz"]), "Top match for your search");
assert.strictEqual(s.whyRelevant({name:"x/y", desc:"unrelated", rel:9}, ["zzz"]), "Related to your search");
// whole-word match: "ai" must NOT fire on "email"
assert.strictEqual(s.whyRelevant({name:"me/mailer", desc:"a fast email client", rel:0}, ["ai","chat"]), "Top match for your search");
// esc escapes quotes so repo text can't break out of an HTML attribute
assert.ok(s.esc('a"b').indexOf('"') < 0 && s.esc("a'b").indexOf("'") < 0, "esc should escape quotes");
// RS5: a repo found in a later query at a better position takes the lower rel (cross-query dedup)
const xseen = {}, xex = {license:0,stale:0,low:0,fork:0,harm:0};
const L1 = s.keep([{full_name:"z/lo",stargazers_count:5,license:{spdx_id:"MIT"},pushed_at:now,description:"d"},
                   {full_name:"x/dup",stargazers_count:1000,license:{spdx_id:"MIT"},pushed_at:now,description:"d"}], 50, "", xex, xseen);
const xdup = L1.find(r => r.name === "x/dup");
assert.strictEqual(xdup.rel, 1, "first query sees x/dup at index 1");
s.keep([{full_name:"x/dup",stargazers_count:1000,license:{spdx_id:"MIT"},pushed_at:now,description:"d"}], 50, "", xex, xseen);
assert.strictEqual(xdup.rel, 0, "dup rel drops to the better position found by a later query");
console.log("web logic ok");

// RS23: PRD feature extraction (client-side, capped for the rate limit)
const prd = ["# My app PRD","## Features","- User authentication with email and Google",
 "- Payment checkout with Stripe","- Push notifications","* Image upload and cropping",
 "The app must support offline mode","1) Admin dashboard with charts","random prose line here"].join("\n");
const f = s.prdFeatures(prd);
assert.ok(f.length >= 2 && f.length <= 6, "features: " + f.length);
assert.ok(f.some(x => x.includes("authentication")) && f.some(x => x.includes("payment")), f.join(" | "));
console.log("prd ok:", f.join(" | "));

// RS34 limit note: wait wording (rounded up, never 0, capped at 24 h) and the three failure lines
{ const w = s.fmtWait;
  assert.strictEqual(w(0), "a minute"); assert.strictEqual(w(NaN), "a minute"); assert.strictEqual(w(-5), "a minute");
  assert.strictEqual(w(60), "a minute"); assert.strictEqual(w(61), "2 minutes"); assert.strictEqual(w(3540), "59 minutes");
  assert.strictEqual(w(3600), "1 hour"); assert.strictEqual(w(3660), "1 hour 1 minute"); assert.strictEqual(w(19200), "5 hours 20 minutes");
  assert.strictEqual(w(1e12), "24 hours");
  const g = s.gateLine;
  assert.match(g({ok:false,error:"llm_daily_limit",resetsIn:19200}), /gate-wait.*used up.*They reset in 5 hours 20 minutes\./);
  assert.match(g({ok:false,error:"llm_rate_limited",resetsIn:20}), /gate-wait.*busy right now.*Try again in a minute\./);
  assert.match(g({ok:false,error:"llm_error"}), /Couldn.t check relevance/);
  assert.ok(!/gate-wait/.test(g({ok:false,error:"llm_error"})));
  assert.strictEqual(g(null), "");
  console.log("limit note ok"); }

// RS34b: the function's cached example list is exactly the page's quick-pick texts
{ const src = fs.readFileSync(path.join(__dirname, "..", "functions", "api", "relevance.js"), "utf8");
  const block = src.match(/EXAMPLE_QUERIES = \[([\s\S]*?)\];/)[1];
  const fnList = [...block.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map(m => m[1]);
  const pageList = [...html.match(/var EXAMPLES=\[([\s\S]*?)\];/)[1].matchAll(/text:"((?:[^"\\]|\\.)*)"/g)].map(m => m[1]);
  assert.deepStrictEqual(fnList, pageList);
  console.log("example list in sync"); }
