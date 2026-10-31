"""Auditor agent: independently prove the books are right, or block the close.

It does not trust the other agents. It recomputes everything from the raw
sources and checks invariants that must hold to the cent:

  1. every source row is accounted for exactly once
  2. ledger vs processor difference == sum of open exception impacts
  3. payouts vs bank difference == sum of open bank exception impacts
  4. each processor payout equals the net of the transactions it settled
  5. every auto-fix is allowed by the owner's policy and within its cap
  6. no double posting: one fix per exception, unique fix ids, only for
     auto-fixed or human-approved exceptions
  7. all money is integer cents
  8. the owner's original ledger file was not modified
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .fixer import FIXED, FixEntry
from .ingest import Dataset
from .matcher import MatchResult, in_scope_ledger, in_scope_payouts, in_scope_txns, payout_key
from .models import Exception_, money
from .policy import Policy


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class AuditReport:
    checks: list[Check] = field(default_factory=list)
    diff_before: int = 0
    diff_after: int = 0
    open_impact: int = 0
    bank_diff: int = 0
    bank_open_impact: int = 0
    processor_net: int = 0
    ledger_before: int = 0
    ledger_after: int = 0

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(Check(name, bool(ok), detail))


def audit(ds: Dataset, mr: MatchResult, exceptions: list[Exception_], fixes: list[FixEntry], policy: Policy,
          ledger_hash_before: str = "", ledger_hash_after: str = "") -> AuditReport:
    r = AuditReport()

    # 1. conservation
    seen: Counter[str] = Counter()
    for m in mr.matches:
        seen[m.left] += 1
        seen[m.right] += 1
    for x in exceptions:
        for ref in x.refs:
            if not ref.startswith("fees:"):
                seen[ref] += 1
    for i in mr.out_of_scope:
        seen[i] += 1
    fee_batches = {x.refs[0] for x in exceptions if x.cause == "processor_fee"}
    all_batches = {"fees:" + (t.payout_id or f"pending:{t.processor}") for t in in_scope_txns(ds)}
    for e in mr.ledger_fee_entries:
        if ("fees:" + e.reference) in all_batches:
            seen[e.id] += 1
    universe = [e.id for e in ds.ledger] + [t.id for t in in_scope_txns(ds)] \
        + [payout_key(p) for p in in_scope_payouts(ds)] + [b.id for b in ds.bank]
    missing = [u for u in universe if seen[u] == 0]
    double = [u for u in universe if seen[u] > 1]
    r.add("conservation", not missing and not double,
          f"{len(universe)} source rows: {len(missing)} unaccounted, {len(double)} counted twice"
          + (f" (e.g. {(missing + double)[:3]})" if missing or double else ""))

    # 2. ledger vs processor, to the cent
    ledger = in_scope_ledger(ds)
    r.processor_net = sum(t.net for t in in_scope_txns(ds))
    r.ledger_before = sum(e.amount for e in ledger)
    r.ledger_after = r.ledger_before + sum(f.amount for f in fixes)
    r.diff_before = r.processor_net - r.ledger_before
    r.diff_after = r.processor_net - r.ledger_after
    proc = [x for x in exceptions if x.side == "processor"]
    explained_before = sum(x.impact for x in proc)
    r.open_impact = sum(x.impact for x in proc if not (x.status in FIXED and x.proposed_entry))
    r.add("every ringgit explained (before fixes)", explained_before == r.diff_before,
          f"difference {money(r.diff_before)} vs sum of exception impacts {money(explained_before)}")
    r.add("every ringgit explained (after fixes)", r.open_impact == r.diff_after,
          f"remaining difference {money(r.diff_after)} vs open exceptions {money(r.open_impact)}")

    # 3. payouts vs bank
    payouts_total = sum(-p.amount for p in in_scope_payouts(ds))
    bank_ids = {m.right for m in mr.matches if m.kind == "payout-bank"} | {b.id for b in mr.unmatched_bank}
    bank_total = sum(b.amount for b in ds.bank if b.id in bank_ids)
    r.bank_diff = payouts_total - bank_total
    r.bank_open_impact = sum(x.impact for x in exceptions if x.side == "bank")
    r.add("payouts reconcile to bank", r.bank_diff == r.bank_open_impact,
          f"payouts {money(payouts_total)} - bank {money(bank_total)} = {money(r.bank_diff)}, "
          f"explained by bank exceptions {money(r.bank_open_impact)}")

    # 4. processor's own numbers are internally consistent
    settled: dict[str, int] = defaultdict(int)
    for t in ds.processor:
        if t.type != "payout" and t.payout_id:
            settled[t.payout_id] += t.net
    bad = [payout_key(p) for p in ds.processor if p.type == "payout" and settled.get(payout_key(p), 0) != -p.amount]
    r.add("payouts equal net of settled transactions", not bad,
          "all payouts tie out" if not bad else f"payouts not tying out: {bad[:3]}")

    # 5. policy compliance
    violations = []
    for x in exceptions:
        if x.status == "auto_fixed":
            cap = policy.auto_fix.get(x.cause)
            if cap is None or abs(x.impact) > cap or x.blocked or x.confidence < policy.min_auto_confidence:
                violations.append(x.id)
    r.add("auto-fixes within owner policy", not violations,
          f"{sum(x.status == 'auto_fixed' for x in exceptions)} auto-fixes checked against policy "
          f"{policy.sha256[:10]}" + (f"; violations {violations}" if violations else ""))

    # 6. no double posting
    ids = [f.id for f in fixes]
    per_exc = Counter(f.exception_id for f in fixes)
    allowed = {x.id for x in exceptions if x.status in FIXED and x.proposed_entry}
    rogue = [f.id for f in fixes if f.exception_id not in allowed]
    r.add("no double posting", len(ids) == len(set(ids)) and max(per_exc.values(), default=1) == 1 and not rogue,
          f"{len(fixes)} fix entries, unique, one per approved/auto exception"
          + (f"; rogue {rogue}" if rogue else ""))

    # 7. integer cents
    amounts = [e.amount for e in ds.ledger] + [t.amount for t in ds.processor] + [t.fee for t in ds.processor] \
        + [b.amount for b in ds.bank] + [f.amount for f in fixes] + [x.impact for x in exceptions]
    r.add("integer cents only", all(isinstance(a, int) for a in amounts), f"{len(amounts)} amounts checked")

    # 8. original ledger untouched
    if ledger_hash_before:
        r.add("original ledger untouched", ledger_hash_before == ledger_hash_after,
              f"sha256 {ledger_hash_before[:10]}… before and after")
    return r
