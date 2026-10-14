"""SPEC RS42: plugin hybrid retrieval (BM25 + opt-in meaning scores + live-confirmed indexed repos). No network."""
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hybrid  # noqa: E402
import scout  # noqa: E402

DESC = "voice based ai app to track my diet and step counter"
DOCS = [hybrid.repo_text("a/calorie-counter", "Track calories and diet", ["nutrition"]),
        hybrid.repo_text("b/karaoke", "Make karaoke from songs", []),
        hybrid.repo_text("c/step-counter", "Android step counter app", ["fitness"])]
GOLDEN = [2.374521, 0.0, 1.871074]   # the same numbers tests/test_web_logic.js asserts for the page (parity)


def test_bm25_golden_and_stop_parity_with_page():
    assert hybrid.bm25_scores(DESC, DOCS) == GOLDEN
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    page_stop = re.search(r'var STOP=new Set\("([^"]+)"', html).group(1).split(" ")
    assert set(page_stop) == hybrid.STOP, "plugin and page must drop the same filler words"


def test_rrf_and_hybrid_order():
    assert hybrid.rrf_order(3, [None, [0, 5, 1]]) == [1, 0, 2]
    rows = [{"full_name": "b/karaoke", "description": "Make karaoke from songs"},
            {"full_name": "z/noise", "description": "Unrelated toolkit"},
            {"full_name": "a/calorie-counter", "description": "Track calories and diet", "topics": ["nutrition"]}]
    names = lambda rs: [r["full_name"] for r in rs]
    # BM25 alone lifts the diet repo one place but cannot overturn the fit order on its own (damped by design)
    assert names(hybrid.hybrid_order(rows, DESC)) == ["b/karaoke", "a/calorie-counter", "z/noise"]
    # when meaning agrees with BM25, the diet repo goes to the top (2 of 3 signals)
    assert names(hybrid.hybrid_order(rows, DESC, [0.1, 0.2, 0.9])) == ["a/calorie-counter", "b/karaoke", "z/noise"]
    assert hybrid.hybrid_order(rows, "") == rows                       # no description: order untouched
    assert names(hybrid.hybrid_order(rows, DESC, [0.1, 0.2])) == names(hybrid.hybrid_order(rows, DESC))   # wrong length: ignored


def test_confirm_queries_stay_under_limit():
    qs = hybrid.confirm_queries([f"owner{i}/repository-name-{i}" for i in range(9)])
    assert all(len(q) <= 200 for q in qs) and sum(q.count("repo:") for q in qs) == 9


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_semantic_parses_and_fails_closed():
    rows = [{"full_name": "a/b", "description": "x"}]
    seen = {}
    def ok(req, timeout):
        seen["body"] = json.loads(req.data)
        return _Resp(json.dumps({"sim": [0.8], "neighbors": [{"name": "c/d", "score": 0.7}, {"name": "bad name", "score": 1}]}).encode())
    r = hybrid.semantic(DESC, rows, opener=ok)
    assert r == {"sim": [0.8], "neighbors": [{"name": "c/d", "score": 0.7}]}   # malformed names dropped (RS9)
    assert seen["body"]["mode"] == "semantic" and seen["body"]["repos"][0]["name"] == "a/b"
    def down(req, timeout): raise OSError("no network")
    assert hybrid.semantic(DESC, rows, opener=down) is None


def _repo(name, stars, desc):
    return {"full_name": name, "stargazers_count": stars, "license": {"spdx_id": "MIT"}, "pushed_at": "2026-09-01T00:00:00Z",
            "description": desc, "html_url": "https://github.com/" + name, "topics": []}


NOW = scout.dt.datetime(2026, 10, 1, tzinfo=scout.dt.timezone.utc)


def test_default_is_unchanged_and_hybrid_reorders():
    items = [_repo("b/karaoke", 900, "Make karaoke from songs"), _repo("z/noise", 850, "Unrelated toolkit"),
             _repo("a/calorie-counter", 800, "Track calories and diet")]
    fetch = lambda q, token=None: {"items": items}
    fit = scout.scout(["diet"], fetcher=fetch, now=NOW)
    assert [r["full_name"] for r in fit["top"]] == ["b/karaoke", "z/noise", "a/calorie-counter"] and fit["semantic"] is None
    hyb = scout.scout(["diet"], fetcher=fetch, now=NOW, rank_mode="hybrid", description=DESC)
    assert [r["full_name"] for r in hyb["top"]] == ["b/karaoke", "a/calorie-counter", "z/noise"]
    sem = scout.scout(["diet"], fetcher=fetch, now=NOW, semantic_on=True, description=DESC,
                      semantic_fn=lambda d, rows: {"sim": [0.1, 0.2, 0.9], "neighbors": []})
    assert [r["full_name"] for r in sem["top"]][0] == "a/calorie-counter"


def test_semantic_neighbors_only_after_live_confirm():
    calls = []
    def fetch(q, token=None):
        calls.append(q)
        if q.startswith("repo:"):   # the live confirm: only c/real still exists
            return {"items": [_repo("c/real", 300, "Step counter for Android")]}
        return {"items": [_repo("a/calorie-counter", 800, "Track calories and diet")]}
    sem = lambda d, rows: {"sim": [0.9], "neighbors": [{"name": "c/real", "score": 0.8}, {"name": "d/gone", "score": 0.9}]}
    res = scout.scout(["diet"], fetcher=fetch, now=NOW, semantic_on=True, semantic_fn=sem, description=DESC)
    names = [r["full_name"] for r in res["top"]]
    assert "c/real" in names and "d/gone" not in names            # unconfirmed indexed repo never shown (RS7)
    assert any(q.startswith("repo:c/real repo:d/gone") for q in calls)
    assert res["semantic"] == "ok" and "found by meaning" in res["queries"]


def test_semantic_unavailable_keeps_keyword_results():
    fetch = lambda q, token=None: {"items": [_repo("a/calorie-counter", 800, "Track calories and diet")]}
    res = scout.scout(["diet"], fetcher=fetch, now=NOW, semantic_on=True, semantic_fn=lambda d, r: None)
    assert res["semantic"] == "unavailable" and [r["full_name"] for r in res["top"]] == ["a/calorie-counter"]
