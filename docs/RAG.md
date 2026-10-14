# Replore and RAG (SPEC RS42)

**Short version:** Replore already works like a RAG system. GitHub search is the *retriever* and the user's own AI
writes the plan, so it is the *generator*. RS42 adds meaning-based retrieval next to GitHub's keyword search, in
phases. Each phase ships only if its gate passes.

**Hybrid search:** lexical (GitHub keyword search + BM25 against the whole description) and semantic (embeddings),
fused per query by weighted blend or reciprocal rank fusion (RRF), whichever the evals favour.

```
user description
   │
   ├─► needs-first keyword queries (RS16a) ─► GitHub search (live) ──┐
   │                                                                  ├─► ONE AI check (RS34) on both ─► confirm ─► fuse (RRF) ─► cards
   └─► embed (Workers AI bge) ─► Vectorize nearest repos (Phase 2) ───┘        ▲
                                     │                                         │
                                     └─► live GitHub confirm + refresh ────────┘   (unconfirmed → dropped)

cards ─► user ticks repos ─► plan prompt (RS28) ─► user's own AI writes the PRD   ← the "generation" step
```

| Phase | What | Cost | Gate | Status |
|---|---|---|---|---|
| 0 | Offline eval: BM25, embeddings and hybrids on 91 labelled repos | Free (local) | Best semantic/hybrid AUC ≥ 0.75 and ≥ BM25 + 0.15 | Script ready; BM25 = 0.56; real models not yet run |
| 1 | Hybrid rerank: BM25 + meaning scores, fused by RRF (web + plugin) | ~5 neurons/search (estimate) | Live eval (owner-approved) beats today | Built, **off** (`RAG_RERANK`) |
| 2 | Vectorize index + ingestion + live confirm (web + plugin) | Dry-run estimate first (owner-approved) | Recall set shows repos keyword search misses | Built, **off** (`RAG_INDEX`) |

## Run Phase 0 (on your machine)

```
pip install sentence-transformers
python evals/embed_offline.py
```

It downloads two small open models once (BAAI bge-small and bge-base), spends no API credits, and prints PASS or
FAIL against the gate. Paste the output back so the result goes into SPEC RS42.

## Why no RAG framework

LangChain, LlamaIndex, Haystack and RAGFlow orchestrate document chunking, vector stores and LLM calls. Replore has
no documents to chunk, one short AI check, and two hard constraints: a stdlib-only plugin (RS11) and a no-build web
page (RS22). The pieces RS42 needs (one embedding call, one vector query, rank fusion) are a few dozen lines each.

## Switching phases on (owner, in this order)

**Phase 1: hybrid rerank** (after the Phase 0 gate passes)
1. Cloudflare → Workers & Pages → replore → Settings → Variables and Secrets → add `RAG_RERANK` = `1` for **Preview** only.
2. Open a preview link, run a few searches, then approve a live eval run on the preview.
3. If it beats today's results, add the same variable for **Production**. To undo, delete it: the site goes back to today's behaviour.

**Phase 2: the repo index** (after Phase 1 is live)
1. Create the index once: `npx wrangler vectorize create replore-repos --dimensions=1024 --metric=cosine`.
2. GitHub → Actions → **rag-ingest** → Run workflow with *apply* off. Read the printed cost estimate.
3. Add repository secrets `CF_ACCOUNT_ID` and `CF_API_TOKEN` (token with Workers AI + Vectorize edit), then run again with *apply* on.
4. Uncomment the `[[vectorize]]` block in `wrangler.toml` (a PR), then add `RAG_INDEX` = `1` for Preview, test, then Production.

**Plugin:** `--semantic` needs `RAG_PLUGIN` = `1` as well (it has no bot check; see SPEC RS42 for the risk). `--rank hybrid` works offline any time.

## The pipeline in code

| Step | Web | Plugin | Server / ops |
|---|---|---|---|
| Keyword queries (needs first) | `keywordQueries` | the skill writes them | — |
| Lexical retrieval | GitHub search | GitHub search | — |
| Lexical scoring | `bm25Scores` | `hybrid.bm25_scores` | — |
| Semantic scoring | reply `sim` | `hybrid.semantic` → `sim` | `semanticScores` (bge-m3) |
| Semantic retrieval | reply `neighbors` | `hybrid.semantic` → `neighbors` | Vectorize `REPOS_INDEX.query` |
| Freshness / fail closed | `confirmQueries` → live search | `hybrid.confirm_queries` → live search | — |
| Fusion | `hybridOrder` (RRF) | `hybrid.hybrid_order` (RRF) | — |
| Generation | plan prompt → user's AI | user's AI | — |
| Index filling | — | — | `ops/ingest.py`, Actions `rag-ingest` |
