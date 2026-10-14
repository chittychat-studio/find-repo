#!/usr/bin/env python3
"""SPEC RS42b: smoke check that the RAG half really runs on a deployment (maintainer tool, not shipped with the plugin).

1. GET  <base>/api/relevance  -> which RAG parts the deployment says are switched on (free).
2. POST <base>/api/relevance {"mode":"semantic"} for a few fixed searches -> meaning scores / indexed repos must come
   back in the right shape. This uses the plugin route, so the deployment needs RAG_PLUGIN=1 (set it for Preview only).

Cost gate: step 2 makes one Workers AI embedding call per fixed search (and one Vectorize query when the index is on).
Without --yes it prints that and stops after step 1. Standard library only. Exit 0 = RAG ran; 1 = it did not.

  python ops/rag_smoke.py https://claude-my-branch.replore.pages.dev          # step 1 + cost note
  python ops/rag_smoke.py https://claude-my-branch.replore.pages.dev --yes    # runs the fixed searches
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

CASES = [
    ("voice based app to track my diet and steps", [
        {"name": "a/calorie-counter", "description": "Track calories and diet", "topics": ["nutrition"]},
        {"name": "b/karaoke", "description": "Make karaoke from songs", "topics": []}]),
    ("offline maps for a trip planner", [
        {"name": "maplibre/maplibre-gl-js", "description": "Interactive vector tile maps in the browser", "topics": ["maps"]},
        {"name": "c/chat", "description": "A chat app", "topics": []}]),
    ("chatbot that answers questions from my PDFs", [
        {"name": "d/pdf-qa", "description": "Ask questions about PDF documents", "topics": ["rag"]},
        {"name": "e/game", "description": "2D platform game", "topics": []}]),
]
NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _call(url, body=None, opener=urllib.request.urlopen, timeout=20):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "replore-rag-smoke"})
    try:
        with opener(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return 0, {"error": type(e).__name__}


def check_reply(flags, repos, status, j):
    """Problems with one semantic reply ([] = fine)."""
    if status != 200:
        return [f"HTTP {status} {j.get('error', '')}".strip()]
    out = []
    if flags.get("rerank"):
        sim = j.get("sim")
        if not (isinstance(sim, list) and len(sim) == len(repos) and all(isinstance(x, (int, float)) for x in sim)):
            out.append("meaning scores missing or wrong length")
        elif sim[0] <= sim[1]:
            out.append(f"fitting repo did not score higher ({sim[0]} vs {sim[1]})")
    if flags.get("index"):
        nb = j.get("neighbors")
        if not (isinstance(nb, list) and all(isinstance(x, dict) and isinstance(x.get("name"), str)
                                             and NAME.fullmatch(x["name"]) for x in nb)):
            out.append("indexed repos missing or malformed")
    return out


def main(argv=None, opener=urllib.request.urlopen):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base", help="deployment URL, e.g. https://claude-my-branch.replore.pages.dev")
    ap.add_argument("--yes", action="store_true", help="approve the Workers AI calls")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", a.base.rstrip("/")):
        print("base must be an https:// origin with no path")
        return 1
    url = a.base.rstrip("/") + "/api/relevance"
    status, cfg = _call(url, opener=opener)
    flags = cfg.get("rag") if isinstance(cfg, dict) and isinstance(cfg.get("rag"), dict) else {}
    print(f"switched on: rerank={bool(flags.get('rerank'))} index={bool(flags.get('index'))} (HTTP {status})")
    if not (flags.get("rerank") or flags.get("index")):
        print("FAIL: RAG is not switched on for this deployment (set RAG_RERANK=1 and/or RAG_INDEX=1)")
        return 1
    if not a.yes:
        print(f"Next step makes {len(CASES)} Workers AI embedding calls"
              + (f" and {len(CASES)} Vectorize queries" if flags.get("index") else "")
              + ". Re-run with --yes to approve.")
        return 1
    bad = 0
    for query, repos in CASES:
        st, j = _call(url, {"mode": "semantic", "query": query, "repos": repos}, opener=opener)
        probs = check_reply(flags, repos, st, j if isinstance(j, dict) else {})
        bad += bool(probs)
        print(f"[{'FAIL' if probs else 'PASS'}] {query}" + ("" if not probs else "  -> " + "; ".join(probs)))
    if bad:
        print("RAG did not run cleanly. Check the Functions logs for rag_fail codes (sem_timeout, sem_error, "
              "sem_bad_shape, index_timeout, index_error). HTTP 404 semantic_off = RAG_PLUGIN=1 is not set.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
