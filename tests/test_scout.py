"""Replore unit tests. No network: fetch is replaced with fixtures (RS2-RS11)."""
import datetime as dt
import io
import json
import re
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scout  # noqa: E402

NOW = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)


def repo(name, stars, spdx="MIT", pushed="2026-09-01T00:00:00Z", **kw):
    return {"full_name": name, "stargazers_count": stars, "license": {"spdx_id": spdx} if spdx else None,
            "pushed_at": pushed, "html_url": f"https://github.com/{name}", "description": f"{name} desc",
            "fork": False, "archived": False, **kw}


def fake(pages):
    calls = []

    def f(q, token=None):
        calls.append((q, token))
        return {"items": pages[len(calls) - 1]}
    f.calls = calls
    return f


def run(pages, queries=None, **kw):
    f = fake(pages)
    res = scout.scout(queries or [f"q{i}" for i in range(len(pages))], fetcher=f, now=NOW, **kw)
    return res, f


def test_dedupes_and_ranks_across_queries():
    """RS2, RS5."""
    res, _ = run([[repo("a/gsap", 20000), repo("b/x", 500)], [repo("c/taste", 3000), repo("a/gsap", 20000)]])
    assert [r["full_name"] for r in res["top"]] == ["a/gsap", "c/taste", "b/x"]
    assert [r["rank"] for r in res["top"]] == [1, 2, 3]
    assert res["excluded"]["duplicate"] == 1
    assert res["top"][1]["query"] == "q1"


def test_tie_broken_by_recent_push():
    """RS5: in stars mode, equal stars are broken by the most recent push."""
    res, _ = run([[repo("a/old", 100, pushed="2026-01-01T00:00:00Z"), repo("b/new", 100)]], rank_mode="stars")
    assert [r["full_name"] for r in res["top"]] == ["b/new", "a/old"]


def test_balanced_rank_stops_one_query_swamping_others():
    """RS5: the iOS/website failure: one broad query used to fill the whole top 10."""
    broad = [repo(f"big/r{i}", 100000 - i) for i in range(10)]
    niche = [repo("niche/a", 900), repo("niche/b", 800)]
    other = [repo("other/a", 50)]
    res, _ = run([broad, niche, other], top=3, rank_mode="balanced")
    assert [r["full_name"] for r in res["top"]] == ["big/r0", "niche/a", "other/a"]
    assert [r["full_name"] for r in res["candidates"][3:5]] == ["big/r1", "niche/b"]


def test_stars_rank_mode_keeps_old_order():
    """RS5."""
    broad = [repo(f"big/r{i}", 100000 - i) for i in range(5)]
    res, _ = run([broad, [repo("niche/a", 900)]], top=3, rank_mode="stars")
    assert [r["full_name"] for r in res["top"]] == ["big/r0", "big/r1", "big/r2"]


def test_balanced_round_sorted_by_stars_and_empty_query_skipped():
    """RS5."""
    res, _ = run([[repo("a/low", 10)], [], [repo("b/high", 99)]], rank_mode="balanced")
    assert [r["full_name"] for r in res["top"]] == ["b/high", "a/low"]


def test_fit_score_lifts_relevance_and_freedom():
    """RS5: a precise top-of-search match beats a tangential giant; permissive beats copyleft at a tie."""
    exact = {"rel": 0, "stars": 300, "starter": False, "license_use": scout.USE_PAID_OK}
    giant = {"rel": 12, "stars": 120000, "starter": False, "license_use": scout.USE_PAID_OK}
    assert scout.fit_score(exact) > scout.fit_score(giant)
    mit = {"rel": 0, "stars": 1000, "starter": False, "license_use": scout.USE_PAID_OK}
    agpl = {"rel": 0, "stars": 1000, "starter": False, "license_use": scout.USE_NETWORK}
    assert scout.fit_score(mit) > scout.fit_score(agpl)


def test_fit_is_default_and_ranks_relevant_small_repo_first():
    """RS5: with fit (the default), the exact match at the top of its search outranks a far bigger tangential repo."""
    # tangential giant sits 13th in its query's results (rel=12); the exact match is first in its query (rel=0)
    tangential = [repo(f"big/f{i}", 1) for i in range(12)] + [repo("big/giant", 120000)]
    res, _ = run([[repo("tiny/exact", 300)], tangential])
    assert res["rank_mode"] == "fit"
    assert res["top"][0]["full_name"] == "tiny/exact"


def test_why_relevant_keyword_then_fallback():
    """RS24: shows the matched words, else a best-match fallback."""
    w = scout.why_relevant("rag chatbot", "me/rag-chat", "a RAG chatbot over PDFs", 0)
    assert w.startswith("Matches your search") and "rag" in w
    assert scout.why_relevant("zzz", "x/y", "unrelated", 1) == "Top match for your search"
    assert scout.why_relevant("zzz", "x/y", "unrelated", 9) == "Related to your search"


def test_why_relevant_whole_word_and_ignores_qualifiers():
    """RS24: 'ai' must not match inside 'email'; topic:/language: and negated -terms are never claimed."""
    assert scout.why_relevant("ai chat", "me/mailer", "a fast email client", 0) == "Top match for your search"
    assert scout.why_relevant("ios app -topic:macos", "a/b", "a macOS and iOS helper", 0) == 'Matches your search: "ios"'
    assert scout.why_relevant("rag chatbot", "me/rag", "a RAG chatbot", 0) == 'Matches your search: "rag", "chatbot"'


def test_duplicate_keeps_best_relevance_position():
    """RS5: a repo found by two queries is scored under its best (lowest) best-match position, not the first."""
    q1 = [repo(f"q1/r{i}", 1000) for i in range(5)] + [repo("x/dup", 1000)]  # x/dup at rel=5 here
    q2 = [repo("x/dup", 1000)]                                               # and rel=0 here
    res, _ = run([q1, q2])
    dup = next(r for r in res["all"] if r["full_name"] == "x/dup")
    assert dup["rel"] == 0 and dup["query"] == "q0"  # best rel, still grouped under the first finder (RS23)
    assert res["excluded"]["duplicate"] == 1


def test_freedom_tiers_rank_free_above_copyleft_above_none():
    """RS5: permissive > weak > GPL/AGPL > no licence (the last only with --license any)."""
    assert scout._freedom(scout.USE_PAID_OK) > scout._freedom(scout.USE_WEAK) > scout._freedom(scout.USE_SHARE)
    assert scout._freedom(scout.USE_SHARE) == scout._freedom(scout.USE_NETWORK) > scout._freedom(scout.USE_NONE)


def test_fit_starter_bonus_uses_per_query_floor():
    """RS15: a niche query's starter earns the nudge against *its* top repo, not a bigger query's."""
    big = [repo("big/lib", 100000)]
    niche = [repo("niche/lib", 2000), repo("niche/tpl", 500, is_template=True)]
    res, _ = run([big, niche], prefer_starters=True)
    names = [r["full_name"] for r in res["all"]]
    assert names.index("niche/tpl") < names.index("niche/lib")


@pytest.mark.parametrize("spdx,want", [
    ("MIT", "USE_PAID_OK"), ("Apache-2.0", "USE_PAID_OK"), ("CC0-1.0", "USE_PAID_OK"), ("BSD-3-Clause", "USE_PAID_OK"),
    ("MPL-2.0", "USE_WEAK"), ("LGPL-3.0", "USE_WEAK"),
    ("GPL-3.0", "USE_SHARE"), ("GPL-2.0", "USE_SHARE"), ("EUPL-1.2", "USE_SHARE"),
    ("AGPL-3.0", "USE_NETWORK"), ("OSL-3.0", "USE_NETWORK"),
    (None, "USE_NONE"), ("NOASSERTION", "USE_NONE"), ("CC-BY-NC-4.0", "USE_NONE"),
])
def test_license_use_plain_english(spdx, want):
    """RS14."""
    assert scout.license_use(spdx) == getattr(scout, want)


def test_every_open_license_has_a_label():
    """RS14: no open license falls through to 'no license'."""
    labelled = scout.PERMISSIVE | scout.WEAK_COPYLEFT | scout.STRONG_COPYLEFT | scout.NETWORK_COPYLEFT
    assert scout.OPEN_LICENSES <= labelled


def test_starter_detection_and_hint():
    """RS15."""
    res, _ = run([[repo("a/tpl", 3, is_template=True), repo("b/topic", 2, topics=["Boilerplate", "react"]),
                   repo("c/lib", 1, topics=["ui"])]])
    by = {r["full_name"]: r for r in res["candidates"]}
    assert by["a/tpl"]["starter"] and by["a/tpl"]["start_hint"] == scout.HINT_TEMPLATE
    assert by["b/topic"]["starter"] and by["b/topic"]["start_hint"] == scout.HINT_README
    assert not by["c/lib"]["starter"]


def test_prefer_starters_within_each_query():
    """RS15: starters first inside a query; balanced rounds still apply across queries."""
    q0 = [repo("lib/big", 50000), repo("tpl/small", 6000, is_template=True)]
    q1 = [repo("other/x", 7000)]
    res, _ = run([q0, q1], prefer_starters=True, rank_mode="balanced")
    assert [r["full_name"] for r in res["candidates"]] == ["other/x", "tpl/small", "lib/big"]
    res, _ = run([q0, q1], rank_mode="balanced")
    assert [r["full_name"] for r in res["candidates"]] == ["lib/big", "other/x", "tpl/small"]


def test_tiny_starter_does_not_jump_a_popular_library():
    """RS15: live regression, a 65-star template outranked a 12,992-star animation library."""
    q = [repo("barbajs/barba", 12992), repo("tiny/tpl", 65, is_template=True), repo("ok/tpl", 1300, is_template=True)]
    res, _ = run([q], prefer_starters=True, rank_mode="balanced")
    assert [r["full_name"] for r in res["candidates"]] == ["ok/tpl", "barbajs/barba", "tiny/tpl"]


def test_text_and_markdown_show_labels_and_key():
    """RS10, RS14, RS15, RS17."""
    res, _ = run([[repo("a/tpl", 3, spdx="AGPL-3.0", is_template=True)]], license_mode="open")
    txt, md = scout.render(res), scout.render_markdown(res)
    for out in (txt, md):
        assert scout.USE_NETWORK in out and scout.HINT_TEMPLATE.replace("'", "") in out.replace("'", "").replace("\\", "")
        assert "stars can be bought" in out and "not legal advice" in out
        assert "fit" in out
    assert "[starter]" in txt and "| yes |" in md
    empty, _ = run([[]])
    assert "stars can be bought" in scout.render(empty) and "stars can be bought" in scout.render_markdown(empty)


def test_cli_rank_and_starter_flags(monkeypatch, capsys):
    """RS5, RS15."""
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 500)]})
    assert scout.main(["--rank", "stars", "--prefer-starters", "--json", "x"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["rank_mode"] == "stars" and data["prefer_starters"] is True


def test_skill_vibe_coder_rules():
    """RS16, RS17, RS14, RS15."""
    skill = (ROOT / "skills" / "find" / "SKILL.md").read_text()
    assert "-topic:macos" in skill and "--prefer-starters" in skill
    assert "winget install Python.Python.3.12" in skill and "Add python.exe to PATH" in skill
    assert "license_use" in skill and "start_hint" in skill and "stars can be bought" in skill


def test_workflow_passes_rank_and_starters_via_env():
    """RS13, RS5, RS15."""
    wf = (ROOT / ".github" / "workflows" / "find.yml").read_text()
    assert "RANK: ${{ inputs.rank }}" in wf and "PREFER_STARTERS: ${{ inputs.prefer_starters }}" in wf
    assert '"--rank", os.environ["RANK"]' in wf


def test_top_and_candidates_limits():
    """RS5."""
    res, _ = run([[repo(f"o/r{i}", 1000 - i) for i in range(20)]], top=3, candidates=10)
    assert len(res["top"]) == 3 and len(res["candidates"]) == 10


def test_query_always_excludes_forks_and_archived():
    """RS2."""
    _, f = run([[]])
    assert f.calls[0][0] == "q0 fork:false archived:false is:public"


def test_forks_archived_disabled_excluded():
    """RS2."""
    res, _ = run([[repo("a/f", 9, fork=True), repo("a/z", 9, archived=True), repo("a/d", 9, disabled=True),
                   repo("a/ok", 1)]])
    assert [r["full_name"] for r in res["top"]] == ["a/ok"]
    assert res["excluded"]["fork_or_archived"] == 3


@pytest.mark.parametrize("spdx", [None, "NOASSERTION", "CC-BY-NC-4.0", "SSPL-1.0"])
def test_non_open_license_excluded_by_default(spdx):
    """RS3."""
    res, _ = run([[repo("a/x", 9, spdx=spdx), repo("a/ok", 1, spdx="Apache-2.0")]])
    assert [r["full_name"] for r in res["top"]] == ["a/ok"]
    assert res["excluded"]["license"] == 1


def test_license_any_keeps_and_flags_unlicensed():
    """RS3."""
    res, _ = run([[repo("a/none", 9, spdx=None), repo("a/nc", 8, spdx="CC-BY-NC-4.0"), repo("a/mit", 1)]],
                 license_mode="any")
    by = {r["full_name"]: r for r in res["top"]}
    assert "all rights reserved" in by["a/none"]["license"] and not by["a/none"]["open_license"]
    assert "not an open-source license" in by["a/nc"]["license"]
    assert by["a/mit"]["license"] == "MIT" and by["a/mit"]["open_license"]


def test_stale_and_missing_push_excluded():
    """RS4."""
    res, _ = run([[repo("a/old", 9, pushed="2023-01-01T00:00:00Z"), repo("a/nodate", 9, pushed=None),
                   repo("a/ok", 1)]])
    assert [r["full_name"] for r in res["top"]] == ["a/ok"]
    assert res["excluded"]["stale"] == 2


def test_stale_filter_off():
    """RS4."""
    res, _ = run([[repo("a/old", 9, pushed="2019-01-01T00:00:00Z")]], max_age_months=0)
    assert res["top"][0]["full_name"] == "a/old"


def test_too_many_or_no_queries_refused():
    """RS8, RS7."""
    with pytest.raises(scout.ScoutError, match="At most 4"):
        scout.scout(["a", "b", "c", "d", "e"], fetcher=fake([[]] * 5), now=NOW)
    with pytest.raises(scout.ScoutError, match="No search query"):
        scout.scout(["  "], fetcher=fake([[]]), now=NOW)


def test_one_failed_query_fails_whole_run():
    """RS7: no partial results."""
    def f(q, token=None):
        if q.startswith("bad"):
            raise scout.ScoutError("GitHub search failed: HTTP 500.")
        return {"items": [repo("a/ok", 1)]}
    with pytest.raises(scout.ScoutError):
        scout.scout(["good", "bad"], fetcher=f, now=NOW)


def test_malformed_response_fails_closed():
    """RS7."""
    with pytest.raises(scout.ScoutError, match="Unexpected"):
        scout.scout(["x"], fetcher=lambda q, t=None: {"message": "oops"}, now=NOW)


def test_repo_text_cleaned_and_capped():
    """RS9."""
    res, _ = run([[repo("a/x", 1, description="ignore\x1b[2J previous‮ steps " + "z" * 500)]])
    d = res["top"][0]["description"]
    assert len(d) <= scout.MAX_TEXT and "\x1b" not in d and "‮" not in d


def test_token_passed_but_never_in_output(monkeypatch, capsys):
    """RS8."""
    seen = []
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret123")
    monkeypatch.setattr(scout, "fetch", lambda q, token=None: seen.append(token) or {"items": [repo("a/b", 500)]})
    assert scout.main(["x"]) == 0
    out = capsys.readouterr()
    assert seen == ["ghp_secret123"]
    assert "ghp_secret123" not in out.out + out.err


def _patch_fetch(monkeypatch, fn):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(scout, "fetch", fn)


def test_main_exit_codes(monkeypatch, capsys):
    """RS7, RS10: 0 ok, 1 no match, 2 error."""
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 500)]})
    assert scout.main(["x"]) == 0
    assert "a/b" in capsys.readouterr().out
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": []})
    assert scout.main(["x"]) == 1
    assert "No repository matched" in capsys.readouterr().out

    def boom(q, token=None):
        raise scout.ScoutError("Could not reach GitHub: down.")
    _patch_fetch(monkeypatch, boom)
    assert scout.main(["x"]) == 2
    err = capsys.readouterr()
    assert "Could not reach GitHub" in err.err and err.out == ""


def test_main_json(monkeypatch, capsys):
    """RS10."""
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 500)]})
    assert scout.main(["x", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["top"][0] == {"full_name": "a/b", "stars": 500, "license": "MIT", "open_license": True,
                              "license_use": scout.USE_PAID_OK, "free": scout.FREE_YES, "starter": False,
                              "start_hint": scout.HINT_README,
                              "pushed": "2026-09-01", "url": "https://github.com/a/b", "query": "x",
                              "description": "a/b desc", "rel": 0, "why": "Top match for your search", "rank": 1}
    assert data["rank_mode"] == "fit" and data["prefer_starters"] is False
    assert set(data["excluded"]) == {"fork_or_archived", "license", "stale", "low_stars", "duplicate"}
    assert data["min_stars"] == 50


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_builds_request_and_maps_errors(monkeypatch):
    """RS2, RS7, RS8: the real fetch, with urlopen stubbed."""
    got = {}

    def ok(req, timeout):
        got["url"], got["auth"] = req.full_url, req.get_header("Authorization")
        return _Resp(b'{"items": []}')
    monkeypatch.setattr(scout.urllib.request, "urlopen", ok)
    assert scout.fetch("gsap fork:false", token="t0k") == {"items": []}
    assert "per_page=30" in got["url"] and "sort=stars" not in got["url"] and got["auth"] == "Bearer t0k"

    def http(code, remaining=None):
        def f(req, timeout):
            raise urllib.error.HTTPError(req.full_url, code, "x", {"X-RateLimit-Remaining": remaining}, None)
        return f
    for fn, msg in [(http(403, "0"), "rate limit"), (http(422), "rejected"), (http(500), "HTTP 500")]:
        monkeypatch.setattr(scout.urllib.request, "urlopen", fn)
        with pytest.raises(scout.ScoutError, match=msg):
            scout.fetch("q")

    def down(req, timeout):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(scout.urllib.request, "urlopen", down)
    with pytest.raises(scout.ScoutError, match="Could not reach"):
        scout.fetch("q")
    monkeypatch.setattr(scout.urllib.request, "urlopen", lambda r, timeout: _Resp(b"<html>"))
    with pytest.raises(scout.ScoutError, match="not JSON"):
        scout.fetch("q")


def test_stdlib_only_and_no_model_calls():
    """RS1, RS11."""
    src = (ROOT / "scripts" / "scout.py").read_text()
    imports = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_]+)", src, re.M))
    assert imports <= {"argparse", "csv", "datetime", "http", "io", "json", "math", "os", "re", "sys", "urllib"}, imports
    assert not re.search(r"anthropic|openai|claude", src, re.I)


def test_skill_calls_real_script():
    """RS1."""
    skill = (ROOT / "skills" / "find" / "SKILL.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/scripts/scout.py" in skill
    assert (ROOT / "scripts" / "scout.py").exists()


def test_skill_asks_for_task_when_no_description():
    """RS1a."""
    skill = (ROOT / "skills" / "find" / "SKILL.md").read_text()
    front = skill.split("---")[1]
    assert "argument-hint:" in front
    assert "$ARGUMENTS" in skill
    assert "What are you building, or what task do you need a GitHub repo for?" in skill
    assert skill.index("RS1a") < skill.index("scripts/scout.py"), "must ask before running the search"


def test_markdown_summary_escapes_repo_text():
    """RS13, RS9: repo text cannot inject Markdown, HTML or links into the job summary."""
    res, _ = run([[repo("a/ok", 5, description="<img src=x> [click](http://evil) | **bold**"),
                   repo("b/odd", 3)]])
    res["top"][1]["full_name"] = "b/odd](http://evil)"
    md = scout.render_markdown(res)
    assert "\\<img src=x\\>" in md and "\\*\\*bold\\*\\*" in md and "\\|" in md
    assert re.search(r"(?<!\\)<img", md) is None
    assert "](http://evil)" not in md
    assert "[a/ok](https://github.com/a/ok)" in md
    assert "| 1 |" in md and "semantic relevance check" in md


def test_markdown_no_match(monkeypatch, capsys):
    """RS13, RS7."""
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": []})
    assert scout.main(["--markdown", "x"]) == 1
    assert "No repository matched" in capsys.readouterr().out


def test_workflow_passes_inputs_via_env_only():
    """RS13: workflow inputs never interpolated into the shell script."""
    wf = (ROOT / ".github" / "workflows" / "find.yml").read_text()
    run_block = wf.split("run: |", 1)[1]
    assert "${{" not in run_block
    assert "workflow_dispatch" in wf and "contents: read" in wf
    assert '"--", *queries' in run_block


def test_min_stars_filter_and_cli_default(monkeypatch, capsys):
    """RS4a: live 'diet app' run put 41- and 48-star repos in the top 3."""
    res, _ = run([[repo("wger/wger", 7104), repo("tiny/a", 41)], [repo("tiny/b", 48)]], min_stars=50)
    assert [r["full_name"] for r in res["candidates"]] == ["wger/wger"]
    assert res["excluded"]["low_stars"] == 2
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("tiny/a", 49)]})
    assert scout.main(["x"]) == 1
    assert "low_stars=1" in capsys.readouterr().out
    assert scout.main(["--min-stars", "0", "x"]) == 0


def test_long_query_refused_before_network():
    """RS19: live run, a pasted sentence got HTTP 422 from GitHub."""
    calls = []
    long_q = "i want to build a really nice looking app " * 6
    with pytest.raises(scout.ScoutError, match="too long.*1-3 keywords"):
        scout.scout([long_q], fetcher=lambda q, t=None: calls.append(q) or {"items": []}, now=NOW)
    assert calls == []


def test_error_names_user_query_not_qualifiers():
    """RS19: messages never show the added fork/archived qualifiers."""
    def f(q, token=None):
        raise scout.ScoutError("GitHub rejected it (HTTP 422). Use 1-3 keywords per search.")
    with pytest.raises(scout.ScoutError) as e:
        scout.scout(["calorie counter"], fetcher=f, now=NOW)
    assert "'calorie counter'" in str(e.value) and "fork:false" not in str(e.value)


def test_workflow_fails_on_error_but_not_on_no_match():
    """RS19: live runs showed errors as green because the default shell had no pipefail."""
    wf = (ROOT / ".github" / "workflows" / "find.yml").read_text()
    step = wf.split("- name: Search GitHub", 1)[1]
    assert "shell: bash" in step
    assert "sys.exit(0 if code == 1 else code)" in step
    assert "MIN_STARS: ${{ inputs.min_stars }}" in step and '"--min-stars", os.environ["MIN_STARS"]' in step


def test_skill_edge_case_rules():
    """RS1b, RS18, RS19."""
    skill = (ROOT / "skills" / "find" / "SKILL.md").read_text()
    assert "diet app" in skill and "Do not block on a question" in skill
    assert "Do you mean learning security / testing an app you own, or a hackathon project?" in skill
    assert "Only test systems you own or have written permission to test." in skill
    for word in ("account takeover", "stalkerware", "credential stealers", "keygens", "generators"):
        assert word in skill
    assert "only finds open-source code on GitHub" in skill


def test_defaults_are_top20_with_40_candidates():
    """RS29: top 20, shortlist 40 so the relevance gate can drop and still have 20."""
    res, _ = run([[repo(f"o/r{i}", 1000 - i) for i in range(50)]])
    assert len(res["top"]) == 20 and len(res["candidates"]) == 40


@pytest.mark.parametrize("spdx,want", [("MIT", "FREE_YES"), ("MPL-2.0", "FREE_WEAK"), ("GPL-3.0", "FREE_SHARE"),
                                       ("AGPL-3.0", "FREE_SHARE"), (None, "FREE_NO"), ("NOASSERTION", "FREE_NO")])
def test_completely_free_from_license(spdx, want):
    """RS20."""
    assert scout.free_text(spdx) == getattr(scout, want)


def test_csv_output_rows_and_formula_guard(monkeypatch, capsys):
    """RS20: CSV for Excel/Sheets; repo text starting with = is not run as a formula."""
    import csv as _csv
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [
        repo("a/b", 900, description="=HYPERLINK(evil)"), repo("c/d", 800, spdx="GPL-3.0")]})
    assert scout.main(["--csv", "x"]) == 0
    rows = list(_csv.reader(capsys.readouterr().out.splitlines()))
    assert rows[0] == scout.CSV_FIELDS
    assert rows[1][1] == "a/b" and rows[1][4] == "900" and rows[1][7] == scout.FREE_YES
    assert rows[1][12].startswith("'=")
    assert rows[2][7] == scout.FREE_SHARE and len(rows) == 3


def test_markdown_top_table_then_extra_candidates_and_free_note():
    """RS20, RS10: top 20 printed once, the rest under 'More candidates'."""
    res, _ = run([[repo(f"o/r{i}", 1000 - i) for i in range(30)]])
    md = scout.render_markdown(res)
    assert "### Top 20" in md and "### More candidates" in md
    assert md.count("[o/r0]") == 1 and "[o/r29]" in md
    assert "Completely free?" in md and scout.FREE_NOTE in md
    small, _ = run([[repo("a/b", 900)]], top=10)
    assert "More candidates" not in scout.render_markdown(small)


def test_skill_comparison_table_and_prompt_fields():
    """RS20, RS21."""
    skill = (ROOT / "skills" / "find" / "SKILL.md").read_text()
    for col in ("What it does", "Relevance", "OK in a paid product?", "Completely free?", "How to start"):
        assert col in skill
    assert "up to 20" in skill and "Stop when you have 20" in skill
    for field in ("What I'm building", "Platform", "Stack", "Selling it?", "Starting from scratch?"):
        assert field in skill


def test_readme_has_prompt_examples_and_template():
    """RS21."""
    readme = (ROOT / "README.md").read_text()
    assert "## Example prompts" in readme and "## Prompt template" in readme
    for goal in ("Website", "Mobile app", "AI agent", "Data", "Games", "Learning"):
        assert f"**{goal}" in readme


def test_csv_block_under_markdown_cannot_break_fence(monkeypatch, capsys):
    """RS20, RS9: one search, CSV fenced under the summary; repo text with ``` can't close the fence."""
    fence = chr(96) * 3
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 900, description=fence + " x")]})
    assert scout.main(["--markdown", "--csv-block", "x"]) == 0
    out = capsys.readouterr().out
    assert "## CSV" in out and out.count(fence) == 2 and out.rstrip().endswith(fence)


def test_workflow_csv_option():
    """RS20, RS13."""
    wf = (ROOT / ".github" / "workflows" / "find.yml").read_text()
    assert "CSV: ${{ inputs.csv }}" in wf and '["--csv-block"] if os.environ["CSV"] == "true"' in wf


def test_web_page_is_safe_static(monkeypatch):
    """RS22: no embedded secret, no external scripts, uses the public search API, logic mirrors the script."""
    html = (ROOT / "web" / "index.html").read_text()
    # no key or token anywhere: the page never asks for, stores, or embeds one
    import re as _re
    assert not _re.search(r"gh[pousr]_[A-Za-z0-9]{20,}", html), "looks like a real token is embedded"
    assert not _re.search(r"github_pat_[A-Za-z0-9_]{20,}", html)
    assert 'id="token"' not in html and "findrepo_gh_token" not in html
    assert "models.github" not in html and "Authorization" not in html
    # only external script allowed: GSAP from cdnjs, pinned to an exact version; page degrades without it
    srcs = _re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert srcs == ["https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"], srcs
    assert "unpkg" not in html.lower() and "jsdelivr" not in html.lower()
    # any external stylesheet must be Google Fonts (Inter), degrades to system
    sheets = _re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
    assert all(h.startswith("https://fonts.googleapis.com/") for h in sheets), sheets
    # calls the public search API in best-match order (RS2), forks/archived excluded; fit ranking (RS5) re-ranks
    assert "api.github.com/search/repositories" in html
    assert "fork:false archived:false is:public" in html
    assert "sort=stars" not in html  # RS5: best-match seeds fit ranking; stars no longer forced on the fetch
    assert "rankByFit" in html and "fitScore" in html
    assert "whyRelevant" in html and "Matches your words" in html  # RS24: each card says why it is relevant
    # license sets kept in sync with scout.py
    assert all(l in html for l in ("AGPL-3.0", "MPL-2.0", "MIT", "Unlicense"))
    assert "STARTER_MIN_SHARE" in html and "0.10" in html
    assert "max 200 characters" in html  # RS19 length guard
    # RS24 cards surface the license meaning, free answer and starter flag (short labels + full text in titles)
    assert "OK to use in a paid product" in html and "Starter" in html and "Completely free?" in html
    # RS21 clickable example prompts (quick-picks under the search bar) fill the box and run
    assert 'id="quickpicks"' in html and "EXAMPLES" in html and "buildQuickpicks" in html
    assert "function pickExample" in html and "pickExample(ex)" in html
    # RS23 PRD upload is client-side only (FileReader, never uploaded)
    assert 'id="prd"' in html and "FileReader" in html and "prdFeatures" in html
    assert "never uploaded" in html
    # RS22: how-to-run-in-Claude-Code and the >10 edge-case CTA both point to the plugin
    assert "/plugin install replore@replore" in html and "/replore:find" in html
    assert "Use the plugin" in html and "PLUGIN_CTA" in html
    # RS31/RS32: the plugin modal has two tabs — Claude Code one-command, and any other agent via MCP / AGENTS.md
    assert 'data-tab="cc"' in html and 'data-tab="other"' in html and "mcp_server.py" in html and "AGENTS.md" in html
    assert "passed the filters" in html  # the "want every suitable repo?" plugin banner
    # RS29c (retired): the per-results keyword-search banner is gone
    assert "LEXICAL_NOTE" not in html
    # RS29: the redundant "Paid-use OK"/"Completely free" filter chips are collapsed into one commercial-use chip
    assert "Free for commercial use" in html and "data-com=" in html
    assert 'data-paid=' not in html and 'data-free=' not in html
    # RS30: a "Next steps" menu item opens a guidance modal (no model call, points to the plugin)
    assert 'id="nextBtn"' in html and 'id="nextModal"' in html and "Next steps" in html
    assert "Generate plan" in html and "Build it with your AI agent" in html
    # RS27a: similar-repo requires text and is narrowed by it (no silent drop); "find similar" alone is blocked
    assert "RS27a" in html and "· matching" in html and "Add a few words too" in html
    # RS29: a persistent "Clear filter" button appears when a non-All filter is active
    assert 'id="resClearBtn"' in html and "Clear filter" in html
    # search-bar ✕ resets everything (text, similar repo, filters, picks, results) — shared with the logo
    assert 'id="clearQ"' in html and "function resetAll" in html and 'addEventListener("click",resetAll)' in html
    # light/dark toggle (RS24)
    assert 'id="theme"' in html and "data-theme" in html and "findrepo_theme" in html
    # RS24 Tour: a current screenshot of the live page is committed and embedded (replaces the stale gif)
    assert 'src="tour.png"' in html and (ROOT / "web" / "tour.png").exists()
    # RS28 select-to-PRD hand-off: no model call/key; copy + deep-link to the user's own Claude
    assert 'class="pick-cb"' in html and 'id="prdModal"' in html and 'id="prdPrompt"' in html
    assert "claude.ai/new?q=" in html and "Copy prompt" in html
    # RS24 richness: cursor tilt + star count-up are native (no extra library)
    assert "attachTilt" in html and 'class="cnt"' in html
    for t in ("portfolio website", "iPhone app", "trip planner", "practice app"):
        assert t in html


def test_pages_workflow_present():
    """RS22."""
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "upload-pages-artifact" in wf and "path: web" in wf and "deploy-pages" in wf


def test_all_uncaps_and_groups_by_feature():
    """RS23: --all returns every match; groups hold each feature's repos, deduped to the first finder."""
    pages = [[repo("auth/a", 900), repo("shared/x", 500)], [repo("pay/a", 700), repo("shared/x", 500)]]
    res, _ = run(pages, queries=["user auth", "payments"], top=None, candidates=None)
    assert len(res["all"]) == 3  # shared/x counted once
    assert [g["query"] for g in res["groups"]] == ["user auth", "payments"]
    assert [r["full_name"] for r in res["groups"][0]["repos"]] == ["auth/a", "shared/x"]  # first finder keeps it
    assert [r["full_name"] for r in res["groups"][1]["repos"]] == ["pay/a"]


def test_grouped_markdown_sections_and_counts():
    """RS23."""
    pages = [[repo("a/1", 900)], [repo("b/1", 800), repo("b/2", 700)]]
    res, _ = run(pages, queries=["login", "billing"], top=None, candidates=None)
    md = scout.render_markdown_grouped(res)
    assert "### login  (1)" in md and "### billing  (2)" in md
    assert "3 open-source repos across 2 needs" in md and scout.FREE_NOTE in md


def test_cli_all_and_group(monkeypatch, capsys):
    """RS23."""
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 500)]})
    assert scout.main(["--all", "--json", "x"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "groups" in data and data["top"] == data["all"]
    _patch_fetch(monkeypatch, lambda q, token=None: {"items": [repo("a/b", 500)]})
    assert scout.main(["--markdown", "--group", "x"]) == 0
    assert "grouped by need" in capsys.readouterr().out


def test_workflow_all_group_options():
    """RS23."""
    wf = (ROOT / ".github" / "workflows" / "find.yml").read_text()
    assert "ALL: ${{ inputs.all }}" in wf and "GROUP: ${{ inputs.group }}" in wf
    assert '["--all"] if os.environ["ALL"]' in wf and '["--group"] if os.environ["GROUP"]' in wf



def test_privacy_notice_matches_what_the_code_does():
    """RS33: the published privacy claims stay true — CI fails if a data flow is added without updating them."""
    html = (ROOT / "web" / "index.html").read_text()
    priv = (ROOT / "PRIVACY.md").read_text()
    readme = (ROOT / "README.md").read_text()
    assert 'id="privacyModal"' in html and "PRIVACY.md" in html and "privacy-note" in html
    assert "PRIVACY.md" in readme and "not legal advice" in priv and "Last updated" in priv
    # "no cookies / no analytics / no tracking" must stay literally true
    for banned in ("document.cookie", "sessionStorage", "indexedDB", "gtag(", "googletagmanager", "plausible",
                   "sendBeacon", "posthog", "umami", "analytics.js"):
        assert banned not in html, banned
    # only these hosts are contacted; PRIVACY.md names each of them
    hosts = set(re.findall(r"https://([a-z0-9.-]+)", html))
    allowed = {"api.github.com", "github.com", "fonts.googleapis.com", "fonts.gstatic.com", "cdnjs.cloudflare.com",
               "claude.ai", "claude.com", "replore.pages.dev"}
    assert hosts <= allowed, hosts - allowed
    for named in ("api.github.com", "Google Fonts", "cdnjs", "Cloudflare", "claude.ai", "security.log", "200 characters"):
        assert named in priv, named
    # the hook really writes only on a match, at most 200 chars, locally
    hook = (ROOT / "hooks" / "security_log.py").read_text()
    assert "if not hits:" in hook and "text[:200]" in hook and "urllib" not in hook
