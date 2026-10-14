# Replore

A repo finder for your AI coding agent — a one-command plugin for **Claude Code**, and an MCP server for
**Codex, Cursor, Gemini CLI, Copilot, Windsurf, Cline or any other agent** ([setup](#use-in-any-other-ai-agent)). Describe your project in plain words and get the open-source GitHub repos that
**best fit** it — ranked by relevance, popularity, and how freely you can use the license — as a comparison
table: stars, what it does, relevance, license, whether you can use it in a paid product, whether it's
completely free, and how to start.

```
/replore:find a portfolio website with smooth scroll animations and good design taste
```

## Example prompts

Type `/replore:find` followed by what you're building. Plain English is fine.

- **Website:** `/replore:find a portfolio website with smooth scroll animations, starting from scratch`
- **Website:** `/replore:find landing page for my SaaS in Next.js, I'll sell it`
- **Mobile app:** `/replore:find my first iPhone app, a habit tracker, no coding experience`
- **Mobile app:** `/replore:find diet app for Android and iPhone`
- **AI agent:** `/replore:find a chatbot that answers questions from my PDFs, Python`
- **AI agent:** `/replore:find generate PowerPoint decks from my notes`
- **Data:** `/replore:find dashboard to show my sales spreadsheet as charts`
- **Games:** `/replore:find a simple 2D browser game engine for beginners`
- **Learning:** `/replore:find learn web security by hacking a practice app`
- **Learning:** `/replore:find offline maps for my trip planner app`

## Prompt template

Copy, fill in what you know, delete the rest. Only the first line is needed.

```
/replore:find
What I'm building: <one sentence>
Platform: <web / iPhone / Android / desktop / not sure>
Stack: <React, Python, Swift... or not sure>
Selling it?: <yes / no>
Starting from scratch?: <yes / no>
```

The plugin answers with a comparison table of up to 20 repos. Ask for "as a sheet" to get CSV for Excel or Google Sheets.

**Got a PRD or spec?** Attach it (or paste it) and the plugin reads every feature, searches per feature, and
returns **all** the suitable open-source repos grouped by need — not just the top 20. "All suitable" means every
open-source match that passes the filters, not every repo on GitHub.

## Web page (no install)

**Try it live: [replore.cardzo.co.in](https://replore.cardzo.co.in)** — type a project and see the top repos in your
browser, no Claude and no Python needed.

A static page at `web/index.html` powers it. It auto-deploys (Cloudflare Pages) to [replore.cardzo.co.in](https://replore.cardzo.co.in)
(Cloudflare Pages) on every push to `main`. To self-host it elsewhere, it also deploys free on GitHub Pages:

1. Settings → Pages → Source → **GitHub Actions**.
2. Push to `main` (the `pages` workflow deploys `web/`), or run the **pages** workflow by hand.
3. Open the URL the workflow prints.

It calls the public GitHub search API from the browser (about 10 searches a minute, no login, no key) and runs
the same filters, ranking and license labels as the plugin. The searches are keyword-based; then a small server-side
**relevance check** (`functions/api/relevance.js`, SPEC RS34) asks an AI which of the top 30 repos don't fit what you
described, and moves them to the end under a "Less likely to fit" divider. If the check is unavailable or over its free limit, you get the plain keyword
results. The page shows no note either way; the outcome is in the results' `data-gate` attribute for debugging.
Failed checks are logged as codes and timings only (SPEC RS34d) to the Cloudflare log (Pages → your project → the
deployment → Functions → Real-time logs; live only, not stored). To keep them, enable Workers Analytics Engine on the
account, then uncomment the `[[analytics_engine_datasets]]` block in `wrangler.toml`. AI-written searches and the feature-by-feature PRD mode live in the plugin.

**How the relevance check runs (maintainer, SPEC RS34a):** `wrangler.toml` binds Cloudflare Workers AI as `AI`, so
the check works on deploy with no key (optional variable `WORKERS_AI_MODEL`, comma-separated; default `@cf/meta/llama-3.1-8b-instruct-fp8`, then `@cf/meta/llama-3.3-70b-instruct-fp8-fast` if Cloudflare has retired the first).
Keep the account on the Workers **Free** plan if you want it to stop at the daily free allocation rather than bill.
**Optional fallback** for when Workers AI is over its allocation or failing: in Cloudflare → your Pages project →
Settings → Variables and Secrets, add a **secret** `LLM_API_KEY` (e.g. a free Groq API key from console.groq.com) and
redeploy; optional `LLM_BASE_URL` (any OpenAI-compatible endpoint; default Groq) and `LLM_MODEL` (default
`llama-3.1-8b-instant`). With neither the binding nor the key, the page shows plain keyword results with no note.
**Bot check (SPEC RS34c, recommended):** in Cloudflare → Turnstile, add a widget for your site's hostname
(Invisible or Managed), then in the Pages project add the variable `TURNSTILE_SITE_KEY` (public) and the **secret**
`TURNSTILE_SECRET`, and redeploy. Every AI check then needs a fresh Turnstile token. Also add a rate-limiting rule
(Security → WAF → Rate limiting rules) on the path `/api/relevance`, per IP. On the Free plan, the worst that
abuse can do is use up the day's allowance, never bill you.
Before adding or switching a provider, check its data-use terms (free tiers intended for prototyping, such as GitHub
Models, don't qualify) and update `PRIVACY.md`.

## Install (Claude Code)

```
/plugin marketplace add chittychat-studio/replore
/plugin install replore@replore
```

Needs Python 3.11+ (the plugin tells you how to install it if it's missing). Once installed, it is available in every project.

## Use in any other AI agent

Replore is model-agnostic. The `/plugin install` command above is Claude Code-only; every other agent loads the
same engine through **MCP** (Model Context Protocol), the open tool-connection standard Codex, Cursor, Gemini CLI,
VS Code Copilot, Windsurf and Cline all support — whatever model they run. No API key.

**1. Get Replore.** Needs Python 3.11+ and git (no git? on GitHub click **Code → Download ZIP** and unzip). On
Windows, type `python` wherever this says `python3`.

```
git clone https://github.com/chittychat-studio/replore
cd replore
pwd          # Windows: cd     — prints the full path; use it in place of /path/to/replore below
```

**2. Add the `replore` entry to your agent's MCP config.** If the file already exists, add only the `"replore": {…}`
entry inside its existing `mcpServers` block (VS Code: `servers`) — don't paste a second `{…}` or replace the file.
Then restart the agent.

| Agent | File | Entry |
|---|---|---|
| Codex CLI | `~/.codex/config.toml` | `[mcp_servers.replore]`<br>`command = "python3"`<br>`args = ["/path/to/replore/scripts/mcp_server.py"]` |
| Cursor | `~/.cursor/mcp.json` | `"mcpServers": {"replore": {"command": "python3", "args": ["/path/to/replore/scripts/mcp_server.py"]}}` |
| Gemini CLI | `~/.gemini/settings.json` | same `mcpServers` entry as Cursor |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | same `mcpServers` entry as Cursor |
| Cline | Cline panel → **MCP Servers** → **Configure** (opens `cline_mcp_settings.json`) | same `mcpServers` entry as Cursor |
| VS Code (Copilot) | `.vscode/mcp.json` in each project (or **MCP: Add Server** in the command palette) | `"servers": {"replore": {"type": "stdio", "command": "python3", "args": ["/path/to/replore/scripts/mcp_server.py"]}}` |
| Claude Code (MCP instead of the plugin) | terminal | `claude mcp add --scope user replore -- python3 /path/to/replore/scripts/mcp_server.py` |

These are each agent's documented MCP locations at the time of writing; if one has moved, check that agent's MCP
docs — the command and argument stay the same.

**3. Ask your agent** — *"find repos for a diet app for iPhone"*. It calls Replore's `find_repos` tool and shows the
comparison table. Your AI writes the searches and judges which results fit; the feature-by-feature PRD mode is in the
Claude Code plugin.

**No MCP support?** Open the cloned folder in your agent. Codex, Cursor, Copilot, Cline and Windsurf read
[`AGENTS.md`](AGENTS.md) automatically; with any other agent, say *"follow AGENTS.md"*. It then runs
`scripts/scout.py` itself. Or run it by hand:

```
python3 scripts/scout.py "diet tracker app" "calorie counter" --markdown
```

Same filters, ranking and license labels in every path. Browser-only chats with no local tools can't run it — use
the [web page](https://replore.cardzo.co.in) there.

## Hybrid search (RAG): built, switched off

Replore can rank repos by meaning as well as by your words, and pull in repos from its own index that GitHub's
keyword search misses. Every indexed repo is checked live on GitHub before it is shown. The web page and the plugin
work the same way (plugin: `--rank hybrid`, opt-in `--semantic`). It stays off until tests show it beats the current
results, and the site only mentions it while it is on. Details: [`docs/RAG.md`](docs/RAG.md).

## How it works (rules in `SPEC.md`)

1. Claude turns your description into 1–4 GitHub search queries (RS1).
2. `scripts/scout.py` runs them against the GitHub search API in best-match (relevance) order, no forks, no
   archived repos (RS2).
3. It keeps only repos with an open-source license (RS3) that were pushed in the last 24 months (RS4).
4. Ranking is by **fit** (RS5): a composite of relevance, popularity (stars) and license-freedom, so the top
   repo is relevant *and* popular *and* free to use — not just the most-starred. Starting a new project?
   Starter templates get a boost (RS15). (`--rank stars` or `--rank balanced` change it.)
5. Claude may drop off-topic repos from the shortlist, giving a reason, but never reorders the list or adds repos (RS6).
6. Every result says in plain words whether you can use it in a paid product (RS14) and how to start (RS15).

## Run it on GitHub (no install)

Repo → Actions → **find** → Run workflow. Type searches separated by `;`. Results appear on the run's summary
page. This version has no relevance check: Claude only runs inside Claude Code.

## Limits

- Repos under 50 stars are skipped by default (`--min-stars 0` keeps them).
- Vague asks ("diet app") get a search plus an offer to narrow; "hacking" asks get one question about the purpose,
  and the plugin won't find tools for getting into other people's accounts, spying, cheats or cracks (SPEC RS18).

- This is GitHub search, not a scan of every repository. Stars measure popularity, not quality.
- Repos with no license file are excluded by default. `--license any` keeps them, flagged "all rights reserved".
- Without a token GitHub allows 10 searches a minute. Set `GITHUB_TOKEN` to raise it; the token is never printed.

## Direct use

```
python3 scripts/scout.py "animation library" "topic:css-framework" [--json | --markdown | --csv] [--license any]
    [--max-age-months 12] [--rank balanced|stars] [--prefer-starters]
```

Exit codes: 0 results, 1 no match after filtering, 2 error (network, rate limit, bad query).

## Development

```
pip install -r requirements-dev.txt
python3 -m pytest
```

## Privacy

No account, no database, no analytics, nothing stored: the makers of Replore never keep your ideas or searches.
Search words go to GitHub to run the search; on the web page they also pass through a small relevance check to an AI
provider (Cloudflare Workers AI, with Groq as fallback) that hides off-topic repos. Fonts and scripts are served from the site itself. The plugin never uses
the relevance check. Details — including what the web page keeps in your browser and the plugin's optional,
off-by-default local safety log — are in [`PRIVACY.md`](PRIVACY.md).

## License

MIT. See `LICENSE`.
