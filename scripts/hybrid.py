"""SPEC RS42 hybrid retrieval for the plugin — the same structure as the web page.

Lexical: BM25 of each repo against the user's whole description (identical to the page's bm25Scores).
Semantic (opt-in, --semantic): meaning scores and indexed nearest repos from Replore's endpoint, which runs
Cloudflare Workers AI embeddings and the Vectorize index server-side. Off by default, so the plugin stays
fully local unless the user asks (RS11). Standard library only.
Fusion: reciprocal rank fusion (RRF) of the fit order, the BM25 order and, when present, the meaning order.
"""
import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter

ENDPOINT = "https://replore.cardzo.co.in/api/relevance"
RRF_K = 60
# Same words as the web page's STOP list (tests/test_scout.py checks they stay identical).
STOP = set(("a an the my our your for to with and or of in on app apps application build building make making want "
            "really nice looking simple create please that helps people some something cool new project using use it "
            "by from first show as into about i ill i'll sell answers questions").split())
_NONWORD = re.compile(r"[^a-z0-9 +#.]")


def lex_tokens(text):
    """Lower-case words without filler words; a plural 's' is dropped (maps -> map)."""
    words = _NONWORD.sub(" ", (text or "").lower()).split()
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w and w not in STOP]


def repo_text(name, description, topics=()):
    return " ".join([(name or "").replace("/", " ").replace("-", " ").replace("_", " "), description or "", " ".join(topics or ())])


def bm25_scores(query, docs, k1=1.2, b=0.75):
    """BM25 of one query against a small set of repo texts; IDF over that set."""
    toks = [lex_tokens(d) for d in docs]
    n = len(toks)
    if not n:
        return []
    avg = (sum(map(len, toks)) / n) or 1.0
    df = Counter(w for t in toks for w in set(t))
    q = set(lex_tokens(query))
    out = []
    for t in toks:
        tf = Counter(t)
        s = 0.0
        for w in q:
            if tf[w]:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        out.append(round(s, 6))
    return out


def rrf_order(n, score_lists, k=RRF_K):
    """Indices 0..n-1 ordered by reciprocal rank fusion. Each list holds one score per item (higher = better);
    list 0 is the current order (pass None to use the given order). Ties keep the current order."""
    fused = [0.0] * n
    for scores in score_lists:
        order = list(range(n)) if scores is None else sorted(range(n), key=lambda i: (-scores[i], i))
        for rank, i in enumerate(order):
            fused[i] += 1.0 / (k + rank + 1)
    return sorted(range(n), key=lambda i: (-fused[i], i))


def hybrid_order(rows, description, sims=None):
    """RS42: rows (already in fit order) re-ordered by fit + BM25 (+ meaning when sims is given)."""
    if not rows or not (description or "").strip():
        return list(rows)
    lex = bm25_scores(description, [repo_text(r.get("full_name"), r.get("description"), r.get("topics")) for r in rows])
    lists = [None, lex]
    if sims and len(sims) == len(rows):
        lists.append(sims)
    return [rows[i] for i in rrf_order(len(rows), lists)]


def semantic(description, rows, endpoint=ENDPOINT, timeout=12, opener=urllib.request.urlopen):
    """Opt-in: meaning scores for rows and indexed nearest repos. Any failure -> None (results stay keyword + BM25)."""
    body = json.dumps({"mode": "semantic", "query": (description or "")[:200],
                       "repos": [{"name": r["full_name"], "description": (r.get("description") or "")[:100],
                                  "topics": list(r.get("topics") or [])[:5]} for r in rows[:30]]}).encode()
    req = urllib.request.Request(endpoint, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "replore-plugin"})
    try:
        with opener(req, timeout=timeout) as r:
            j = json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if not isinstance(j, dict):
        return None
    sim = j.get("sim") if isinstance(j.get("sim"), list) and all(isinstance(x, (int, float)) for x in j["sim"]) else None
    nb = [x for x in (j.get("neighbors") or []) if isinstance(x, dict) and isinstance(x.get("name"), str)
          and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", x["name"]) and isinstance(x.get("score"), (int, float))]
    return {"sim": sim, "neighbors": nb[:8]}


def confirm_queries(names, limit=200):
    """Live GitHub check for indexed repos: as few searches as fit, each 'repo:a/b repo:c/d' under the limit."""
    out, cur = [], ""
    for n in names:
        part = f"repo:{n}"
        if cur and len(cur) + 1 + len(part) > limit:
            out.append(cur)
            cur = part
        else:
            cur = (cur + " " + part).strip()
    if cur:
        out.append(cur)
    return out
