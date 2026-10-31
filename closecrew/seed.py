"""Generate a realistic, deliberately messy month of fake data for a small shop.

Writes three source files plus `ground_truth.json`, which lists every mess we
planted. The tests use it to prove the agents find every planted problem and
nothing else. All data is fake; no real people, cards or money.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

FIRST = ["Aisyah", "Wei Ming", "Priya", "Mei Ling", "Hafiz", "Kar Wai", "Siti", "Arjun",
         "Jia Hui", "Farid", "Kavitha", "Jun Hao", "Nadia", "Ravi", "Hui Min", "Amir",
         "Shalini", "Zhi Wei", "Liyana", "Darren"]
LAST = ["Rahman", "Tan", "Nair", "Lim", "Ismail", "Chong", "Abdullah", "Pillai", "Ng",
        "Hassan", "Raj", "Goh", "Yusof", "Kumar", "Wong", "Aziz", "Menon", "Lee", "Osman", "Teh"]
ITEMS = ["Kuih box", "Pandan cake", "Kopi beans 500g", "Onde-onde dozen", "Party tray",
         "Kaya jar", "Gift hamper", "Butter cake", "Seri muka slab", "Coffee subscription"]


@dataclass
class Plan:
    """How many of each mess to plant. Defaults give a compelling demo month."""

    n_charges: int = 120
    missing_ledger_entry: int = 2
    duplicate_charge: int = 2
    refund_booked: int = 1
    refund_small_unbooked: int = 1
    refund_large_unbooked: int = 1
    transposition: int = 1
    rounding: int = 1
    missing_reference: int = 3
    ledger_without_payment: int = 1
    fee_bps: int = 300  # 3.00%
    fee_fixed: int = 100  # + RM 1.00
    year: int = 2026
    month: int = 10
    extra: dict = field(default_factory=dict)


def _fee(amount: int, plan: Plan) -> int:
    return (amount * plan.fee_bps + 5000) // 10000 + plan.fee_fixed


def _transposable(rng: random.Random) -> tuple[int, int]:
    """Return (true_cents, booked_cents) where booked swaps the two ringgit digits."""
    while True:
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        if a != b:
            return (a * 10 + b) * 100, (b * 10 + a) * 100


def generate(out_dir: str | Path, seed: int = 42, plan: Plan | None = None) -> dict:
    plan = plan or Plan()
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    start = date(plan.year, plan.month, 1)
    nxt = date(plan.year + (plan.month == 12), plan.month % 12 + 1, 1)
    last_day = (nxt - timedelta(days=1)).day
    period_end = nxt - timedelta(days=1)

    def hexid(prefix: str) -> str:
        return prefix + "".join(rng.choice("0123456789abcdef") for _ in range(14))

    # ---- base charges -------------------------------------------------------
    used_amounts: set[int] = set()
    charges = []
    for i in range(plan.n_charges):
        d = start + timedelta(days=rng.randint(0, last_day - 2))
        amt = rng.randint(85, 2500) * 10  # RM 8.50 .. RM 250.00 in 10-sen steps
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        charges.append({
            "id": hexid("ch_"), "date": d, "amount": amt, "order": f"ORD-{10001 + i}",
            "customer": name, "item": rng.choice(ITEMS), "desc_extra": "",
        })
    charges.sort(key=lambda c: (c["date"], c["order"]))

    pool = list(range(len(charges)))
    rng.shuffle(pool)

    def take(n: int) -> list[int]:
        return [pool.pop() for _ in range(n)]

    truth: dict = {"exceptions": [], "fuzzy_matches": [], "fuzzy_bank_matches": [],
                   "seed": seed, "plan": plan.__dict__ | {}}

    missing_idx = take(plan.missing_ledger_entry)
    dup_idx = take(plan.duplicate_charge)
    transp_idx = take(plan.transposition)
    round_idx = take(plan.rounding)
    refund_booked_idx = take(plan.refund_booked)
    refund_small_idx = take(plan.refund_small_unbooked)
    refund_large_idx = take(plan.refund_large_unbooked)
    # Refunds need time to happen inside the month.
    for idx in refund_booked_idx + refund_small_idx + refund_large_idx:
        if charges[idx]["date"].day > last_day - 6:
            charges[idx]["date"] = start + timedelta(days=rng.randint(0, last_day - 8))

    transp_book: dict[int, int] = {}
    for idx in transp_idx:
        true, booked = _transposable(rng)
        while true in used_amounts:
            true, booked = _transposable(rng)
        charges[idx]["amount"] = true
        transp_book[idx] = booked
    for idx in round_idx:
        charges[idx]["desc_extra"] = f" (card in SGD {charges[idx]['amount'] / 330:.2f}, converted)"
    for idx in refund_large_idx:
        charges[idx]["amount"] = rng.randint(1800, 2400) * 10

    # Fuzzy targets need an amount that is unique within the matching window.
    def unique_amount_ok(idx: int) -> bool:
        c = charges[idx]
        return all(not (o["amount"] == c["amount"] and abs((o["date"] - c["date"]).days) <= 3)
                   for j, o in enumerate(charges) if j != idx)

    fuzzy_idx: list[int] = []
    while len(fuzzy_idx) < plan.missing_reference and pool:
        idx = pool.pop()
        if unique_amount_ok(idx):
            fuzzy_idx.append(idx)

    # ---- processor transactions --------------------------------------------
    txns = []
    for i, c in enumerate(charges):
        txns.append({"id": c["id"], "created": c["date"], "type": "charge", "amount": c["amount"],
                     "fee": _fee(c["amount"], plan), "order": c["order"], "customer": c["customer"],
                     "description": f"{c['item']} - {c['order']}{c['desc_extra']}"})
        if i in dup_idx:
            dup = {"id": hexid("ch_"), "created": c["date"], "type": "charge", "amount": c["amount"],
                   "fee": _fee(c["amount"], plan), "order": c["order"], "customer": c["customer"],
                   "description": f"{c['item']} - {c['order']}"}
            txns.append(dup)
            truth["exceptions"].append({"cause": "duplicate_charge", "refs": [dup["id"]]})
        if i in missing_idx:
            truth["exceptions"].append({"cause": "missing_ledger_entry", "refs": [c["id"]]})

    refunds = []
    for idx in refund_booked_idx + refund_small_idx + refund_large_idx:
        c = charges[idx]
        if idx in refund_small_idx:
            amt = min(1250, c["amount"] // 2)
        else:
            amt = c["amount"]
        r = {"id": hexid("re_"), "created": c["date"] + timedelta(days=rng.randint(1, 5)),
             "type": "refund", "amount": -amt, "fee": 0, "order": c["order"],
             "customer": c["customer"], "description": f"Refund {c['order']}", "_idx": idx}
        refunds.append(r)
        txns.append(r)
        if idx not in refund_booked_idx:
            truth["exceptions"].append({"cause": "refund_not_booked", "refs": [r["id"]]})

    txns.sort(key=lambda t: (t["created"], t["type"] != "charge"))
    for t in txns:
        t["available_on"] = t["created"] + timedelta(days=2)
        t["payout_id"] = ""

    # Weekly payouts (Mondays-ish) plus one on the last day that lands next month.
    payout_days = [d for d in (6, 13, 20, 27) if d <= last_day] + [last_day]
    payouts = []
    for pd in payout_days:
        p_date = date(plan.year, plan.month, pd)
        batch = [t for t in txns if t["type"] != "payout" and not t["payout_id"] and t["available_on"] <= p_date]
        total = sum(t["amount"] - t["fee"] for t in batch)
        if not batch or total <= 0:
            continue
        pid = hexid("po_")
        arrival = p_date + timedelta(days=1 if pd != last_day else 2)
        for t in batch:
            t["payout_id"] = pid
        fees = sum(t["fee"] for t in batch)
        payouts.append({"id": pid, "created": p_date, "type": "payout", "amount": -total, "fee": 0,
                        "order": "", "customer": "", "description": "STRIPE PAYOUT",
                        "available_on": p_date, "payout_id": pid, "arrival": arrival})
        truth["exceptions"].append({"cause": "processor_fee", "refs": ["fees:" + pid], "fees": fees})
        if arrival > period_end:
            truth["exceptions"].append({"cause": "payout_in_transit", "refs": [pid]})
    pending_fees = sum(t["fee"] for t in txns if not t["payout_id"])
    if pending_fees:
        truth["exceptions"].append({"cause": "processor_fee", "refs": ["fees:pending:stripe"], "fees": pending_fees})

    # ---- ledger (what the owner typed into her spreadsheet) -----------------
    ledger = []
    for i, c in enumerate(charges):
        if i in missing_idx:
            continue
        amount = c["amount"]
        ref = c["order"]
        desc = f"Sale {c['order']} - {c['customer']} - {c['item']}"
        d = c["date"]
        if i in transp_idx:
            amount = transp_book[i]
        if i in round_idx:
            amount = c["amount"] - 3
        if i in fuzzy_idx:
            ref = ""
            desc = f"Sale - {c['customer'].split()[0]} {c['customer'].split()[-1]} ({c['item'].lower()})"
            d = c["date"] + timedelta(days=rng.choice([0, 1]))
        ledger.append({"date": d, "description": desc, "reference": ref, "amount": amount,
                       "kind": "sale", "method": "card", "customer": c["customer"], "_charge": c["id"], "_i": i})
    for r in refunds:
        if r["_idx"] in refund_booked_idx:
            ledger.append({"date": r["created"], "description": f"Refund {r['order']} - {r['customer']}",
                           "reference": r["order"], "amount": r["amount"], "kind": "refund",
                           "method": "card", "customer": r["customer"], "_charge": r["id"], "_i": -1})
    for k in range(plan.ledger_without_payment):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        ledger.append({"date": start + timedelta(days=rng.randint(3, last_day - 3)),
                       "description": f"Sale ORD-{19001 + k} - {name} - {rng.choice(ITEMS)}",
                       "reference": f"ORD-{19001 + k}", "amount": rng.randint(300, 900) * 10,
                       "kind": "sale", "method": "card", "customer": name, "_charge": "", "_i": -2})
    # A couple of non-card rows: real books have these and the agents must ignore them.
    ledger.append({"date": start + timedelta(days=4), "description": "Cash sale - weekend market",
                   "reference": "", "amount": 38500, "kind": "sale", "method": "cash", "customer": "",
                   "_charge": "", "_i": -3})
    ledger.append({"date": start + timedelta(days=1), "description": "Rent - shop lot October",
                   "reference": "", "amount": -150000, "kind": "expense", "method": "bank",
                   "customer": "", "_charge": "", "_i": -3})
    ledger.sort(key=lambda e: (e["date"], e["description"]))
    for n, e in enumerate(ledger, start=1):
        e["id"] = f"LED-{n:04d}"

    for e in ledger:
        i = e["_i"]
        if i in transp_idx:
            truth["exceptions"].append({"cause": "transposition", "refs": [e["id"], e["_charge"]]})
        if i in round_idx:
            truth["exceptions"].append({"cause": "rounding", "refs": [e["id"], e["_charge"]]})
        if i in fuzzy_idx:
            truth["fuzzy_matches"].append([e["id"], e["_charge"]])
        if i == -2:
            truth["exceptions"].append({"cause": "ledger_without_payment", "refs": [e["id"]]})

    # ---- bank statement ------------------------------------------------------
    bank = []
    fuzzy_payout = payouts[1]["id"] if len(payouts) > 2 else None
    for p in payouts:
        if p["arrival"] > period_end:
            continue
        desc = f"STRIPE TRANSFER {p['id']}" if p["id"] != fuzzy_payout else "STRIPE TRANSFER"
        bank.append({"date": p["arrival"], "description": desc, "amount": -p["amount"], "_payout": p["id"]})
    bank.append({"date": start + timedelta(days=1), "description": "IBG RENT SHOP LOT OCT",
                 "amount": -150000, "_payout": ""})
    bank.append({"date": start + timedelta(days=5), "description": "CASH DEPOSIT CDM",
                 "amount": 38500, "_payout": ""})
    bank.sort(key=lambda b: b["date"])
    for n, b in enumerate(bank, start=1):
        b["id"] = f"BNK-{n:04d}"
        if b["_payout"] == fuzzy_payout and fuzzy_payout:
            truth["fuzzy_bank_matches"].append([fuzzy_payout, b["id"]])

    # ---- write files --------------------------------------------------------
    def c2s(c: int) -> str:
        return f"{c / 100:.2f}"

    with open(out / "ledger.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "date", "description", "reference", "amount", "kind", "method", "customer"])
        for e in ledger:
            w.writerow([e["id"], e["date"].isoformat(), e["description"], e["reference"],
                        c2s(e["amount"]), e["kind"], e["method"], e["customer"]])

    all_txns = sorted(txns + payouts, key=lambda t: (t["created"], t["type"] == "payout"))
    with open(out / "stripe_balance_transactions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "created", "type", "amount", "fee", "net", "currency", "order_id",
                    "customer", "description", "payout_id", "available_on", "arrival"])
        for t in all_txns:
            w.writerow([t["id"], t["created"].isoformat(), t["type"], c2s(t["amount"]), c2s(t["fee"]),
                        c2s(t["amount"] - t["fee"]), "myr", t["order"], t["customer"], t["description"],
                        t["payout_id"], t["available_on"].isoformat(),
                        t["arrival"].isoformat() if t.get("arrival") else ""])

    with open(out / "bank_statement.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "date", "description", "amount"])
        for b in bank:
            w.writerow([b["id"], b["date"].isoformat(), b["description"], c2s(b["amount"])])

    with open(out / "ground_truth.json", "w") as f:
        json.dump(truth, f, indent=2, default=str)
    return truth


if __name__ == "__main__":
    import sys

    generate(sys.argv[1] if len(sys.argv) > 1 else "data")
