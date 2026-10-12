# Find Repo

A Claude Code plugin. Describe your project in plain words and get the 3 most-starred
open-source GitHub repos that fit it, with license and last-push date.

```
/find-repo:find a portfolio website with smooth scroll animations and good design taste
```

## Install (Claude Code)

```
/plugin marketplace add chittychat-studio/find-repo
/plugin install find-repo@find-repo
```

Needs Python 3.11+. Once installed, it is available in every project.

## How it works (rules in `SPEC.md`)

1. Claude turns your description into 1–4 GitHub search queries (RS1).
2. `scripts/scout.py` runs them against the GitHub search API, sorted by stars, no forks, no archived repos (RS2).
3. It keeps only repos with an open-source license (RS3) that were pushed in the last 24 months (RS4), then ranks by stars (RS5).
4. Claude may drop off-topic repos from the shortlist, giving a reason, but never reorders the list or adds repos (RS6).

## Limits

- This is GitHub search, not a scan of every repository. Stars measure popularity, not quality.
- Repos with no license file are excluded by default. `--license any` keeps them, flagged "all rights reserved".
- Without a token GitHub allows 10 searches a minute. Set `GITHUB_TOKEN` to raise it; the token is never printed.

## Direct use

```
python3 scripts/scout.py "animation library" "topic:css-framework" [--json] [--license any] [--max-age-months 12]
```

Exit codes: 0 results, 1 no match after filtering, 2 error (network, rate limit, bad query).

## Development

```
pip install -r requirements-dev.txt
python3 -m pytest
```

## License

MIT. See `LICENSE`.
