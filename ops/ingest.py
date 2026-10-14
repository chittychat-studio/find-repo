#!/usr/bin/env python3
"""SPEC RS42 Phase 2: fill the Replore Vectorize index with repo cards (maintainer tool, not shipped with the plugin).

For each seed search in ops/rag_seeds.txt: GitHub search (sorted by stars, 50+ stars, pushed within 24 months, no forks
or archived repos) -> one card per repo (name, description, topics) -> Workers AI embedding (bge-m3) -> Vectorize upsert.
Only public repo metadata is stored. Standard library only.

Cost gate: the default is a DRY RUN. It searches GitHub (free), counts repos and prints the estimated Workers AI usage
and Vectorize storage, then stops. Nothing is embedded or written without --apply.

  python ops/ingest.py                      # dry run: counts + cost estimate
  python ops/ingest.py --apply              # needs GITHUB_TOKEN, CF_ACCOUNT_ID, CF_API_TOKEN

The index must exist first:  npx wrangler vectorize create replore-repos --dimensions=1024 --metric=cosine
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GH = "https://api.github.com/search/repositories"
CF = "https://api.cloudflare.com/client/v4/accounts/{acct}"
MODEL = "@cf/baai/bge-m3"          # same model as functions/api/relevance.js EMBED_MODEL
DIMS = 1024                        # bge-m3 output size (create the index with this)
NEURONS_PER_M_TOKENS = 1075        # Cloudflare's published rate for bge-m3 (checked 2026-10-14)
FREE_STORED_DIMS = 5_000_000       # Vectorize free tier, stored vector dimensions
SEEDS = Path(__file__).with_name("rag_seeds.txt")
_CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏  ‪-‮⁦-⁩]")


def clean(s, n):
    return re.sub(r"\s+", " ", _CTRL.sub(" ", str(s or "")).replace("<", " ").replace(">", " ")).strip()[:n]


def card_text(name, description, topics):
    """Same card the server embeds at query time (relevance.js cardText), so index and query vectors match."""
    t = ", ".join(clean(x, 30) for x in (topics or [])[:8] if clean(x, 30))
    return f"{clean(name, 140)}. {clean(description, 160)}" + (f" Topics: {t}" if t else "")


def vector_id(name):
    return hashlib.sha1(name.lower().encode()).hexdigest()   # Vectorize ids are short; full names can be long


def seed_list(path=SEEDS):
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def _http(req, timeout=30, opener=urllib.request.urlopen):
    with opener(req, timeout=timeout) as r:
        return json.load(r)


def search(seed, page, token, since, opener=urllib.request.urlopen):
    q = f"{seed} fork:false archived:false is:public stars:>=50 pushed:>={since}"
    req = urllib.request.Request(GH + "?" + urllib.parse.urlencode({"q": q, "sort": "stars", "per_page": 100, "page": page}),
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "replore-ingest"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return _http(req, opener=opener).get("items") or []


def collect(seeds, pages, token, now=None, opener=urllib.request.urlopen, pause=2.1, sleep=time.sleep):
    since = ((now or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(days=730)).date().isoformat()
    cards = {}
    for seed in seeds:
        for page in range(1, pages + 1):
            items = search(seed, page, token, since, opener)
            for it in items:
                name = it.get("full_name") or ""
                if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) or it.get("fork") or it.get("archived"):
                    continue
                cards.setdefault(name.lower(), {
                    "id": vector_id(name), "text": card_text(name, it.get("description"), it.get("topics")),
                    "metadata": {"name": name, "stars": int(it.get("stargazers_count") or 0),
                                 "license": (it.get("license") or {}).get("spdx_id") or "",
                                 "pushed": (it.get("pushed_at") or "")[:10], "seed": seed}})
            if pause:
                sleep(pause)   # authenticated search: 30 requests a minute
            if len(items) < 100:
                break
    return list(cards.values())


def estimate(cards):
    tokens = sum(len(c["text"]) for c in cards) // 4 + len(cards)   # ~4 characters a token
    neurons = tokens * NEURONS_PER_M_TOKENS / 1_000_000
    stored = len(cards) * DIMS
    return {"repos": len(cards), "tokens": tokens, "neurons": round(neurons, 1), "stored_dims": stored,
            "over_free_storage": stored > FREE_STORED_DIMS}


def embed(texts, acct, cf_token, opener=urllib.request.urlopen):
    req = urllib.request.Request(CF.format(acct=acct) + "/ai/run/" + MODEL, method="POST",
                                 data=json.dumps({"text": texts}).encode(),
                                 headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"})
    out = _http(req, timeout=60, opener=opener)
    data = (out.get("result") or {}).get("data") if isinstance(out, dict) else None
    if not out.get("success") or not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError("embedding failed")
    return data


def upsert(rows, acct, cf_token, index, opener=urllib.request.urlopen):
    nd = "\n".join(json.dumps(r) for r in rows).encode()
    req = urllib.request.Request(CF.format(acct=acct) + f"/vectorize/v2/indexes/{index}/upsert", method="POST", data=nd,
                                 headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/x-ndjson"})
    out = _http(req, timeout=60, opener=opener)
    if not out.get("success"):
        raise RuntimeError("upsert failed")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="embed and write to Vectorize (spends Workers AI usage)")
    ap.add_argument("--pages", type=int, default=2, help="pages of 100 per seed (GitHub caps a search at 1000)")
    ap.add_argument("--index", default="replore-repos")
    ap.add_argument("--batch", type=int, default=50)
    a = ap.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")   # never printed
    acct, cf_token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if a.apply and not (token and acct and cf_token):
        print("ingest: --apply needs GITHUB_TOKEN, CF_ACCOUNT_ID and CF_API_TOKEN set.", file=sys.stderr)
        return 2
    try:
        cards = collect(seed_list(), max(1, min(a.pages, 10)), token)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"ingest: GitHub search failed ({getattr(e, 'code', '') or type(e).__name__}); nothing written.", file=sys.stderr)
        return 2
    est = estimate(cards)
    print(f"{est['repos']} repos from {len(seed_list())} seeds | ~{est['tokens']} tokens -> ~{est['neurons']} Workers AI "
          f"neurons (10,000 free a day) | {est['stored_dims']:,} stored dimensions "
          f"({'over' if est['over_free_storage'] else 'within'} the 5,000,000 Vectorize free tier)")
    if not a.apply:
        print("Dry run: nothing embedded or written. Re-run with --apply after approving the estimate.")
        return 0
    done = 0
    try:
        for i in range(0, len(cards), a.batch):
            chunk = cards[i:i + a.batch]
            vecs = embed([c["text"] for c in chunk], acct, cf_token)
            upsert([{"id": c["id"], "values": v, "metadata": c["metadata"]} for c, v in zip(chunk, vecs)], acct, cf_token, a.index)
            done += len(chunk)
    except (urllib.error.URLError, OSError, ValueError, RuntimeError) as e:
        print(f"ingest: stopped after {done} of {len(cards)} ({getattr(e, 'code', '') or e}).", file=sys.stderr)
        return 2
    print(f"Upserted {done} repo cards into {a.index}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
