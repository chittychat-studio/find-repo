# Privacy

*Last updated: 14 October 2026 (wording: off-topic repos move down, not hidden; optional tips via Stripe; bot check switched on; feedback goes by email to Cardzo). This describes how Replore handles data as built. It is not legal advice.*

**Short version:** Replore has no account, no database and no visitor analytics, and stores nothing you type. The people who
make Replore never keep your ideas, searches or plans. Your search words go to GitHub to run the search and — on the
web page only — to an AI provider that checks which results fit. Nothing you type is kept by us; if the AI check fails, we
keep only the error type and time, to fix it.

## Web page (replore.cardzo.co.in, also replore.pages.dev)

| What | Where it goes | Why |
|---|---|---|
| Your search words (and words taken from a plan you upload) | **GitHub's API** (`api.github.com`), with your IP address | To run the search. The trending carousel and gallery also ask GitHub's API for popular repos (no words from you), at most once per list every 30 minutes. GitHub's handling is covered by the [GitHub Privacy Statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). |
| Your search words, and the names, descriptions and topics of up to 30 repos found | **Our relevance check** (a small Cloudflare Pages Function) → **Cloudflare Workers AI** (the AI that judges fit, run by Cloudflare, which also hosts this site), or, when that is unavailable or over its daily limit, **Groq** (the same check at another AI provider) | To move repos that don't fit what you're building to the end of the list, under "Less likely to fit". The function stores nothing you send. When a check fails, it records only the error type, how long it took and when — never your search words, the repos, your IP address or anything else you typed — so we can fix problems. Workers AI processes the request under [Cloudflare's privacy policy](https://www.cloudflare.com/privacypolicy/); Groq under [its own](https://groq.com/privacy-policy/). Cloudflare may keep standard request logs under its policy. We keep nothing you type. To avoid re-running the same check, the AI's answer (only which repos don't fit) is cached for an hour, keyed by a one-way fingerprint of the search and the repo list, never the words themselves; for our own built-in example searches, for up to a day. If the check is unavailable, you get the unfiltered keyword results instead. |
| Only when switched on (SPEC RS42): your search words and the same repo names, descriptions and topics | **Cloudflare Workers AI** embedding model (same provider as above), and for the repo index, **Cloudflare Vectorize** (which holds public repo names and descriptions only) | To rank repos by meaning as well as by matching words, and to suggest public repos the keyword search missed. Nothing you type is stored; every suggested repo is checked live on GitHub before it is shown. If this step fails, only an error code and how long it took are logged (SPEC RS42b), never your words. In the plugin this only happens if you add `--semantic`, which sends your project description to Replore's server for this one purpose; that plugin route has no bot check, so it stays off unless we switch it on separately. |
| Browser signals Cloudflare Turnstile uses to tell people from bots (the bot check is on) | **Cloudflare Turnstile** (`challenges.cloudflare.com`), loaded when you search | To stop automated scripts from using up the shared free AI allowance. It usually needs no click. Our function passes your IP address to Cloudflare's verification service along with the Turnstile token. Cloudflare handles it under its [privacy policy](https://www.cloudflare.com/privacypolicy/). |
| Your IP address and browser details, when the page loads | **Cloudflare Pages** (hosts the page) | To deliver the page. Loading the page doesn't reveal what you search: searches are never put in the page address. (The relevance check in the row above does send your search words to Cloudflare.) Fonts and scripts are served from the same site — no request goes to Google Fonts or any other CDN. |
| Your last search, results and filters, your light/dark choice, a 30-minute copy of the public trending lists, and — only when the AI check's daily allowance is used up — the time it resets | **Your browser only** (local storage on your device) | So a refresh brings your results back, the trending carousel doesn't re-ask GitHub on every visit, and the page doesn't retry the AI check before it resets. Tap **✕** in the search bar or the Replore logo to delete it, or clear this site's data in your browser. |
| A plan / PRD file you upload | **Stays on your device.** It is read in your browser and never uploaded. Only short feature phrases taken from it are sent to GitHub as searches. | To search per feature. |
| The build-plan prompt, if you click **Open in Claude** or **Open in ChatGPT** | **claude.ai** or **chatgpt.com**, under your own account | You choose to send it. **Copy** keeps it on your clipboard instead. |
| The build-plan prompt, if you click **Open in Gemini** | **Your clipboard**, then **gemini.google.com** opens; nothing is sent unless you paste it there | Gemini has no pre-fill link. |
| What you type in the **Feedback** form (title, type, message, and your email only if you add it), when you press **Send** | **Web3Forms** (`api.web3forms.com`, an email-forwarding service, with your IP address) → **hello@cardzo.co.in**. Web3Forms handles it under its own terms. If sending fails, the form offers your own email app instead. | So you can report bugs and suggest improvements, and so we can reply if you leave an address. |
| Nothing, unless you click **Tip** (next to ★ Star) or scan the tip QR code in the plan window | **Stripe** (`buy.stripe.com`) opens in a new tab. Anything you enter there (amount, card, email) goes to Stripe, not to Replore, and Stripe handles it under its [privacy policy](https://stripe.com/privacy). Cardzo sees the payment and what Stripe shares with merchants; Replore's page sends Stripe nothing. | So people who find Replore useful can choose to support it. Tipping is optional and unlocks nothing. |

The page contains no analytics, tracking pixels, ads or cookies set by Replore.

## Plugin, MCP server and script (on your computer)

- Everything runs on your own computer. Your search words go to **GitHub's API** (as above). Nothing is sent to us.
- Your AI agent and its AI provider (for example Anthropic, OpenAI or Google) process your conversation under
  **their own** terms. That is between you and them; Replore doesn't receive it.
- If you set `GITHUB_TOKEN`, it is sent only to GitHub and is never printed or logged.
- **Optional security log (Claude Code plugin only) — off by default.** Nothing from your prompts is stored unless
  you turn this on. If you set the environment variable `REPLORE_SECURITY_LOG` (to `1` for the default location, or
  to a file path), a safety hook checks each prompt you send in Claude Code while the plugin is enabled; when one
  matches a prompt-injection or harmful-request pattern, it writes one line — time, session id, which pattern
  matched, and the **first 200 characters** of that prompt — to `~/.replore/security.log` (or your path) **on your
  computer**. It is never sent anywhere. Unset the variable to stop; delete the file at any time. This log is an
  audit trail, not a protection: Replore's safety rules work the same whether it is on or off. The MCP server and
  the script never write it.

## Questions

Open an issue at [github.com/chittychat-studio/replore/issues](https://github.com/chittychat-studio/replore/issues).
If anything here changes, this page changes in the same release, with a new date.

**Saved on your device (SPEC RS43).** The web page keeps your last 10 searches and their results in your own browser's storage for one hour, so repeating a search is instant and uses no GitHub or AI calls. This never leaves your device. A "Search again" link always runs a fresh search.
