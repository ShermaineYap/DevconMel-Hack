"""Fixer agent: propose journal entries, apply only what policy or a human allows.

It never edits the owner's original ledger. It writes a reconciled copy plus a
unified diff, so every change can be reviewed like a code change.
"""

from __future__ import annotations

import csv
import difflib
import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Exception_, LedgerEntry
from .policy import Policy

FIXED = ("auto_fixed", "approved")


@dataclass
class FixEntry:
    id: str
    exception_id: str
    date: date
    description: str
    reference: str
    amount: int
    kind: str
    applied_by: str  # policy | <human name>

    def as_ledger(self) -> LedgerEntry:
        return LedgerEntry(id=self.id, date=self.date, description=self.description, reference=self.reference,
                           amount=self.amount, kind=self.kind, method="card", source="fix", row=0)


def decide(exceptions: list[Exception_], policy: Policy, approvals: dict, period_end: date) -> list[FixEntry]:
    fixes: list[FixEntry] = []
    for x in exceptions:
        decision, reason = policy.decide(x.cause, x.impact, x.confidence, x.blocked)
        if decision == "auto" and not x.proposed_entry:
            decision, reason = "approval", "no safe ledger entry exists for this cause"
        x.decision, x.decision_reason = decision, reason
        human = approvals.get(x.id, {})
        if decision == "info":
            x.status = "info"
        elif decision == "auto":
            x.status = "auto_fixed"
        elif human.get("status") in ("approved", "rejected"):
            x.status = human["status"]
            x.decision_reason += f"; {human['status']} by {human.get('by', 'owner')}" + (
                f" ({human['note']})" if human.get("note") else "")
        else:
            x.status = "open"
        if x.status in FIXED and x.proposed_entry:
            pe = x.proposed_entry
            fixes.append(FixEntry(id="FIX-" + x.id.split("-", 1)[1], exception_id=x.id, date=period_end,
                                  description=pe["description"], reference=pe.get("reference", ""),
                                  amount=int(pe["amount"]), kind=pe["kind"],
                                  applied_by="policy" if x.status == "auto_fixed" else human.get("by", "owner")))
    return fixes


def write_outputs(ledger_path: Path, fixes: list[FixEntry], out_dir: Path) -> tuple[Path, Path]:
    """Write ledger_reconciled.csv (original + fixes) and ledger.diff. Original untouched."""
    out_dir.mkdir(parents=True, exist_ok=True)
    original = ledger_path.read_text(encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for f in sorted(fixes, key=lambda f: f.id):
        w.writerow([f.id, f.date.isoformat(), f.description, f.reference, f"{f.amount / 100:.2f}", f.kind,
                    "card", f"applied by {f.applied_by}"])
    reconciled = original.rstrip("\n") + "\n" + buf.getvalue()
    rec_path = out_dir / "ledger_reconciled.csv"
    rec_path.write_text(reconciled, encoding="utf-8")
    diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), reconciled.splitlines(keepends=True),
                                        fromfile=f"a/{ledger_path.name}", tofile="b/ledger_reconciled.csv"))
    diff_path = out_dir / "ledger.diff"
    diff_path.write_text(diff, encoding="utf-8")
    return rec_path, diff_path
