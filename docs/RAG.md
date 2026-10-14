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
   │                                                                  ├─► fuse (RRF) ─► AI check (RS34) ─► fit + meaning rank ─► cards
   └─► embed (Workers AI bge) ─► Vectorize nearest repos (Phase 2) ───┘        ▲
                                     │                                         │
                                     └─► live GitHub confirm + refresh ────────┘   (unconfirmed → dropped)

cards ─► user ticks repos ─► plan prompt (RS28) ─► user's own AI writes the PRD   ← the "generation" step
```

| Phase | What | Cost | Gate | Status |
|---|---|---|---|---|
| 0 | Offline eval: BM25, embeddings and hybrids on 91 labelled repos | Free (local) | Best semantic/hybrid AUC ≥ 0.75 and ≥ BM25 + 0.15 | Script ready; BM25 = 0.56 |
| 1 | Hybrid rerank of GitHub results: BM25 + embeddings (web; BM25 also in plugin) | ~5 neurons/search (estimate) | Live eval (owner-approved) beats today | Not started |
| 2 | Vectorize index + ingestion + live confirm | Workers/Vectorize plan (owner-approved) | Recall set shows repos keyword search misses | Not started |

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
