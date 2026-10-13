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
  code + "; this.keywordQueries=keywordQueries; this.balanced=balanced; this.lu=lu; this.freeText=freeText;" +
  " this.keep=keep; this.harmful=harmful; this.harmfulRepo=harmfulRepo; this.prdFeatures=prdFeatures;").call(s, document, global.localStorage || {getItem:()=>null,setItem(){},removeItem(){}});

// RS16: iOS excludes macOS
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
// RS4a/RS3/RS4 filters + RS5 balanced with starter floor
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
assert.deepStrictEqual(s.balanced([k1, k2], true).map(r => r.name), ["b/x", "a/tpl", "a/big"]);
console.log("web logic ok");

// RS23: PRD feature extraction (client-side, capped for the rate limit)
const prd = ["# My app PRD","## Features","- User authentication with email and Google",
 "- Payment checkout with Stripe","- Push notifications","* Image upload and cropping",
 "The app must support offline mode","1) Admin dashboard with charts","random prose line here"].join("\n");
const f = s.prdFeatures(prd);
assert.ok(f.length >= 2 && f.length <= 6, "features: " + f.length);
assert.ok(f.some(x => x.includes("authentication")) && f.some(x => x.includes("payment")), f.join(" | "));
console.log("prd ok:", f.join(" | "));
