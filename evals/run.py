#!/usr/bin/env python3
"""Goal-based eval suite for Find Repo's fit ranking (SPEC RS5).

Unit tests (tests/) lock exact orderings; these evals measure the *product goal*:
does a vibe coder get the repo they actually want at #1 — relevant AND popular AND
free to use — across hand-labelled scenarios? Weights can move without breaking the
goal, as long as the top pick stays right.

Offline and stdlib-only. It scores the plugin's fit ranking (scripts/scout.py); the web
page uses the identical formula, and that parity is locked by tests/test_web_logic.js.

Run: python evals/run.py   (exit 0 if the pass rate meets the threshold, else 1)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scout  # noqa: E402


def _to_repo(c):
    return {
        "full_name": c["name"],
        "stars": c["stars"],
        "rel": c.get("rel", 0),
        "starter": c.get("starter", False),
        "license_use": scout.license_use(c.get("spdx")),
    }


def _rank(candidates, prefer_starters):
    rows = [_to_repo(c) for c in candidates]
    floor = max((r["stars"] for r in rows), default=0) * scout.STARTER_MIN_SHARE
    return sorted(rows, key=lambda r: (-scout.fit_score(r, prefer_starters, floor), -r["stars"], r["full_name"]))


def main():
    data = json.loads((Path(__file__).parent / "fit_cases.json").read_text())
    cases, threshold = data["cases"], data.get("threshold", 1.0)
    passed = 0
    print(f"Find Repo — fit-ranking eval ({len(cases)} goal cases)\n")
    for c in cases:
        ranked = _rank(c["candidates"], c.get("prefer_starters", False))
        top = ranked[0]["full_name"]
        ok = top == c["expect_top"]
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {c['name']}")
        if not ok:
            print(f"       goal: {c['goal']}")
            print(f"       expected #1 {c['expect_top']!r}, got {top!r}")
            print(f"       order: {[r['full_name'] for r in ranked]}")
    score = passed / len(cases) if cases else 0.0
    print(f"\nScore: {passed}/{len(cases)} = {score:.0%} (threshold {threshold:.0%})")
    return 0 if score >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
