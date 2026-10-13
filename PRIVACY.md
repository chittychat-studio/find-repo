# Privacy

*Last updated: 13 October 2026. This describes how Replore handles data as built. It is not legal advice.*

**Short version:** Replore has no account, no server, no database and no analytics. The people who make Replore
never receive your ideas, your searches or your plans. Your search words go from your own browser or computer
straight to GitHub so the search can run.

## Web page (replore.pages.dev)

| What | Where it goes | Why |
|---|---|---|
| Your search words (and words taken from a plan you upload) | **GitHub's API** (`api.github.com`), with your IP address | To run the search. GitHub's handling is covered by the [GitHub Privacy Statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). |
| Your IP address and browser details, when the page loads | **Cloudflare Pages** (hosts the page) | To deliver the page. It sees that you loaded the page, **not** what you search: searches are never put in the page address and never sent to it. Fonts and scripts are served from the same site — no request goes to Google Fonts or any other CDN. |
| Your last search, results and filters, and your light/dark choice | **Your browser only** (local storage on your device) | So a refresh brings your results back. Tap **✕** in the search bar or the Replore logo to delete it, or clear this site's data in your browser. |
| A plan / PRD file you upload | **Stays on your device.** It is read in your browser and never uploaded. Only short feature phrases taken from it are sent to GitHub as searches. | To search per feature. |
| The build-plan prompt, if you click **Open in Claude** | **claude.ai**, under your own Claude account | You choose to send it. **Copy** keeps it on your clipboard instead. |

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
