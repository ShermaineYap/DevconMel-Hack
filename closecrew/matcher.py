"""Matcher agent: pair the books with the money.

Three passes for ledger <-> processor (exact, same-reference, fuzzy with a
confidence score), then payouts <-> bank. Every pairing carries a reason
string so a human can see *why* two rows were tied together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ingest import Dataset
from .models import BankLine, LedgerEntry, Match, ProcessorTxn
from .policy import Policy


@dataclass
class MatchResult:
    matches: list[Match] = field(default_factory=list)
    ref_pairs: list[tuple[LedgerEntry, ProcessorTxn]] = field(default_factory=list)
    ambiguous: list[tuple[LedgerEntry, list[ProcessorTxn]]] = field(default_factory=list)
    unmatched_ledger: list[LedgerEntry] = field(default_factory=list)
    unmatched_txns: list[ProcessorTxn] = field(default_factory=list)
    unmatched_payouts: list[ProcessorTxn] = field(default_factory=list)
    unmatched_bank: list[BankLine] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    ledger_fee_entries: list[LedgerEntry] = field(default_factory=list)

    def stats(self) -> dict:
        by = {}
        for m in self.matches:
            by[m.method] = by.get(m.method, 0) + 1
        return by


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", s.lower()) if len(t) > 1}


def name_score(entry: LedgerEntry, txn: ProcessorTxn) -> float:
    want = _tokens(txn.customer)
    if not want:
        return 0.0
    have = _tokens(entry.description) | _tokens(entry.customer)
    return len(want & have) / len(want)


def payout_key(t: ProcessorTxn) -> str:
    return t.payout_id or t.id


def in_scope_ledger(ds: Dataset) -> list[LedgerEntry]:
    return [e for e in ds.ledger if e.method == "card" and ds.period_start <= e.date <= ds.period_end]


def in_scope_txns(ds: Dataset) -> list[ProcessorTxn]:
    return [t for t in ds.processor
            if t.type != "payout" and ds.period_start <= t.created <= ds.period_end]


def in_scope_payouts(ds: Dataset) -> list[ProcessorTxn]:
    return [t for t in ds.processor
            if t.type == "payout" and ds.period_start <= t.created <= ds.period_end]


def match(ds: Dataset, policy: Policy) -> MatchResult:
    res = MatchResult()
    ledger_all = in_scope_ledger(ds)
    res.ledger_fee_entries = [e for e in ledger_all if e.kind == "fee"]
    ledger = sorted((e for e in ledger_all if e.kind != "fee"), key=lambda e: (e.date, e.row))
    txns = sorted(in_scope_txns(ds), key=lambda t: (t.created, t.row))
    used_t: set[str] = set()
    used_l: set[str] = set()

    for e in ds.ledger:
        if e not in ledger_all:
            res.out_of_scope.append(e.id)

    def want_type(e: LedgerEntry) -> str:
        return "charge" if e.amount > 0 else "refund"

    # Pass 1: exact (reference + type + amount)
    for e in ledger:
        if not e.reference:
            continue
        cands = [t for t in txns if t.id not in used_t and t.order_id == e.reference
                 and t.type == want_type(e) and t.amount == e.amount]
        if cands:
            t = cands[0]
            used_t.add(t.id)
            used_l.add(e.id)
            res.matches.append(Match(e.id, t.id, "ledger-processor", "exact", 1.0,
                                     f"reference {e.reference} and amount {e.amount / 100:.2f} agree"))

    # Pass 2: same reference, different amount -> handed to the Investigator
    for e in ledger:
        if e.id in used_l or not e.reference:
            continue
        cands = [t for t in txns if t.id not in used_t and t.order_id == e.reference and t.type == want_type(e)]
        if cands:
            t = min(cands, key=lambda t: abs(t.amount - e.amount))
            used_t.add(t.id)
            used_l.add(e.id)
            res.ref_pairs.append((e, t))

    # Pass 3: fuzzy (amount must agree; date window and customer name raise confidence)
    w = policy.date_window_days
    for e in ledger:
        if e.id in used_l:
            continue
        scored = []
        for t in txns:
            if t.id in used_t or t.type != want_type(e) or t.amount != e.amount:
                continue
            dd = abs((t.created - e.date).days)
            if dd > w:
                continue
            score = 0.5 + 0.25 * (1 - dd / (w + 1)) + 0.25 * name_score(e, t)
            scored.append((round(score, 3), t))
        if not scored:
            continue
        scored.sort(key=lambda x: (-x[0], x[1].created, x[1].row))
        best, t = scored[0]
        second = scored[1][0] if len(scored) > 1 else None
        if best >= policy.fuzzy_accept and (second is None or best - second >= policy.ambiguity_margin):
            used_t.add(t.id)
            used_l.add(e.id)
            res.matches.append(Match(e.id, t.id, "ledger-processor", "fuzzy", best,
                                     f"amount {e.amount / 100:.2f} equal, {abs((t.created - e.date).days)}d apart, "
                                     f"name match {name_score(e, t):.0%}"))
        elif second is not None and best - second < policy.ambiguity_margin and best >= 0.5:
            used_l.add(e.id)
            res.ambiguous.append((e, [x[1] for x in scored if best - x[0] < policy.ambiguity_margin]))

    res.unmatched_ledger = [e for e in ledger if e.id not in used_l]
    res.unmatched_txns = [t for t in txns if t.id not in used_t]

    # Payouts <-> bank
    payouts = sorted(in_scope_payouts(ds), key=lambda p: (p.created, p.row))
    bank = [b for b in ds.bank if ds.period_start <= b.date <= ds.period_end]
    for b in ds.bank:
        if b not in bank:
            res.out_of_scope.append(b.id)
    kw = policy.processor_keywords
    used_b: set[str] = set()
    pending: list[ProcessorTxn] = []
    for p in payouts:
        key = payout_key(p)
        exact = [b for b in bank if b.id not in used_b and key.split(":")[-1] in b.description
                 and b.amount == -p.amount]
        if exact:
            used_b.add(exact[0].id)
            res.matches.append(Match(key, exact[0].id, "payout-bank", "exact", 1.0,
                                     f"payout id and amount {-p.amount / 100:.2f} found on statement"))
        else:
            pending.append(p)
    for p in pending:
        key = payout_key(p)
        cands = [b for b in bank if b.id not in used_b and b.amount == -p.amount
                 and 0 <= (b.date - p.created).days <= 5
                 and any(k in b.description.upper() for k in kw + [p.processor.upper()])]
        if len(cands) == 1:
            b = cands[0]
            used_b.add(b.id)
            conf = round(0.9 - 0.05 * max(0, (b.date - p.created).days - 1), 3)
            res.matches.append(Match(key, b.id, "payout-bank", "fuzzy", conf,
                                     f"amount {b.amount / 100:.2f} equal, processor keyword on line, "
                                     f"{(b.date - p.created).days}d after payout (no id on statement)"))
        else:
            res.unmatched_payouts.append(p)
    for b in bank:
        if b.id in used_b:
            continue
        if any(k in b.description.upper() for k in kw):
            res.unmatched_bank.append(b)
        else:
            res.out_of_scope.append(b.id)
    return res
