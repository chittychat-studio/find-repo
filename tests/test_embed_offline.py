"""SPEC RS42 Phase 0: the offline embedding eval's scoring is correct (no model download)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import embed_offline as eo  # noqa: E402


def test_auc_basics():
    assert eo.auc([3, 2, 1], [True, False, False]) == 1.0
    assert eo.auc([1, 2, 3], [True, False, False]) == 0.0
    assert eo.auc([1, 1], [True, False]) == 0.5
    assert eo.auc([1, 2], [True, True]) is None          # one class: no AUC


def test_bm25_prefers_matching_doc():
    s = eo.bm25_scores([("calorie tracker", "calorie tracker app for diet"), ("calorie tracker", "karaoke from songs")])
    assert s[0] > s[1] == 0


def test_query_prefix_never_leaks_into_fake_tokens():
    a, b = eo.fake_embed([eo.QUERY_PREFIX + "voice", "voice"])
    assert a == b


def test_fake_run_wires_end_to_end(capsys):
    eo.main(["--fake"])                                   # exit code is the gate verdict; wiring is what's tested
    out = capsys.readouterr().out
    assert "BM25 (lexical)" in out and "hybrid RRF" in out and "hybrid 50% semantic" in out and "fake-bag-of-words" in out and "RS42 Phase 0 gate" in out


def test_hybrid_blend_and_rrf():
    items = [{"query": "q", "rel": True}, {"query": "q", "rel": False}]
    lex, sem = [2.0, 1.0], [0.1, 0.9]                    # lexical prefers item 0, semantic item 1
    assert eo.hybrid_blend(items, lex, sem, 1.0) == [0.0, 1.0]   # all-semantic follows semantic
    assert eo.hybrid_blend(items, lex, sem, 0.0) == [1.0, 0.0]   # all-lexical follows lexical
    r = eo.hybrid_rrf(items, lex, sem)
    assert abs(r[0] - r[1]) < 1e-12                      # one first place each: a tie
