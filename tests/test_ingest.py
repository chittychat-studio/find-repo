"""SPEC RS42 Phase 2: index ingestion (ops/ingest.py). Fake network only; nothing is embedded or written."""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops"))
import ingest  # noqa: E402

GOLDEN_CARD = "a/b. Hello b world /b Topics: x, y"   # tests/test_relevance_fn.mjs asserts the same for the server


class _R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_card_matches_server_and_ids_are_stable():
    assert ingest.card_text("a/b", "Hello <b>world</b>", ["x", "y"]) == GOLDEN_CARD
    assert ingest.vector_id("Owner/Repo") == ingest.vector_id("owner/repo") and len(ingest.vector_id("a/b")) == 40


def test_collect_dedups_filters_and_paces():
    pages = {1: [{"full_name": "a/b", "description": "d", "stargazers_count": 90, "topics": ["t"]},
                 {"full_name": "a/b", "description": "dup"}, {"full_name": "f/fork", "fork": True},
                 {"full_name": "bad name"}]}
    urls, sleeps = [], []
    def opener(req, timeout):
        urls.append(req.full_url)
        assert "Authorization" not in req.headers or req.headers["Authorization"] == "Bearer T"
        return _R(json.dumps({"items": pages.get(1)}).encode())
    cards = ingest.collect(["calorie counter", "step counter"], 2, "T", opener=opener, sleep=sleeps.append)
    assert [c["metadata"]["name"] for c in cards] == ["a/b"]
    assert len(urls) == 2 and "sort=stars" in urls[0] and "stars%3A%3E%3D50" in urls[0] and len(sleeps) == 2


def test_dry_run_is_the_default_and_apply_needs_secrets(monkeypatch, capsys):
    monkeypatch.setattr(ingest, "collect", lambda seeds, pages, token: [
        {"id": "x", "text": "a/b. calorie counter", "metadata": {"name": "a/b"}}])
    called = []
    monkeypatch.setattr(ingest, "embed", lambda *a, **k: called.append("embed"))
    for k in ("CF_ACCOUNT_ID", "CF_API_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert ingest.main([]) == 0 and called == []                      # cost gate: no embedding without --apply
    out = capsys.readouterr().out
    assert "Dry run" in out and "neurons" in out and "free tier" in out
    assert ingest.main(["--apply"]) == 2                              # no secrets -> refuses


def test_estimate_and_free_tier_flag():
    e = ingest.estimate([{"text": "x" * 400}] * 10)
    assert e["repos"] == 10 and e["stored_dims"] == 10 * ingest.DIMS and not e["over_free_storage"]
    assert ingest.estimate([{"text": "x"}] * 5000)["over_free_storage"]


def test_embed_and_upsert_shapes():
    seen = {}
    def opener(req, timeout):
        seen.setdefault("urls", []).append(req.full_url)
        if req.full_url.endswith("/upsert"):
            seen["nd"] = req.data.decode().splitlines()
            return _R(b'{"success":true}')
        return _R(json.dumps({"success": True, "result": {"data": [[0.1, 0.2]]}}).encode())
    v = ingest.embed(["t"], "ACC", "K", opener=opener)
    ingest.upsert([{"id": "x", "values": v[0], "metadata": {"name": "a/b"}}], "ACC", "K", "replore-repos", opener=opener)
    assert seen["urls"][0].endswith("/accounts/ACC/ai/run/@cf/baai/bge-m3")
    assert seen["urls"][1].endswith("/accounts/ACC/vectorize/v2/indexes/replore-repos/upsert")
    assert json.loads(seen["nd"][0])["metadata"]["name"] == "a/b"


def test_stdlib_only():
    import ast
    tree = ast.parse((ROOT / "ops" / "ingest.py").read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= set(sys.stdlib_module_names)
