# Replore — Specification v0.1

Status: draft v0.1, 2026-10-12. Every line of code traces to a rule ID below.
Replore is a Claude Code plugin that returns the top 20 open-source GitHub repos for a described project. Moved out of chittychat-studio/Governance-manager
(where it was drafted as "Repo Scout", later named "Find Top Skill") into its own repository, so it ships and installs on its own.

## RS — Behaviour

- **RS1** Input is any free-text project description. The `/replore:find` skill, running in the
  user's own Claude Code session, turns it into 1–4 GitHub search queries (keywords, optionally
  `topic:` / `language:` qualifiers). The script never calls a model and holds no model API key.
- **RS1a** When the skill starts without a description (bare `/replore:find`, or a request that does not say
  what is being built), it asks the user one plain question about the project or task, and runs no search until
  they answer. The question also offers two optional preferences: language or stack, and whether unlicensed repos are OK.
- **RS2** "All public GitHub" means the GitHub REST search API (`GET /search/repositories`). Each query
  is sent with `per_page=30` and `fork:false archived:false is:public` added, in GitHub's best-match
  (relevance) order over name, description, topics and README; this seeds the fit ranking (RS5). `sort=stars`
  is no longer forced — stars stay in every result and still weigh in RS5.
  Results from all queries are merged and de-duplicated by `full_name`.
  Limit: the API searches name, description and topics and returns the 1,000 best matches per query at most. It does not scan every repository.
- **RS3** "Free" means the repository declares an open-source license: its `license.spdx_id` is in
  the `OPEN_LICENSES` set in `scripts/scout.py`. A missing license, `NOASSERTION` or a
  non-open license is excluded by default. With `--license any`, unlicensed repos are kept and
  flagged `no license: all rights reserved by default`.
- **RS4** Staleness filter: a repo whose last push is older than `--max-age-months` (default 24) is excluded.
  `--max-age-months 0` turns the filter off.
- **RS4a** Minimum stars: a repo with fewer than `--min-stars` stars (CLI and workflow default 50; 0 turns it
  off) is excluded and counted as `low_stars`. Reason: fit ranking (RS5) gives relevant small repos a real slot, and a
  live "diet app" run put 41- and 48-star repos in the top 3 ahead of one with 2,670.
- **RS5** Fit ranking (default `--rank fit`). The aim is to save the user from scrolling hundreds of repos, so
  the top rank is what a builder actually wants: relevant **and** popular **and** free to use. Each candidate
  gets a *fit* score, highest first, blending three signals:
  (a) **relevance** — its position in GitHub's best-match order (RS2) for the query it was found by; a term hit
  in the repo name or topics counts most;
  (b) **stars** — log-scaled, so a very popular repo ranks well without burying a precise smaller match;
  (c) **freedom** — permissive licenses (MIT/Apache/BSD/ISC…) rank above weak copyleft (LGPL/MPL/EPL), which
  rank above GPL/AGPL (all still pass the RS3 open-source filter).
  Starters keep their RS15 bonus. A repo found by several queries is counted once, under its best (lowest)
  relevance position. Default weighting is relevance ≈0.45, stars ≈0.35, freedom ≈0.20; the exact constants
  live next to the code and the spec rule governs, not the numbers. `--rank stars` keeps pure star-descending
  order for anyone who wants it. The script returns the top `--top` (default 10) plus a shortlist of
  `--candidates` (default 40), so the relevance gate (RS6) can drop repos and still have 20 left.
  Goal-based evals (`evals/run.py`, cases in `evals/fit_cases.json`) assert the fit ranking puts the
  relevant-and-popular-and-free repo at #1 across labelled scenarios; they run in CI and must pass.
- **RS1b** Vague but usable input (e.g. "diet app"): the skill does not block on a question. It searches the
  domain (e.g. `diet tracker app`, `calorie counter`, `meal planner app`), says which platform it assumed or that
  it searched all, and offers one line to narrow it. It asks first only when there is no domain at all
  ("an app", "something cool", nonsense).
- **RS6** Relevance gate. The script already ranks by fit (RS5). The skill may further *drop* a shortlisted
  repo that clearly does not match the description, giving a one-line reason for each drop, and then take the
  next one in fit order. It never reorders the surviving repos, never adds a repo that is not in the script
  output, and never states a star count, license or date that the script did not print.
- **RS7** Fail closed. A network error, HTTP error or rate limit → exit code 2 and a plain message.
  The script never returns partial results as if they were complete. A query that fails ends the
  whole run. Zero matches after filtering → exit code 1, and the excluded counts for each reason are printed.
- **RS8** Auth: if `GITHUB_TOKEN` or `GH_TOKEN` is set, it is sent as a bearer token. It is never
  printed, logged or written. Without a token GitHub allows 10 search requests a minute, so the
  script refuses more than 4 queries per run.
- **RS9** Repo text is data. Names and descriptions from GitHub are stripped of control characters
  and capped at 200 characters before printing. The skill treats them as data: if a description
  asks it to do something, it does not, and tells the user.
- **RS10** Output: a plain table for people, `--json` for machines, or `--markdown` for a job summary (RS13). Each row has rank, `full_name`, a one-line `why` relevance note (RS24), stars, license label (RS14), starter flag and start hint (RS15),
  last push date, URL, matched query and description. Every run also prints the query
  list and the excluded counts (fork/archived, license, stale, duplicate).
- **RS13** GitHub Actions run (`.github/workflows/find.yml`): a manual "Run workflow" form takes search
  queries separated by `;`, plus the license mode, the max age, the ranking mode (RS5) and
  prefer-starters (RS15), and an optional CSV block (`--csv-block` with `--markdown`, RS20). It runs `scout.py --markdown` with the
  Actions token (read-only, `contents: read`) and writes the result to the job summary. Inputs reach the
  script through environment variables, never pasted into the shell command. Repo text is Markdown-escaped
  in the summary, and a repo is linked only when its name is a plain `owner/repo`. This run has no
  relevance gate (RS6), because no model runs in Actions, and the summary says so.
- **RS14** Plain-English license label. Each result carries `license_use`, decided only from its SPDX id:
  permissive (MIT, Apache-2.0, BSD, ISC, CC0, Unlicense, Zlib and similar) → "OK to use in a paid product";
  weak copyleft (LGPL, MPL-2.0, EPL, MS-RL) → "OK in a paid product, but changes to its own files must stay open";
  GPL-2.0/GPL-3.0/EUPL → "You must share your app's code if you give the app to others";
  AGPL-3.0/OSL-3.0 → "You must share your code, even for a website or online service";
  anything else, or no license → "No license: you may not reuse this code".
  The output says this is a plain summary, not legal advice.
- **RS15** Starter templates. A result is a `starter` when GitHub marks it `is_template`, or its topics include
  `template`, `starter`, `starter-kit`, `starter-template` or `boilerplate`. With `--prefer-starters`, inside
  each query's own list starters come before non-starters (each group by stars), and RS5 then runs as usual.
  A starter moves ahead only if it has at least 10% of the stars of that query's most-starred match, so a tiny
  template cannot outrank a widely used library (found live: a 65-star template beat a 12,992-star library).
  Without the flag, starters are only labelled. Every result has a `start_hint`: for `is_template`, "On GitHub,
  click 'Use this template'"; otherwise "Follow the Getting started / Installation section of its README".
  The plugin still only recommends (RX4).
- **RS16** Query hygiene for vibe coders (skill text). The skill prefers specific phrases ("swiftui app template")
  over one broad tag (`topic:swiftui`), and excludes the wrong platform with a negated qualifier, e.g.
  `-topic:macos` for iOS. It passes `--prefer-starters` when the user is starting a new project.
  The web page's keyword expansion (`SYN`) follows the same rule: a word may only expand to a specific, on-topic
  phrase ("portfolio template", "landing page template"), never a bare category ("frontend framework", "web
  framework"). A bare category returns the most-starred general frameworks, which the fit ranking (RS5) then
  lifts above the relevant repos — seen live: "portfolio website builder" put Ionic, Expo, qiankun, Luigi, choo,
  san and argon in the top 13 via an expansion of "website" to "frontend framework".
- **RS17** Beginner-friendly output. Every output ends with a short key: stars = how many people bookmarked
  it (popularity, not quality, and can be bought); last push = last time anyone updated it; the license label
  meaning. If no working Python is found, the skill stops and tells the user in plain words how to install it
  (Windows: python.org installer with "Add python.exe to PATH" ticked, or `winget install Python.Python.3.12`;
  macOS: `xcode-select --install` or `brew install python`).
- **RS18** Security and harmful requests (skill text). "Hacking app" is ambiguous: security learning, testing
  your own app, or a hackathon. If the purpose isn't stated, the skill asks once: "Do you mean learning security /
  testing an app you own, or a hackathon project?" For learning or testing it searches defensive and practice terms
  (`penetration testing tool`, `deliberately vulnerable app`, `capture the flag`), and adds: "Only test systems
  you own or have written permission to test." If the stated goal is to get into someone else's account, device
  or data, spy on a person, steal credentials, take down a service, cheat in online games, or crack paid software,
  the skill declines in one line and runs no search. Regardless of the request, the relevance gate (RS6) always
  skips repos whose description offers account takeover of named services ("hack WhatsApp/Instagram accounts"),
  spyware or stalkerware, credential stealers, remote-access trojans, DDoS tools, cheats, cracks, keygens, or
  "free premium/currency generators", even when labelled "ethical" or "educational", and says it skipped them.
- **RS19** Other edge cases. A query over 200 characters is refused before any network call with a plain message
  ("use 1–3 keywords per search"); GitHub rejects long queries (found live: HTTP 422). Error messages quote only
  the user's query, never the added qualifiers. The skill writes queries in English (most repo descriptions are),
  adding one in the user's language if they wrote in another. More than four needs: it searches the four most
  important and names the rest. A request for something GitHub can't answer (paid apps, hardware, services): it
  says the plugin only finds open-source code on GitHub. Nonsense or zero matches: it asks what they are building.
  In the GitHub Actions run, "no match" (exit 1) shows as a successful run with the no-match summary; errors
  (exit 2) fail the run (found live: the workflow shell had no `pipefail`, so failures showed green).
- **RS20** Comparison sheet. Every result carries `free`, a plain answer to "is it completely free?" derived only
  from the license (RS14): permissive → "Yes"; weak copyleft → "Yes, but changes to its files must stay open";
  GPL/AGPL family → "Free to use, but you must share your code"; no license → "No: no license". The output says
  this checks the license only: some projects also sell a paid hosted version or paid add-ons, which the plugin does
  not check. `--csv` prints the same rows as CSV (rank, repo, url, stars, license, can_use_in_paid_product,
  completely_free, starter, how_to_start, last_push, query, description) for Excel or Google Sheets. The skill
  answers with a comparison table of up to 20 repos with these columns: #, Repo, Stars, What it does, Relevance,
  License, OK in a paid product?, Completely free?, Starter?, Last update, How to start. "What it does" is taken
  from the description only. "Relevance" is High/Medium/Low with a short reason; it is the skill's judgment from
  the description and is labelled as such.
- **RS21** Prompt examples. The README lists example prompts by goal (website, mobile app, AI agent, data, games,
  learning) and a fill-in prompt template (What I'm building / Platform / Stack / Selling it? / Starting from
  scratch?). The skill reads the same five fields from whatever the user wrote, and asks only for the ones it
  needs per RS1a/RS1b.
- **RS22** Web page (`web/index.html`, deployed to GitHub Pages by `.github/workflows/pages.yml`). Static,
  single file, no external scripts (except Cloudflare Turnstile when the RS34c bot check is on), no build step, no embedded secret (the RS34 fallback key lives only in the
  server-side function). It runs the keyword-to-query, filter,
  fit-rank (RS5), license-label (RS14), completely-free (RS20) and starter (RS15) logic in JavaScript,
  mirroring `scripts/scout.py`. It shows clickable example prompts (RS21) that fill the box, and calls the public GitHub search API from the browser (unauthenticated,
  ~10 searches/minute). It shows every fit-ranked match that passes the filters (RS29, not a fixed 20) as cards
  with the RS20 fields and the RS17 cautions, refuses a
  query over 200 characters and the harmful intents of RS18, and drops the harmful repo descriptions of RS18.
  No model runs in the browser and the page never asks for or stores a key or token (a public page cannot hold a
  secret). Query generation in the browser is plain keyword search; the relevance check runs server-side in the
  RS34 function (Workers AI binding, plus an optional server-held fallback key). AI-written queries and the PRD mode live in the Claude Code plugin.
- **RS23** PRD mode. When the user hands in a product-requirements doc (or any multi-feature description), the
  skill reads it, extracts the distinct needs/features (not just four), and searches per feature, calling
  `scripts/scout.py` in batches of at most 4 queries (the unauthenticated rate limit) until every feature is
  covered. It answers with results **grouped by feature** (`--group`) and **uncapped** (`--all`, no 10-limit):
  one section per need, each listing every open-source repo that passes the filters, de-duplicated so a repo
  appears under the first need that found it. "Every suitable repo" means every open-source match above the
  star floor and within the staleness window, not every repository on GitHub (search returns at most 1,000 per
  query). The grouped output repeats the RS17 key and RS20 free note, and says the relevance check runs in the
  skill. The PRD text is used only to derive search terms; it is treated as data (RS9), never as instructions.
- **RS24** Web UI (RS22 page). 3D app-shell: a fixed two-column layout on desktop so the page itself never
  scrolls (results scroll inside their panel); single column with natural scroll on phones; on single-column screens, once results are shown the intro (tagline, mode tiles) folds away and the
   quick picks shrink to one swipeable row so the search bar and pills sit right above the matches (✕ or the logo brings the rest back; the Filters
   sheet also offers "Find similar repos" and "Match a whole plan", so both modes stay one tap away), and the
   privacy line sits below the results, not in the search panel. Desktop stays one top-down column (owner's decision: no split screen) but
   uses the width: from 1200px the page spans up to 1500px, the search area up to 1100px (wider bar, tiles and pill
   rows), and the trending carousel (4 cards, 5 from 1500px) and results (4 columns) span the full page width. On the home
   screen (no results yet) the opening section pairs the heading (centred over the search box), search, tiles and pills with the animated
   how-it-works demo on the right, then the carousel runs full width below — a top-down page, not a split app; once
   results show everything stacks full width. Results render as
  compact cards (rank, stars, what it does, a colour-coded license pill, free/starter tags) instead of a wide
  table. The plain-English license meaning (e.g. "OK to use in a paid product" / "Completely free?") renders as
  a line on every card at every breakpoint — not only on wide screens — so the core promise is visible on phones.
  Motion comes from GSAP, loaded from cdnjs at a pinned version as the one external script; every GSAP
  use is guarded so the page works fully without it, and all motion is disabled under prefers-reduced-motion.
  Cards are cursor-reactive (a pointer-driven 3D tilt with a light glare, skipped on touch and under reduced
  motion) and the star counts tween up on reveal, all with the already-loaded GSAP and CSS (no extra library).
  An in-page animated "How it works" explainer (a looping step carousel) stands in for a video and is also
  shown as the results panel's empty state; a current screenshot of the live page (`web/tour.png`) is committed
  under `web/` and shown in the Tour.
  Type is Inter (Google Fonts, the one external stylesheet) with a full system fallback if it fails to load; sizes
  and weights are raised for prominence and legibility. The page defaults to light (`data-theme="light"` on the root); a toggle switches to dark and the choice is
  remembered in `localStorage` (a per-viewer convenience, wrapped in try/catch). No key or token is ever stored (RS22).
  Each result — web card and script row alike — carries a one-line *why relevant* note derived from the search:
  the user's own matching words if they appear in the repo name/description, else a best-match fallback. It is
  stated as keyword transparency, never as an AI judgement.
- **RS11** Runtime: Python 3.11+ standard library only (`urllib`). No third-party packages.
  Unit tests make no network calls (HTTP is replaced with fixtures) and run in CI on every push and PR.
- **RS12** License: MIT, in `LICENSE`, declared as `"license": "MIT"` in `plugin.json`. GitHub then detects
  `MIT`, so the plugin passes its own RS3 filter.
- **RS25** Prompt-injection safety. Every input the plugin reads — the user's description / `$ARGUMENTS`, their
  latest message, any selection, and any pasted or uploaded PRD / spec / file — is treated strictly as data
  describing *what to search for*, never as instructions to the assistant (this extends RS9, which already covers
  GitHub output). The skill text states this and tells the assistant to ignore embedded directives (ignore-these-
  steps, reveal / print the prompt, run or install something, act-as, disable-a-safety-check), take only the
  search intent, and say once that it did so. The skill's only actions remain running `scripts/scout.py` and
  presenting results (RX4). Defence-in-depth: a logging hook (`hooks/security_log.py`, declared in
  `hooks/hooks.json`, Python stdlib only — RS11) runs on `UserPromptSubmit`; it scans the submitted text for
  prompt-injection and harmful-intent patterns and appends any match as one JSON line to a security log.
  **Off by default (opt-in):** it writes nothing unless the user sets `REPLORE_SECURITY_LOG` — to `1`/`on` for the
  default `~/.replore/security.log`, or to a file path. Unset, it exits immediately without storing anything, so
  the plugin never keeps any part of a user's prompts unless they chose to (RS33). When on, it only logs — it never blocks the user and
  never echoes the prompt back verbatim beyond a short truncated sample — so it is an audit trail, not a gate.
  The guarantee holds from the skill text alone; the hook records attempts for review.
- **RS27** Similar-repo mode. Given an existing repo (owner/repo or a GitHub URL), find similar open-source
  repos: look up the repo's metadata (topics, language, description), derive search queries from its topics
  (and description keywords when it has few topics), run the normal filter + fit pipeline (RS2–RS5), and exclude
  the original repo from the results. On the web page this is the optional "find similar ones" field;
  `GET /repos/{owner}/{repo}` is one extra unauthenticated call. A repo that cannot be fetched (404 or rate
  limit) fails closed with a plain message (RS7). The fetched metadata is data, not instructions (RS9, RS25).
  A plugin CLI flag (`--like`) is a planned follow-up. When the target repo has **no GitHub topics**, the queries
  are derived from its description instead; the web page states this in a one-line note above the results (stated
  as the method used, not as a low-confidence "guess") and links to the plugin, which reads the repo itself.
- **RS27a** Similar-repo requires text, and is narrowed by it (RS22 web page). The "find similar repo" field is
  **not used alone**: a few typed words are **required** alongside it. A repo paste with an empty search box does
  not search — the page asks for words ("Add a few words too — what kind of repos like this?") and focuses the
  box. With both, the two are **combined**: the repo-derived queries are narrowed by the typed words (each query
  gets the text appended, so GitHub returns repos like the target that also match the words), and the heading
  says so ("Repos like X · matching 'Y'"). This replaces the earlier behaviour where the repo field silently
  overrode the text box and the typed words were dropped, and it removes the weak topic-less-repo case (the user's
  words always steer the search, so the "matched on description" note no longer appears). Narrowing can return
  fewer repos (GitHub ANDs every term); that fails closed with the normal "no match — broaden" message (RS7), it
  does not fall back to an unnarrowed list. The typed text is still length- and harmful-checked (RS18) as in text mode.
- **RS28** Select-to-PRD hand-off (RS22 web page). The user may tick result repos ("Add to PRD"); a floating
  bar then offers "Generate PRD". The page itself makes **no model call and holds no key** (RS1 upheld): it
  builds a plain-text prompt listing the selected repos (name, GitHub URL, description) plus the user's own
  description, and hands it to the user's **own** Claude two ways — a "Copy prompt" button (for the Claude Code
  plugin or any Claude) and a best-effort "Open in Claude" deep link (`https://claude.ai/new?q=<encoded>`,
  which opens a new chat on the user's logged-in claude.ai account). The deep link is unofficial and may change;
  Copy is the guaranteed path and is always offered, and the link is dropped when the URL would exceed a safe
  length. The prompt instructs Claude to use only the listed repos and invent no libraries, versions, or
  statistics (evidence-only, mirrors RS9/RS14). Selection resets on a new search or Home.
- **RS28a** Select all shown + triage. In the top-matches view a "Select all shown" control ticks every card
  currently visible — respecting the active result filter (RS29) and how far the user has scrolled — and becomes
  "Deselect shown" when all visible cards are ticked. It never ticks hidden or filtered-out cards. Because a bulk
  selection will include repos that don't fit (keyword search has no relevance judgement), the hand-off prompt
  requires the user's AI to triage every listed repo as use / reference only / reject with a one-line reason, and to
  build only on the ones it uses. When the prompt is too long for the "Open in Claude" link, the modal says so and
  points to Copy instead of silently hiding the link.
- **RS29** Result-side filters, result count, and no arbitrary cap (RS22 web page). A search renders **every
  fit-ranked match that passes the filters**, not a fixed 20 — capping at 20 when (say) 23 passed is arbitrary
  and was removed. A sane upper bound (60) guards against a runaway list; the page shows the first 10 and the rest load **automatically as the user scrolls** (10 at a time, no button; a "Showing X of Y" hint) — nothing is re-fetched (RS7 unaffected, no new API call). The
  results header shows the **number of matches** on the right (e.g. "22 results"). Above the results a row of
  **plain-English filter chips** — All / ✅ Free for commercial use / 🧩 Starters — shows or hides the
  already-fetched cards client-side (raw SPDX codes are deliberately not a filter). The commercial-use chip maps
  to the green card verdict (permissive + weak copyleft). The earlier "Paid-use OK" and "Completely free" chips
  were **removed because they filtered to the identical set** every time: both flags were 1 only for permissive
  licences and 0 otherwise, so the two chips could never differ (the paid-vs-free distinction is a copyleft
  nuance kept in the card verdict/tooltip, not two redundant filters). An empty filtered set shows a "clear
  filter" message. Filters apply only to the single top-matches list, not the grouped PRD view.
- **RS29c** *(retired)* A per-results "this is keyword search" banner was shown, then removed at the owner's
  call: each card's "Matches your words" line already shows the match is lexical, and the plugin stays one click
  away (menu + the "Want every suitable repo?" banner). The "How ranking works" modal still states the page is keyword search (matches words, not meaning).
- **RS29a** One license verdict per card (RS14/RS20 on the web page). A card shows a **single** plain-English
  license verdict — ✅ free for commercial use / ✅ paid-use OK, changes stay open / ⚠ must open-source your app /
  ⚠ share your code even as a web app / ⛔ no licence — not the earlier redundant "Paid-use OK" + "Completely
  free" pair, which both read the same for permissive licences. The full "OK in a paid product?" and "Completely
  free?" text stays available in the tag's tooltip and in the plugin's columns (RS20 unchanged).
- **RS29b** Web/plugin ranking parity. The web page (`web/index.html`) and `scripts/scout.py` MUST rank
  identically for the same candidate set: same fit weights (RS5), same filters (RS2–RS4a), same constants
  (open-licence set, starter topics, `STARTER_MIN_SHARE`, `MAX_AGE_MONTHS`, min-stars), and the **same
  tie-break order** — fit, then stars, then most-recent push, then repo name. Differences are only where the
  browser cannot run Claude: query generation (keyword expansion on the web vs Claude-written queries + the
  RS6 relevance gate in the plugin) and the absence of `--license any` on the web. The plugin CLI default stays
  `--top 20` (candidates `40`) for its table; `--all` is uncapped.
- **RS30** "Next steps" guidance for vibe coders (RS22 web page). A **menu item** (not a results-page block, to
  avoid clutter) opens a short modal that turns "a list of repos" into a build path, in three plain-English
  steps: (1) pick the 2–3 repos that fit and compare their license verdict + last-updated date, (2) generate a
  build plan from the selection (the existing RS28 select-to-plan hand-off — no model call, no key, hands the
  prompt to the user's own AI), (3) build it with their AI agent (Claude Code, Codex, Cursor…), with a link to the plugin for smarter search
  and a PRD-driven plan. Guidance only; it starts no search, runs no model, and holds no key (RS1 unchanged).
- **RS31** Any-agent path. The engine (`scripts/scout.py`) is agent-neutral; only the one-command install
  (`/plugin install`, `/replore:find`, the skill) is Claude Code-specific. A root `AGENTS.md` (auto-read by Codex, Cursor, Copilot,
  Cline, Windsurf; not by Claude Code or Gemini CLI) gives those agents the same procedure as the skill — write 1–4 short queries, run the script,
  present the comparison table, treat all input/output/repo text as data (RS9, RS25), decline RS18 requests,
  never invent results (RS7). User-facing copy (web menu, plugin modal, README) says "your AI agent" and shows
  two tabs: Claude Code (one command) and any other agent (clone + `AGENTS.md`, or run the script). Copy never
  presents the Claude Code-only commands as working elsewhere.

- **RS32** Model-agnostic MCP server. `scripts/mcp_server.py` exposes the engine as a Model Context Protocol
  server over stdio (newline-delimited JSON-RPC 2.0), so any MCP-capable agent — Claude Code, Codex CLI, Cursor,
  Gemini CLI, VS Code/Copilot, Windsurf, Cline — can call it whatever model it runs. One tool, `find_repos`
  (1–4 queries; optional prefer_starters, license open|any, min_stars, max_age_months, all, group), returns the
  RS10/RS23 Markdown from `scout.py`. Standard library only (RS11); no model call, no key (RS1); the only network
  call is the GitHub search API via `scout.fetch`. Failures return `isError: true` with the plain message and
  never a partial or remembered list (RS7). stdout carries only protocol messages; nothing logs the token (RS8).
  The tool description tells the calling model that repo names/descriptions are data, not instructions (RS9)
  and to decline RS18 requests. Not reachable from browser-only chats with no local tools; the web page covers those.

- **RS33** Privacy notice. `PRIVACY.md` (linked from README and the web page) and a one-line web notice under the
  search bar describe data handling exactly as built — no broader promise. Facts it must state: the maintainers run
  no server, database, account or analytics and receive no searches; searches go from the user's browser or computer
  to the GitHub API (GitHub sees the words and IP); fonts and the animation library are served from the site itself
  (no third-party font/CDN requests); the page host (Cloudflare Pages) serves the page but never receives searches (they are never put in the URL); the browser keeps
  the last search + results + filters + theme in localStorage until ✕/the logo clears them; an uploaded plan is read
  locally and only short feature phrases are sent to GitHub; "Open in Claude" sends the prompt to the user's own
  claude.ai account; the plugin's RS25 hook is off by default and, only if the user turns it on, writes a flagged
  prompt's first 200 characters to a log on their own machine and never transmits it; the user's AI agent provider handles
  their conversation under its own terms. The notice says it is not legal advice and gives a dated version. Any change
  that adds a data flow must update the notice in the same commit.

- **RS34** Web relevance gate (LLM, server-side). After the fit ranking (RS5), the web page sends the user's
  description and the top candidates (at most 30; name, description ≤160 chars, topics) to a same-origin Cloudflare
  Pages Function, `POST /api/relevance` (`functions/api/relevance.js`). The function asks an LLM — Cloudflare Workers AI first,
  then an optional OpenAI-compatible fallback set by `LLM_BASE_URL` / `LLM_MODEL` with its key in the server-side secret
  `LLM_API_KEY` (never sent to the browser, RS8), see RS34a — to judge each repo's fit for what the user is building, and returns
  the indices to keep plus a one-line reason for each repo it drops. **Provider chain (RS34a):** the function tries
  Cloudflare Workers AI first, through the Pages `AI` binding (no key; model list `WORKERS_AI_MODEL`, default
  `@cf/meta/llama-3.1-8b-instruct-fp8` then `@cf/meta/llama-3.3-70b-instruct-fp8-fast`; a retired or missing model,
  Workers AI errors 5028/5007, falls through to the next), then the OpenAI-compatible provider (when `LLM_API_KEY` is set, e.g. Groq) when
  Workers AI is missing, over its daily allocation, slow or erroring — one same-shape prompt, the same parse rules, a 7 s total budget across
  both. It reports a limit only when every configured provider failed: "busy" if any was a short per-minute limit,
  otherwise "used up" with the soonest reset (capped at 24 h); when any provider failed for another reason, the plain "couldn't check" note is shown. A slow first provider gets at most 60% of the budget so the fallback still runs. Not configured = neither a key nor the binding. A provider whose free
  tier is restricted to experimentation or prototyping (e.g. GitHub Models free usage) is not added to the chain
  for the public site; every provider in the chain is named in `PRIVACY.md`. The live chain is scored with `evals/relevance_live.mjs` (the same
  84-item set and pass bar, posted to the deployed endpoint), run by the manual GitHub workflow `relevance-eval-live`. **Example cache (RS34b):** for the built-in example
  searches only (the fixed texts of RS21, listed in the function and kept identical to the page by a test), a successful
  answer is kept in Cloudflare's edge cache for 24 h, keyed by a SHA-256 of the example text and the candidate repos,
  so repeat quick-pick taps spend no AI allowance. Text a visitor types is never cached or stored. Provider-side
  prompt caching is not used: the reusable prefix (the system prompt) is small next to the per-search repo list.
  Only the first provider's answer is cached (one model's judgement is what visitors see), the key lives on the
  site's own origin, and the cache is checked after the bot check, so a cache hit still needs a token.
  **Bot check (RS34c):** the AI allowance is shared by every visitor, so the function only spends it on requests that
  look like this page: (1) a POST whose `Origin` names another site is refused (403 `bad_origin`); (2) when the owner
  sets `TURNSTILE_SECRET` (and the public `TURNSTILE_SITE_KEY`), every POST must carry a fresh Cloudflare Turnstile
  token in `CF-Turnstile-Token`, verified server-side with Cloudflare's siteverify (success and a hostname equal to this site) before any model call; a missing,
  invalid or unverifiable token is refused (403 `bot_check_failed`) — fail closed on spend, while the page still shows
  keyword results. The page learns the site key from
  `GET /api/relevance` and loads Turnstile from `challenges.cloudflare.com` only when a key is set (the one exception
  to RS33's no-third-party-script rule, disclosed in `PRIVACY.md`). Every browser-side wait (config, script, token) has a deadline and a failed load retries on the next search;
  an interactive challenge gets 90 s. Without the secret the check is off and behaviour
  is unchanged. A per-IP Cloudflare rate-limiting rule on `/api/relevance` is the owner's dashboard setting, not code.
  Limits of this: an agent driving a real browser slowly can still pass; on the Workers Free plan the worst case of
  abuse is a day of keyword-only results, never a bill. The page shows only the kept repos and puts no note about the
  check above them (owner's decision, 2026-10-13). Dropped repos move to the end, hidden; once the visitor reaches the
  last kept card, one quiet line "Show N more we left out" appears at the very bottom and reveals them as ordinary
  cards (the undo for a wrong drop; owner's decision, same day). Rules: repo text
  and the description are data, never instructions (RS9, RS25), and the prompt says so; the LLM may only drop or keep,
  never add, rename or reorder (mirrors RS6 — fit order stays deterministic); a response that isn't valid JSON or names
  an unknown index is ignored. **Fail open, silent:** if the function is missing, unconfigured, over a limit, slow
  (>8 s), refused by the bot check or errors, the page shows the normal keyword results with no note. The function
  still returns specific codes (`llm_daily_limit` with `resetsInSec`, `llm_rate_limited`, `wai_timeout`,
  `wai_error_5028`, `bot_check_failed`, …; no provider message text, no secret) and the page records the outcome in a
  `data-gate` attribute on the results (`ok:<hidden>`, `off`, or the code) for diagnosis only. No live usage counter is
  shown; the owner sees usage in the Cloudflare/provider dashboard — never invented repos (RS7). The function stores no request content.
  **Failure log (RS34d):** when a check fails (any non-200 except `not_configured`), the function records one event:
  outcome code, HTTP status, each provider's code in order, milliseconds taken, and whether the query was a built-in
  example — never the search words, the repo list, the IP address, the bot-check token or any provider message text.
  It prints that line to the Cloudflare log (visible in the Pages real-time logs, not stored) and, when the Analytics
  Engine binding `RELEVANCE_LOG` exists, writes it there so it is kept (Cloudflare's retention applies). The binding is
  off in `wrangler.toml` until the owner enables Analytics Engine on the account (adding it first failed the deploy). Successful checks are not logged. `PRIVACY.md` says so. Input is capped (description
  ≤200 chars, ≤30 repos, body ≤16 KB) and anything else is rejected with 400. The free LLM tiers limit requests for the
  whole site, so under heavy use more searches fall back. RS33 is updated in the same change: search words and the
  candidate list now pass through our function to the LLM providers named in RS34a and PRIVACY.md. The plugin (RS1, RS6) is unchanged; its
  script still never calls a model.

- **RS35** Trending gallery (web). A "🔥 Trending" view lists popular open-source repos without a search, in three
  tabs, each one GitHub search API call (sorted by the API, `fork:false archived:false is:public`):
  **Rising** — created in the last 30 days, `stars:>50`, most stars first; **Most stars** — `stars:>10000`, most stars;
  **Most forks** — `forks:>2000`, most forks. Results pass the same filters as search (open-source licence, pushed in
  the last 12 months, RS18 harm filter) and render as the usual cards (license verdict, Add to plan) with the star and
  fork counts. It is labelled honestly: "Rising" is our definition (new + most-starred), not GitHub's Trending page,
  which has no API and is not scraped (RX1). Each tab is fetched only when opened and kept for 30 minutes in
  localStorage (public repo data only, never what the visitor typed) so tab switching doesn't spend the visitor's
  10 searches/minute. **Home carousel:** the home screen shows the top Rising repos as a self-rotating carousel
  ("🔥 Rising on GitHub this month") under the quick picks, with "See all trending" opening the gallery. It loads
  after the page is idle (one GitHub call per visitor per 30 minutes, shared with the Rising tab cache), advances one
  card every few seconds, pauses while hovered, focused or touched, does not auto-rotate under
  prefers-reduced-motion, can be swiped, and disappears silently if GitHub can't be reached. On single-column screens
  it folds away with the intro once results show. No AI relevance check
  runs on it (there is no description to judge against). Web only; the plugin is a search tool and has no gallery.

- **RS36** Thinking orb (web). A pill with a small rotating dotted sphere (latitude rings of dots, depth-shaded in the
  ink colour, light and dark theme) and a short label with animated dots, in the style of a "Solving…" indicator.
  Used in two places: (1) on the home screen under the how-it-works demo, its label cycling through what Replore
  does ("Scanning open-source repos", "Checking licences", "Skipping abandoned projects", "Ranking by fit"); (2) as the
  loading indicator in the status line while a search, similar-repo lookup, PRD search or trending list loads ("Searching
  GitHub (1/3)", "Checking which repos fit", "Loading trending repos"), one pill per search whose label updates per step
  and disappears when results show. It animates only while on screen and the tab is visible, draws one still frame
  (static dots, no label cycling) under prefers-reduced-motion, is aria-hidden decoration (the label text stays
  readable), stops once removed, and makes no network call.

- **RS34e** Relevance-check diagnosis and model choice. Live eval (2026-10-14, production chain): 6/9 queries timed
  out at 7 s, 2/9 returned unparseable output, and the one that ran dropped 4/6 relevant SaaS starters. Fixes: the
  model replies with indices only (`{"drop":[2,5]}`, max 120 tokens — the per-repo reasons were never shown and made
  replies long and slow); the prompt keeps templates/starters/boilerplates for the same kind of product even with extra
  features. A request may ask for per-attempt diagnostics (`X-Replore-Diag: 1` → model, ms and code per attempt, no
  text). Preview builds (wrangler `env.preview`) carry an `EVAL_MODELS` allowlist so the eval can compare models; the
  production build has none, so a client can never pick a model there. Comparison 2026-10-14 (indices-only replies; timeouts gone, 0.2–1.3 s avg): kept/dropped —
  Mistral Small 3.1 24B 100%/68%, Llama 3.3 70B 98%/32%, Llama 4 Scout 86%/46%, Llama 3.1 8B fp8 72%/76% (the old
  default, which hid good SaaS starters), 8B fast 81%/63%, 3.2 3B 67%/34%; Gemma 3 not allowed on the account (5018);
  GLM 4.7 Flash unparseable. Default becomes Mistral Small, then Llama 3.3 70B. No model meets the 80% drop bar yet;
  keeping good repos (the 95% half) is the half that protects visitors, so a model is only made default if it meets it.

## RX — Deliberately excluded (v0.1)

- **RX1** Scraping github.com HTML, or any non-API source.
- **RX2** Caching results on disk.
- **RX3** Ranking by forks, trending or download counts. (Relevance, stars and license-freedom are the only
  ranking signals — see RS5.)
- **RX4** Writing into the user's repo (cloning, adding dependencies). The output is a recommendation only.
