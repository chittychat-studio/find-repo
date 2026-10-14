// RS22: exercise the web page's pure logic in Node (no browser, no network).
const fs = require("fs"), path = require("path"), assert = require("assert");
const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const code = html.match(/<script>([\s\S]*)<\/script>/)[1].replace('"use strict";', "");
// fake DOM: elements support the methods the page's load-time code calls (chips, modals, theme, RS21-RS24)
const el = () => ({value:"",checked:false,textContent:"",innerHTML:"",type:"",className:"",dataset:{},style:{},
                   addEventListener(){}, appendChild(){}, focus(){}, querySelector:()=>el(), querySelectorAll:()=>[],
                   classList:{add(){},remove(){},toggle(){}}, getAttribute:()=>null, setAttribute(){}, clientWidth:560});
global.document = {getElementById: el, createElement: el, querySelectorAll:()=>[], querySelector:()=>null, addEventListener(){},
                   documentElement: el()};
global.matchMedia = () => ({matches:false});
global.fetch = () => Promise.reject(new Error("no network in tests"));   // RS35 carousel must not reach GitHub from CI
global.window = global;
const s = {};
new Function("document", "localStorage",
  code + "; this.keywordQueries=keywordQueries; this.rankByFit=rankByFit; this.fitScore=fitScore; this.whyRelevant=whyRelevant; this.esc=esc; this.lu=lu; this.freeText=freeText;" +
  " this.keep=keep; this.harmful=harmful; this.harmfulRepo=harmfulRepo; this.prdFeatures=prdFeatures; this.trendingQuery=trendingQuery; this.trendRows=trendRows; this.feedbackUrl=feedbackUrl; this.feedbackPayload=feedbackPayload; this.agoText=agoText; this.cardHtml=cardHtml;").call(s, document, global.localStorage || {getItem:()=>null,setItem(){},removeItem(){}});

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
// RS16a needs first, shell last (owner test: generic website templates crowded out voice + offline maps)
{ const kq = t => s.keywordQueries(t, "");
  assert.deepStrictEqual(kq("website with voice ai and show offline maps"), ["voice ai", "offline maps", "maplibre", "offline map tiles"]);
  assert.ok(!kq("website with voice ai and show offline maps").some(q => /template/.test(q)));
  assert.deepStrictEqual(kq("a landing page with a waitlist").slice(0, 2), ["landing page", "waitlist"]);   // lone word keeps its shell
  assert.ok(!kq("a diet and calorie tracking app").includes("diet"));                                       // bare word -> its expansions
  assert.ok(kq("a diet and calorie tracking app").includes("calorie counter"));
  assert.deepStrictEqual(kq("portfolio website builder"), ["portfolio website builder", "portfolio template", "portfolio website", "landing page template"]);   // single need unchanged
  kq("e-commerce store with stripe payments and admin dashboard").forEach(q => assert.ok(q.split(" ").length <= 3, q));
}
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
// RS5/RS24/RS37: a card says why only when the search words really match (honest keyword match, no filler line)
const w1 = s.whyRelevant({name:"me/rag-chat", desc:"A RAG chatbot over your PDFs", rel:0}, ["rag","chatbot","pdfs"]);
assert.strictEqual(w1, "Matches: rag, chatbot, pdfs");
assert.strictEqual(s.whyRelevant({name:"x/y", desc:"unrelated", rel:1}, ["zzz"]), "");
assert.strictEqual(s.whyRelevant({name:"x/y", desc:"unrelated", rel:9}, ["zzz"]), "");
// whole-word match: "ai" must NOT fire on "email"
assert.strictEqual(s.whyRelevant({name:"me/mailer", desc:"a fast email client", rel:0}, ["ai","chat"]), "");
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

// RS34b: the function's cached example list is exactly the page's quick-pick texts
{ const src = fs.readFileSync(path.join(__dirname, "..", "functions", "api", "relevance.js"), "utf8");
  const block = src.match(/EXAMPLE_QUERIES = \[([\s\S]*?)\];/)[1];
  const fnList = [...block.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map(m => m[1]);
  const pageList = [...html.match(/var EXAMPLES=\[([\s\S]*?)\];/)[1].matchAll(/text:"((?:[^"\\]|\\.)*)"/g)].map(m => m[1]);
  assert.deepStrictEqual(fnList, pageList);
  console.log("example list in sync"); }

// RS35 trending gallery: API-sorted queries, same filters as search, stars/forks order
{ const now = Date.UTC(2026, 9, 14);
  assert.deepStrictEqual(s.trendingQuery("rising", now), { q: "created:>=2026-09-14 stars:>50", sort: "stars" });
  assert.deepStrictEqual(s.trendingQuery("stars", now), { q: "stars:>10000", sort: "stars" });
  assert.deepStrictEqual(s.trendingQuery("forks", now), { q: "forks:>2000", sort: "forks" });
  assert.strictEqual(s.trendingQuery("nonsense", now).q.startsWith("created:>="), true);
  const fresh = new Date(Date.now() - 864e5).toISOString();
  const it = (n, st, fk, lic, extra) => Object.assign({ full_name: "o/" + n, stargazers_count: st, forks_count: fk, license: lic ? { spdx_id: lic } : null,
    pushed_at: fresh, description: n + " tool", html_url: "https://github.com/o/" + n, topics: [] }, extra || {});
  const items = [it("a", 100, 900, "MIT"), it("b", 5000, 10, "Apache-2.0"), it("c", 9000, 50, null), it("d", 300, 300, "MIT", { fork: true }),
                 it("e", 700, 5000, "GPL-3.0")];
  const st = s.trendRows(items, "stars"), fk = s.trendRows(items, "forks");
  assert.deepStrictEqual(st.rows.map(r => r.name), ["o/b", "o/e", "o/a"]);      // no licence and forks are filtered out
  assert.deepStrictEqual(fk.rows.map(r => r.name), ["o/e", "o/a", "o/b"]);
  assert.strictEqual(st.excluded.license, 1); assert.strictEqual(st.excluded.fork, 1);
  assert.match(fk.rows[0].whyText, /5\.0k forks/);
  console.log("trending ok"); }

// RS39 feedback: pre-filled email to Cardzo, user text only URL-encoded, empty title refused
{ assert.strictEqual(s.feedbackUrl("  ", "Bug", "x"), null);
  const u = s.feedbackUrl("Dark <mode> & more", "Feature request", "please\nthanks");
  assert.ok(u.startsWith("mailto:hello@cardzo.co.in?subject="));
  const q = new URLSearchParams(u.split("?")[1]);
  assert.strictEqual(q.get("subject"), "[Replore] [Feature request] Dark <mode> & more");
  assert.match(q.get("body"), /^Type: Feature request\n\nplease\nthanks/);
  assert.ok(!/[<>&\s]/.test(u.split("?")[1].replace(/&body=/, "")), "raw text leaked into the URL");
  assert.strictEqual(new URLSearchParams(s.feedbackUrl("t", "<script>", "").split("?")[1]).get("subject"), "[Replore] [Other] t");  // unknown type
  assert.strictEqual(new URLSearchParams(s.feedbackUrl("x".repeat(500), "Bug", "").split("?")[1]).get("subject").length, 16 + 120);
  assert.ok(s.feedbackUrl("t", "Bug", "y".repeat(5000)).length < 2000, "mailto stays short enough for mail clients");
  // Web3Forms payload: title required, type allowlisted, email kept only if address-shaped, honeypot false
  assert.strictEqual(s.feedbackPayload(" ", "Bug", "x", ""), null);
  const pl = s.feedbackPayload("Dark mode", "<x>", "d".repeat(3000), "not-an-email");
  assert.strictEqual(pl.subject, "[Replore] [Other] Dark mode"); assert.strictEqual(pl.message.length, 2000);
  assert.ok(!("email" in pl) && pl.botcheck === false && "access_key" in pl);
  assert.strictEqual(s.feedbackPayload("t", "Bug", "", "me@site.io").email, "me@site.io");
  console.log("feedback ok"); }

// RS24 result card: relative date, escaped repo text, topics filtered
{ assert.strictEqual(s.agoText(new Date(Date.now() - 3 * 864e5).toISOString()), "3 days ago");
  assert.strictEqual(s.agoText(""), "");
  const h = s.cardHtml({name:"ow<n>/re\"po", stars:1200, forks:30, spdx:"MIT", pushed:"2026-10-01", url:"https://github.com/a/b",
    desc:"<img src=x>", topics:["ok-topic","<bad>"], starter:false, rel:0}, 0, []);
  assert.ok(!h.includes("<img") && !h.includes("<bad>") && !h.includes("ow<n>"), "repo text must be escaped");
  assert.ok(h.includes("class=\"topics\"") && h.includes("top1") && h.includes("pick-cb"));   // fake DOM: esc() yields "" here, so check structure only
  console.log("card ok"); }
