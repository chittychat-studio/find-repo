# Replore

A Claude Code plugin. Describe your project in plain words and get the 10 most-starred
open-source GitHub repos that fit it, as a comparison table: stars, what it does, relevance, license,
whether you can use it in a paid product, whether it's completely free, and how to start.

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

The plugin answers with a comparison table of up to 10 repos. Ask for "as a sheet" to get CSV for Excel or Google Sheets.

**Got a PRD or spec?** Attach it (or paste it) and the plugin reads every feature, searches per feature, and
returns **all** the suitable open-source repos grouped by need — not just the top 10. "All suitable" means every
open-source match that passes the filters, not every repo on GitHub.

## Web page (no install)

A static page at `web/index.html` lets anyone type a project and see the top 10 repos in the browser — no
Claude, no Python. Deploy it free on GitHub Pages:

1. Settings → Pages → Source → **GitHub Actions**.
2. Push to `main` (the `pages` workflow deploys `web/`), or run the **pages** workflow by hand.
3. Open the URL the workflow prints.

It calls the public GitHub search API from the browser (about 10 searches a minute, no login, no key) and runs
the same filters, ranking and license labels as the plugin. It uses basic keyword search; AI-written queries
and the relevance check live in the Claude Code plugin — a public static page can't hold an API key, so the
AI step stays in the plugin.

## Install (Claude Code)

```
/plugin marketplace add chittychat-studio/find-repo
/plugin install replore@replore
```

Needs Python 3.11+ (the plugin tells you how to install it if it's missing). Once installed, it is available in every project.

## How it works (rules in `SPEC.md`)

1. Claude turns your description into 1–4 GitHub search queries (RS1).
2. `scripts/scout.py` runs them against the GitHub search API, sorted by stars, no forks, no archived repos (RS2).
3. It keeps only repos with an open-source license (RS3) that were pushed in the last 24 months (RS4).
4. Ranking is balanced (RS5): each search's best match comes first, then the rest by stars, so one broad
   search can't crowd out the others. Starting a new project? Starter templates go first (RS15).
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

## License

MIT. See `LICENSE`.
