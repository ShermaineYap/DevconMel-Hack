"""The lead agent: run the crew in order, verify after every step, stop if anything fails."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import auditor, explainer, fixer, investigator, matcher
from .ingest import IngestError, load_sources
from .models import money
from .policy import load_policy
from .worklog import WorkLog

ROOT = Path(__file__).resolve().parent.parent


def home() -> Path:
    """Project folder holding sources.yaml, policy.yaml, data/ and state/ (override with CLOSECREW_HOME)."""
    return Path(os.environ.get("CLOSECREW_HOME", ROOT))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_approvals(state_dir: Path) -> dict:
    p = state_dir / "approvals.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_approvals(state_dir: Path, approvals: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "approvals.json").write_text(json.dumps(approvals, indent=2))


def run(config: str | Path | None = None, policy_path: str | Path | None = None,
        state_dir: str | Path | None = None, note: str = "", write_log: bool = True) -> dict:
    config = Path(config or home() / "sources.yaml")
    policy_path = Path(policy_path or home() / "policy.yaml")
    state_dir = Path(state_dir or home() / "state")
    log = WorkLog()
    policy = load_policy(policy_path)
    cfg = yaml.safe_load(config.read_text())
    ledger_path = config.parent / cfg["sources"]["ledger"]["path"]
    h_before = _sha(ledger_path)
    log.add("Lead", "start close", f"period {cfg['period']}; policy sha256 {policy.sha256[:10]}…" + (f"; {note}" if note else ""))

    t = time.perf_counter()
    try:
        ds = load_sources(config)
    except IngestError as e:
        log.add("Ingest", "FAILED", str(e), "stopped the run before matching", t)
        if write_log:
            log.flush(state_dir, "BLOCKED at ingest")
        raise
    log.add("Ingest", "loaded ledger, processor and bank in parallel",
            f"{len(ds.ledger)} ledger rows, {len(ds.processor)} processor txns, {len(ds.bank)} bank lines",
            "; ".join(ds.checks), t)

    t = time.perf_counter()
    mr = matcher.match(ds, policy)
    st = mr.stats()
    log.add("Matcher", "paired books with money",
            f"{st.get('exact', 0)} exact, {st.get('fuzzy', 0)} fuzzy, {len(mr.ref_pairs)} same-order amount gaps, "
            f"{len(mr.ambiguous)} ambiguous",
            "every pairing has a reason string; fuzzy pairs need amount equality", t)
    for m in mr.matches:
        if m.method == "fuzzy":
            log.add("Matcher", f"fuzzy match {m.left} ↔ {m.right}", m.reason, f"confidence {m.confidence:.2f}")

    t = time.perf_counter()
    exceptions = investigator.investigate(ds, mr, policy)
    log.add("Investigator", f"classified {len(exceptions)} exceptions",
            ", ".join(f"{c}×{n}" for c, n in sorted(_count(exceptions).items())),
            "each exception cites its source rows", t)
    for x in exceptions:
        log.add("Investigator", f"{x.id} {x.cause}", f"{money(x.impact)}: {x.evidence[0] if x.evidence else ''}")

    t = time.perf_counter()
    approvals = load_approvals(state_dir)
    fixes = fixer.decide(exceptions, policy, approvals, ds.period_end)
    rec_path, diff_path = fixer.write_outputs(ledger_path, fixes, state_dir)
    for x in exceptions:
        if x.status in ("auto_fixed", "approved", "open"):
            log.add("Fixer", f"{x.id} → {x.status.replace('_', ' ')}", x.decision_reason)
    log.add("Fixer", f"posted {len(fixes)} entries as a diff", f"{diff_path.name}; original ledger not edited",
            "", t)

    t = time.perf_counter()
    audit = auditor.audit(ds, mr, exceptions, fixes, policy, h_before, _sha(ledger_path))
    for c in audit.checks:
        log.add("Auditor", f"{'PASS' if c.ok else 'FAIL'} {c.name}", c.detail)
    log.add("Auditor", "verdict", f"{sum(c.ok for c in audit.checks)}/{len(audit.checks)} checks passed",
            "independent recomputation from raw sources", t)

    t = time.perf_counter()
    s = explainer.summary(audit, exceptions, fixes, st, len(matcher.in_scope_ledger(ds)), len(matcher.in_scope_txns(ds)))
    narration, source = explainer.narrative(s, exceptions)
    report = explainer.report_markdown(ds.period, s, audit, exceptions, fixes, narration)
    (state_dir / "close_report.md").write_text(report, encoding="utf-8")
    log.add("Explainer", "wrote close report", f"narration: {source}", "numbers taken only from the Auditor", t)
    log.add("Lead", f"status {s['status']}", f"difference {money(s['diff_before'])} → {money(s['diff_after'])}",
            "human approval required for everything outside policy")

    result = {
        "run_id": log.run_id, "period": ds.period, "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": s, "narration": narration, "narration_source": source,
        "exceptions": [x.to_dict() for x in exceptions],
        "fixes": [asdict(f) | {"date": f.date.isoformat()} for f in fixes],
        "matches": [asdict(m) for m in mr.matches],
        "audit": [asdict(c) for c in audit.checks],
        "policy": {"sha256": policy.sha256, "auto_fix": {k: v / 100 for k, v in policy.auto_fix.items()}},
        "diff": diff_path.read_text(), "log": [asdict(e) for e in log.entries],
    }
    (state_dir / "latest.json").write_text(json.dumps(result, indent=2, default=str))
    if write_log:
        log.flush(state_dir, f"{s['status']} · {money(s['diff_before'])} → {money(s['diff_after'])}")
    if os.environ.get("CLOSECREW_NOTIFY") == "telegram" and s["status"] != "CLOSED":
        from .telegram_bot import notify_summary
        notify_summary(result)
    return result


def decide(exc_id: str, status: str, by: str = "owner", note: str = "", **kw) -> dict:
    """Record a human decision, re-run the crew, and roll back if the Auditor objects."""
    assert status in ("approved", "rejected")
    state_dir = Path(kw.get("state_dir") or home() / "state")
    approvals = load_approvals(state_dir)
    previous = approvals.get(exc_id)
    approvals[exc_id] = {"status": status, "by": by, "note": note,
                         "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    save_approvals(state_dir, approvals)
    result = run(note=f"{by} {status} {exc_id}", **kw)
    if not all(c["ok"] for c in result["audit"]):
        if previous is None:
            approvals.pop(exc_id)
        else:
            approvals[exc_id] = previous
        save_approvals(state_dir, approvals)
        result = run(note=f"rolled back {exc_id}: auditor objected", **kw)
        result["rolled_back"] = exc_id
    elif status == "approved":
        from .actions import after_approval
        x = next((x for x in result["exceptions"] if x["id"] == exc_id), None)
        if x:
            result["action_result"] = after_approval(x)
    return result


def _count(exceptions) -> dict:
    out: dict[str, int] = {}
    for x in exceptions:
        out[x.cause] = out.get(x.cause, 0) + 1
    return out
