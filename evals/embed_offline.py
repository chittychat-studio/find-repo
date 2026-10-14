#!/usr/bin/env python3
"""SPEC RS42 Phase 0 gate: does meaning-based (embedding) ranking separate fitting repos from
off-topic ones better than keyword (BM25) ranking, on our hand-labelled relevance set?

Offline and free: no API key, no AI credits. It downloads open embedding models once
(BAAI bge family — the same models Cloudflare Workers AI serves as @cf/baai/bge-*).
Dev-only: needs `pip install sentence-transformers` (not part of the stdlib-only plugin, RS11).

Run:   python evals/embed_offline.py                 # bge-small + bge-base
       python evals/embed_offline.py --models BAAI/bge-small-en-v1.5
       python evals/embed_offline.py --fake          # no download; wiring check only (CI)

Score: AUC = chance a fitting repo scores above an off-topic one (0.5 coin flip, 1.0 perfect).
Also scores the RS42 hybrid (semantic + lexical): a per-query weighted blend and reciprocal rank fusion.
Gate (RS42): best semantic or hybrid pooled AUC >= 0.75 AND >= BM25 + 0.15 -> Phase 1 may be built.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SET = Path(__file__).resolve().parent / "relevance_set.json"
GATE_AUC, GATE_MARGIN = 0.75, 0.15
# bge v1.5 retrieval instruction for short queries (model card)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
STOP = set(("a an the my our your for to with and or of in on app apps application build building make making "
            "want really nice looking simple create please that helps people some something cool new project "
            "using use it by from first show as into about i ill i'll sell answers questions is are this").split())


def tokens(text):
    words = re.sub(r"[^a-z0-9 +#.]", " ", (text or "").lower()).split()
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w and w not in STOP]


def bm25_scores(pairs, k1=1.2, b=0.75):
    """BM25 of each (query, doc) pair, IDF over every doc in the set (pooled, so scores compare)."""
    docs = [tokens(d) for _, d in pairs]
    n = len(docs)
    avg = sum(map(len, docs)) / n
    df = Counter(w for d in docs for w in set(d))
    out = []
    for (q, _), d in zip(pairs, docs):
        tf = Counter(d)
        s = 0.0
        for w in set(tokens(q)):
            if tf[w]:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avg))
        out.append(s)
    return out


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def fake_embed(texts, dim=256):
    """Hashed bag of words — deterministic, no download. Only proves the wiring works."""
    out = []
    for t in texts:
        v = [0.0] * dim
        for w in tokens(t.replace(QUERY_PREFIX, "")):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
        out.append(v)
    return out


def model_embedder(name):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        sys.exit("Needs: pip install sentence-transformers   (or run with --fake)")
    model = SentenceTransformer(name)
    return lambda texts: [list(map(float, v)) for v in model.encode(texts, normalize_embeddings=True)]


def embed_scores(pairs, embed):
    queries = sorted({q for q, _ in pairs})
    qv = dict(zip(queries, embed([QUERY_PREFIX + q for q in queries])))
    dv = embed([d for _, d in pairs])
    return [cosine(qv[q], v) for (q, _), v in zip(pairs, dv)]


def _norm_per_query(items, scores):
    """Min-max scale scores within each query, so lexical and semantic scores can be blended."""
    groups = defaultdict(list)
    for i, it in enumerate(items):
        groups[it["query"]].append(i)
    out = [0.0] * len(scores)
    for idx in groups.values():
        lo, hi = min(scores[i] for i in idx), max(scores[i] for i in idx)
        for i in idx:
            out[i] = (scores[i] - lo) / (hi - lo) if hi > lo else 0.0
    return out


def hybrid_blend(items, lexical, semantic, w):
    """RS42 hybrid: w x semantic + (1 - w) x lexical, each scaled per query."""
    lx, sm = _norm_per_query(items, lexical), _norm_per_query(items, semantic)
    return [w * b + (1 - w) * a for a, b in zip(lx, sm)]


def hybrid_rrf(items, lexical, semantic, k=60):
    """RS42 hybrid: reciprocal rank fusion of the lexical and semantic orders within each query."""
    groups = defaultdict(list)
    for i, it in enumerate(items):
        groups[it["query"]].append(i)
    out = [0.0] * len(lexical)
    for idx in groups.values():
        for sc in (lexical, semantic):
            for rank, i in enumerate(sorted(idx, key=lambda j: -sc[j])):
                out[i] += 1.0 / (k + rank + 1)
    return out


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def per_query_auc(items, scores):
    groups = defaultdict(list)
    for it, s in zip(items, scores):
        groups[it["query"]].append((s, it["rel"]))
    vals = [auc([s for s, _ in g], [l for _, l in g]) for g in groups.values()]
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def report(name, items, scores):
    labels = [it["rel"] for it in items]
    pooled = auc(scores, labels)
    mean_q, nq = per_query_auc(items, scores)
    good = sorted(s for s, l in zip(scores, labels) if l)
    junk_high = sum(s > good[len(good) // 2] for s, l in zip(scores, labels) if not l)
    junk = sum(1 for l in labels if not l)
    mq = f"{mean_q:.2f} over {nq} mixed queries" if mean_q is not None else "n/a"
    print(f"{name:32} pooled AUC {pooled:.2f}   per-query AUC {mq}   junk above median good: {junk_high}/{junk}")
    return pooled


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", nargs="*", default=["BAAI/bge-small-en-v1.5", "BAAI/bge-base-en-v1.5"])
    ap.add_argument("--fake", action="store_true", help="hashed bag-of-words embedder, no download")
    args = ap.parse_args(argv)
    items = json.loads(SET.read_text(encoding="utf-8"))["items"]
    pairs = [(it["query"], it["text"]) for it in items]
    print(f"{len(items)} hand-labelled repos, {len({q for q, _ in pairs})} queries "
          f"({sum(it['rel'] for it in items)} fit, {sum(not it['rel'] for it in items)} off-topic)\n")
    lexical = bm25_scores(pairs)
    bm = report("BM25 (lexical)", items, lexical)
    best = None
    for name in (["fake-bag-of-words"] if args.fake else args.models):
        embed = fake_embed if args.fake else model_embedder(name)
        semantic = embed_scores(pairs, embed)
        scores = [report(name.split("/")[-1] + " (semantic)", items, semantic)]
        for w in (0.5, 0.7):
            scores.append(report(f"  hybrid {int(w * 100)}% semantic", items, hybrid_blend(items, lexical, semantic, w)))
        scores.append(report("  hybrid RRF", items, hybrid_rrf(items, lexical, semantic)))
        best = max([best or 0] + scores)
    ok = best is not None and best >= GATE_AUC and best >= bm + GATE_MARGIN
    print(f"\nRS42 Phase 0 gate (best >= {GATE_AUC} and >= BM25 + {GATE_MARGIN}): {'PASS' if ok else 'FAIL'}"
          + ("   [--fake: wiring check only, not a real result]" if args.fake else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
