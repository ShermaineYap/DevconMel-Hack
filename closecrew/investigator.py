"""Investigator agent: turn every unmatched or mismatched row into a named cause.

Each exception carries its exact signed impact on the reconciliation
difference and cites the source rows it is based on. The Auditor later
proves the impacts add up to the difference to the cent.
"""

from __future__ import annotations

from collections import defaultdict

from .ingest import Dataset
from .matcher import MatchResult, payout_key
from .models import Exception_, LedgerEntry, ProcessorTxn, money
from .policy import Policy


def is_transposition(a: int, b: int) -> bool:
    """True if b is a with two adjacent digits swapped (e.g. 45.00 vs 54.00)."""
    sa, sb = str(abs(a)), str(abs(b))
    if len(sa) != len(sb) or sa == sb:
        return False
    diff = [i for i in range(len(sa)) if sa[i] != sb[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and sa[diff[0]] == sb[diff[1]] and sa[diff[1]] == sb[diff[0]]


def expected_fee(amount: int, policy: Policy) -> int:
    return (amount * policy.fee_bps + 5000) // 10000 + policy.fee_fixed


def investigate(ds: Dataset, mr: MatchResult, policy: Policy) -> list[Exception_]:
    exc: list[Exception_] = []

    # 1. Same order, different amount
    for e, t in mr.ref_pairs:
        diff = t.amount - e.amount
        ev = [f"{e.cite()}: booked {money(e.amount)} for {e.reference}",
              f"{t.cite()}: {t.processor} {t.type} {money(t.amount)} for {t.order_id}"]
        if abs(diff) <= policy.rounding_max:
            cause = "rounding"
            why = (f"{e.reference}: books say {money(e.amount)}, {t.processor} received {money(t.amount)}. "
                   f"A {money(abs(diff))} gap on one order is currency conversion or rounding.")
            if "convert" in t.description.lower() or t.currency.lower() != "myr":
                ev.append(f"{t.cite()}: description notes a currency conversion")
        elif is_transposition(e.amount, t.amount):
            cause = "transposition"
            why = (f"{e.reference}: typed as {money(e.amount)} but the customer paid {money(t.amount)}. "
                   f"The digits are swapped, a classic typing slip.")
        else:
            cause = "amount_mismatch"
            why = (f"{e.reference}: books say {money(e.amount)}, {t.processor} received {money(t.amount)}. "
                   f"The {money(abs(diff))} gap has no obvious mechanical cause.")
        exc.append(Exception_(cause, "processor", [e.id, t.id], diff, why, ev,
                              proposed_entry={"kind": "adjustment", "amount": diff, "reference": e.reference,
                                              "description": f"Correct {e.reference}: booked {money(e.amount)}, "
                                                             f"received {money(t.amount)} ({cause})"}))

    # 2. Ambiguous fuzzy matches
    for e, cands in mr.ambiguous:
        exc.append(Exception_(
            "ambiguous_match", "processor", [e.id], -e.amount,
            f"{e.cite()} ({money(e.amount)}) could be any of {len(cands)} payments with the same amount "
            f"and date. A human should pick the right one.",
            [e.cite()] + [f"candidate {t.cite()}: {t.customer} {money(t.amount)} on {t.created}" for t in cands],
            confidence=0.5, action="Pick the matching payment"))

    # 3. Unmatched processor transactions
    all_charges = [t for t in ds.processor if t.type == "charge"]
    unmatched_ids = {t.id for t in mr.unmatched_txns}
    for t in mr.unmatched_txns:
        if t.type == "charge":
            twin = next((o for o in all_charges if o.id != t.id and o.order_id and o.order_id == t.order_id
                         and o.amount == t.amount and o.customer == t.customer
                         and abs((o.created - t.created).days) <= 1
                         and (o.id not in unmatched_ids or (o.created, o.row) < (t.created, t.row))), None)
            if twin:
                exc.append(Exception_(
                    "duplicate_charge", "processor", [t.id], t.amount,
                    f"{t.customer} was charged {money(t.amount)} twice for {t.order_id}. The books have one sale; "
                    f"the second charge is money the shop owes back.",
                    [f"{twin.cite()}: first charge {money(twin.amount)} for {twin.order_id}",
                     f"{t.cite()}: second charge {money(t.amount)} for {t.order_id}, same customer, same day"],
                    proposed_entry={"kind": "liability", "amount": t.amount, "reference": t.order_id,
                                    "description": f"Duplicate charge {t.id} on {t.order_id}: refund owed to "
                                                   f"{t.customer}"},
                    action=f"Refund {t.id} ({money(t.amount)}) to {t.customer}"))
                continue
            exc.append(Exception_(
                "missing_ledger_entry", "processor", [t.id], t.amount,
                f"{t.customer} paid {money(t.amount)} for {t.order_id or 'an order'} on {t.created}, "
                f"but the sale was never entered in the books.",
                [f"{t.cite()}: {t.description} {money(t.amount)}", "no ledger row has this order or amount nearby"],
                proposed_entry={"kind": "sale", "amount": t.amount, "reference": t.order_id,
                                "description": f"Record missing sale {t.order_id} - {t.customer} ({t.id})"}))
        elif t.type == "refund":
            exc.append(Exception_(
                "refund_not_booked", "processor", [t.id], t.amount,
                f"{money(-t.amount)} was refunded to {t.customer or 'a customer'} for {t.order_id} on "
                f"{t.created}, but the refund is not in the books, so sales are overstated.",
                [f"{t.cite()}: refund {money(t.amount)} for {t.order_id}"],
                proposed_entry={"kind": "refund", "amount": t.amount, "reference": t.order_id,
                                "description": f"Book refund {t.order_id} - {t.customer} ({t.id})"}))
        else:
            exc.append(Exception_(
                "processor_adjustment", "processor", [t.id], t.net,
                f"{t.processor} made an adjustment of {money(t.net)} ({t.description}). It needs a human to "
                f"decide how to book it.", [t.cite()],
                proposed_entry={"kind": "adjustment", "amount": t.net, "reference": t.id,
                                "description": f"{t.processor} adjustment {t.id}: {t.description}"}))

    # 4. Unmatched ledger rows
    for e in mr.unmatched_ledger:
        if e.amount > 0:
            exc.append(Exception_(
                "ledger_without_payment", "processor", [e.id], -e.amount,
                f"The books show a card sale of {money(e.amount)} ({e.reference or e.description}) on {e.date}, "
                f"but no card payment arrived. The payment may have failed.",
                [f"{e.cite()}: {e.description} {money(e.amount)}",
                 "no processor charge with this reference, or this amount within the date window"],
                proposed_entry={"kind": "adjustment", "amount": -e.amount, "reference": e.reference,
                                "description": f"Reverse unpaid card sale {e.reference or e.id}: no payment received"},
                action=f"Chase {e.customer or 'the customer'} for {money(e.amount)}"))
        else:
            exc.append(Exception_(
                "refund_without_processor", "processor", [e.id], -e.amount,
                f"The books show a refund of {money(-e.amount)} ({e.reference}) that never went through "
                f"the card processor.",
                [f"{e.cite()}: {e.description} {money(e.amount)}"],
                proposed_entry={"kind": "adjustment", "amount": -e.amount, "reference": e.reference,
                                "description": f"Reverse refund {e.reference or e.id}: not processed"}))

    # 5. Processing fees, grouped by the payout that settled them
    batches: dict[str, list[ProcessorTxn]] = defaultdict(list)
    from .matcher import in_scope_txns
    for t in in_scope_txns(ds):
        key = "fees:" + (t.payout_id or f"pending:{t.processor}")
        batches[key].append(t)
    booked: dict[str, list[LedgerEntry]] = defaultdict(list)
    for e in mr.ledger_fee_entries:
        booked["fees:" + e.reference if e.reference else "fees:unlinked"].append(e)
    for key, ts in sorted(batches.items()):
        fees = sum(t.fee for t in ts)
        led = booked.pop(key, [])
        impact = -fees - sum(e.amount for e in led)
        anomalies = [t for t in ts if t.type == "charge"
                     and abs(t.fee - expected_fee(t.amount, policy)) > policy.fee_tolerance]
        if impact == 0 and not anomalies:
            continue
        label = key.split(":", 1)[1]
        ev = [f"{len(ts)} transactions settled in {label}, fees total {money(fees)}"]
        if led:
            ev.append(f"already booked in ledger: {money(-sum(e.amount for e in led))} ({', '.join(e.cite() for e in led)})")
        for t in anomalies[:5]:
            ev.append(f"{t.cite()}: fee {money(t.fee)} but expected {money(expected_fee(t.amount, policy))} "
                      f"at {policy.fee_bps / 100:.2f}% + {money(policy.fee_fixed)}")
        x = Exception_(
            "processor_fee", "processor", [key], impact,
            f"{label} was paid out net of {money(fees)} in processing fees that are not yet in the books."
            + (f" {len(anomalies)} fee(s) look higher than the agreed rate." if anomalies else ""),
            ev, proposed_entry={"kind": "fee", "amount": impact, "reference": label,
                                "description": f"Card processing fees, {label} ({len(ts)} txns)"})
        x.blocked = f"fee above agreed rate on {len(anomalies)} txn(s)" if anomalies else ""
        exc.append(x)
    for key, led in booked.items():  # fee rows in the ledger that point at no known batch
        for e in led:
            exc.append(Exception_("ledger_fee_unlinked", "processor", [e.id], -e.amount,
                                  f"A fee of {money(-e.amount)} is booked but matches no payout.", [e.cite()]))

    # 6. Payouts vs bank
    for p in mr.unmatched_payouts:
        key = payout_key(p)
        if p.arrival and p.arrival > ds.period_end:
            exc.append(Exception_(
                "payout_in_transit", "bank", [key], -p.amount,
                f"Payout {key} of {money(-p.amount)} left {p.processor} on {p.created} and lands on {p.arrival}, "
                f"after month end. Timing only; nothing is missing.",
                [f"{p.cite()}: payout {money(-p.amount)}, arrival {p.arrival}"]))
        else:
            exc.append(Exception_(
                "payout_missing", "bank", [key], -p.amount,
                f"Payout {key} of {money(-p.amount)} should have reached the bank by "
                f"{p.arrival or p.created}, but it is not on the statement.",
                [f"{p.cite()}: payout {money(-p.amount)}"], action=f"Ask the bank and {p.processor} about {key}"))
    for b in mr.unmatched_bank:
        exc.append(Exception_(
            "bank_unmatched_processor", "bank", [b.id], -b.amount,
            f"The bank received {money(b.amount)} described as '{b.description}', but no payout explains it.",
            [b.cite()], action="Identify the source of this deposit"))
    return exc
