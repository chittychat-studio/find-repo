#!/usr/bin/env python3
"""Find Repo security logging hook (SPEC RS25).

A Claude Code `UserPromptSubmit` hook. It reads the hook event JSON from stdin, scans the
submitted prompt for prompt-injection and harmful-intent patterns, and appends any match as
one JSON line to a security log. It ONLY logs — it never blocks the user and never prints the
prompt back (it stores a short truncated sample for audit). It is defence-in-depth behind the
skill's own rule that all user input is data, not instructions (RS25); the plugin is safe
without it.

Python standard library only (RS11). Fail-safe: any error is swallowed and the hook exits 0,
so a logging problem can never break the user's session.

Log location: $FIND_REPO_SECURITY_LOG, else ~/.find-repo/security.log.
"""
import datetime as dt
import json
import os
import re
import sys

# Attempts to override the assistant's instructions (prompt injection / jailbreak).
INJECTION = {
    "ignore-instructions": r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|prior|earlier|all|your|these)\b.{0,20}\b(instruction|instructions|rule|rules|prompt|context)\b",
    "reveal-prompt": r"\b(reveal|show|print|repeat|output|expose)\b.{0,30}\b(system )?(prompt|instructions)\b",
    "system-prompt": r"\bsystem prompt\b",
    "role-override": r"\b(you are now|act as|pretend (to be|you are)|roleplay as|from now on you)\b",
    "mode-jailbreak": r"\b(developer mode|jailbreak|do anything now|\bDAN\b|unfiltered|without restrictions)\b",
    "disable-safety": r"\b(disable|turn off|bypass|override|ignore)\b.{0,20}\b(safety|guardrail|guardrails|filter|filters|moderation|restriction|restrictions)\b",
    "fake-tags": r"</?\s*(system|instructions|assistant)\s*>",
}
# Asks to build/obtain tooling for clearly harmful ends (mirrors the web/skill RS18 intent list).
HARMFUL = {
    "account-intrusion": r"\bhack (into|someone|my (ex|girlfriend|boyfriend|wife|husband|partner))\b",
    "steal-credentials": r"\bsteal (passwords?|accounts?|credentials?|logins?|data)\b",
    "spy-stalk": r"\b(spy on|stalk)\b|\bstalkerware\b|\bspyware\b",
    "crack-software": r"\bcrack (paid|licensed|commercial) software\b|\bkeygen\b",
    "take-down": r"\btake down (a )?(website|server|service)\b|\bddos\b",
}


def _scan(text):
    low = (text or "").lower()
    hits = []
    for cat, group in (("injection", INJECTION), ("harmful", HARMFUL)):
        for name, pat in group.items():
            if re.search(pat, low, re.I):
                hits.append({"category": cat, "pattern": name})
    return hits


def _log_path():
    p = os.environ.get("FIND_REPO_SECURITY_LOG")
    if not p:
        p = os.path.join(os.path.expanduser("~"), ".find-repo", "security.log")
    return p


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    try:
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}
    # UserPromptSubmit carries "prompt"; be liberal for other events / tool inputs too.
    text = event.get("prompt") or ""
    if not text:
        ti = event.get("tool_input")
        if isinstance(ti, dict):
            text = " ".join(str(v) for v in ti.values())
        elif isinstance(ti, str):
            text = ti
    hits = _scan(text)
    if not hits:
        return 0
    entry = {
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": event.get("hook_event_name") or "UserPromptSubmit",
        "session_id": event.get("session_id"),
        "matches": hits,
        "sample": (text[:200] + "…") if len(text) > 200 else text,  # truncated for audit, not the full text
    }
    try:
        path = _log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let a logging failure break the session
    return 0  # log only; never block (RS25)


if __name__ == "__main__":
    sys.exit(main())
