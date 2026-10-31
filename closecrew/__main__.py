"""CLI: python -m closecrew <command>

  seed [--seed N]           generate a fresh messy month of fake data into data/
  run                       run the whole crew and write state/
  pending                   list items waiting for a human
  approve EXC-ID [--by X]   approve one item (re-runs and re-audits; rolls back if audit fails)
  reject  EXC-ID [--by X]   reject one item
  report                    print the close report
  reset                     forget all approvals and outputs
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from . import pipeline
from .explainer import LABELS
from .models import money
from .seed import generate

ROOT = pipeline.home()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="closecrew", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["seed", "run", "pending", "approve", "reject", "report", "reset"])
    ap.add_argument("exc_id", nargs="?")
    ap.add_argument("--by", default="owner")
    ap.add_argument("--note", default="")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)

    if a.command == "seed":
        truth = generate(ROOT / "data", seed=a.seed)
        print(f"seeded data/ with {len(truth['exceptions'])} planted exceptions (seed {a.seed})")
        return 0
    if a.command == "reset":
        shutil.rmtree(ROOT / "state", ignore_errors=True)
        print("state/ cleared")
        return 0
    if a.command == "report":
        p = ROOT / "state" / "close_report.md"
        print(p.read_text() if p.exists() else "no report yet: run `python -m closecrew run`")
        return 0
    if a.command in ("approve", "reject"):
        if not a.exc_id:
            ap.error("give an exception id, e.g. EXC-1A2B3C4D")
        res = pipeline.decide(a.exc_id, "approved" if a.command == "approve" else "rejected", by=a.by, note=a.note)
        if res.get("rolled_back"):
            print(f"Auditor objected; decision on {a.exc_id} rolled back")
            return 1
        print(f"{a.exc_id} {a.command}d. " + res.get("action_result", ""))
        _print_summary(res)
        return 0

    res = pipeline.run()
    if a.command == "pending":
        items = [x for x in res["exceptions"] if x["status"] == "open"]
        for x in items:
            print(f"{x['id']}  {LABELS.get(x['cause'], x['cause']):34} {money(x['impact']):>12}  {x['explanation']}")
        print(f"{len(items)} item(s) awaiting approval")
        return 0
    _print_summary(res)
    return 0 if all(c["ok"] for c in res["audit"]) else 2


def _print_summary(res: dict) -> None:
    s = res["summary"]
    print(json.dumps({k: s[k] for k in ("status", "matched_total", "exceptions", "auto_fixed", "approved",
                                         "awaiting_approval", "checks_passed", "checks_total")}, indent=2))
    print(f"difference {money(s['diff_before'])} -> {money(s['diff_after'])}")
    for c in res["audit"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"] + ": " + c["detail"])


if __name__ == "__main__":
    sys.exit(main())
