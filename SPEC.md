# Find Repo — Specification v0.1

Status: draft v0.1, 2026-10-12. Every line of code traces to a rule ID below.
Find Repo is a Claude Code plugin that returns the top 10 open-source GitHub repos for a described project. Moved out of chittychat-studio/Governance-manager
(where it was drafted as "Repo Scout", later named "Find Top Skill") into its own repository, so it ships and installs on its own.

## RS — Behaviour

- **RS1** Input is any free-text project description. The `/find-repo:find` skill, running in the
  user's own Claude Code session, turns it into 1–4 GitHub search queries (keywords, optionally
  `topic:` / `language:` qualifiers). The script never calls a model and holds no model API key.
- **RS1a** When the skill starts without a description (bare `/find-repo:find`, or a request that does not say
  what is being built), it asks the user one plain question about the project or task, and runs no search until
  they answer. The question also offers two optional preferences: language or stack, and whether unlicensed repos are OK.
- **RS2** "All public GitHub" means the GitHub REST search API (`GET /search/repositories`). Each query
  is sent with `sort=stars&order=desc&per_page=30`, and `fork:false archived:false is:public` is added.
  Results from all queries are merged and de-duplicated by `full_name`.
  Limit: the API searches name, description and topics and returns the 1,000 best matches per query at most. It does not scan every repository.
- **RS3** "Free" means the repository declares an open-source license: its `license.spdx_id` is in
  the `OPEN_LICENSES` set in `scripts/scout.py`. A missing license, `NOASSERTION` or a
  non-open license is excluded by default. With `--license any`, unlicensed repos are kept and
  flagged `no license: all rights reserved by default`.
- **RS4** Staleness filter: a repo whose last push is older than `--max-age-months` (default 24) is excluded.
  `--max-age-months 0` turns the filter off.
- **RS4a** Minimum stars: a repo with fewer than `--min-stars` stars (CLI and workflow default 50; 0 turns it
  off) is excluded and counted as `low_stars`. Reason: balanced ranking (RS5) gives every search a slot, and a
  live "diet app" run put 41- and 48-star repos in the top 3 ahead of one with 2,670.
Ranking. Default `--rank balanced`: every query's own matches are sorted by stars (ties: most
  recent push, then `full_name`). The final order then takes rounds: round 1 holds each query's best match,
  round 2 each query's second best, and so on; within a round, stars descending. So one broad query cannot
  fill the whole list and push out the others. `--rank stars` keeps the old order: stars descending across all
  queries. The script returns the top `--top` (default 10) plus a shortlist of `--candidates` (default 20), so
  the relevance gate (RS6) can drop repos and still have 10 left.
  A repo found by several queries is counted once, under the first query that returned it.
- **RS1b** Vague but usable input (e.g. "diet app"): the skill does not block on a question. It searches the
  domain (e.g. `diet tracker app`, `calorie counter`, `meal planner app`), says which platform it assumed or that
  it searched all, and offers one line to narrow it. It asks first only when there is no domain at all
  ("an app", "something cool", nonsense).
Relevance gate: stars measure popularity, not fit. The skill may only *drop* a shortlisted
  repo that clearly does not match the description, giving a one-line reason for each drop, and then
  take the next one in star order. It never reorders, never adds a repo that is not in the script
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
- **RS10** Output: a plain table for people, `--json` for machines, or `--markdown` for a job summary (RS13). Each row has rank, `full_name`, stars, license label (RS14), starter flag and start hint (RS15),
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
  answers with a comparison table of up to 10 repos with these columns: #, Repo, Stars, What it does, Relevance,
  License, OK in a paid product?, Completely free?, Starter?, Last update, How to start. "What it does" is taken
  from the description only. "Relevance" is High/Medium/Low with a short reason; it is the skill's judgment from
  the description and is labelled as such.
- **RS21** Prompt examples. The README lists example prompts by goal (website, mobile app, AI agent, data, games,
  learning) and a fill-in prompt template (What I'm building / Platform / Stack / Selling it? / Starting from
  scratch?). The skill reads the same five fields from whatever the user wrote, and asks only for the ones it
  needs per RS1a/RS1b.
- **RS11** Runtime: Python 3.11+ standard library only (`urllib`). No third-party packages.
  Unit tests make no network calls (HTTP is replaced with fixtures) and run in CI on every push and PR.
- **RS12** License: MIT, in `LICENSE`, declared as `"license": "MIT"` in `plugin.json`. GitHub then detects
  `MIT`, so the plugin passes its own RS3 filter.

## RX — Deliberately excluded (v0.1)

- **RX1** Scraping github.com HTML, or any non-API source.
- **RX2** Caching results on disk.
- **RX3** Ranking by anything other than stars (forks, trending, downloads).
- **RX4** Writing into the user's repo (cloning, adding dependencies). The output is a recommendation only.
