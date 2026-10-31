"""Mirror the seeded month into YOUR Stripe TEST account, so the crew can read it live.

    export STRIPE_SECRET_KEY=sk_test_...
    python scripts/seed_stripe.py            # creates charges (incl. duplicates) and refunds
    # then in sources.yaml switch processor.adapter to stripe_api

Refuses live keys. Test cards only (pm_card_visa). Payment dates will be "today" in Stripe,
so set `period:` in sources.yaml to the current month when using the live adapter.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        print("Refusing: set STRIPE_SECRET_KEY to a TEST mode key (sk_test_...)")
        return 1
    currency = os.environ.get("STRIPE_CURRENCY", "myr")
    rows = list(csv.DictReader(open(ROOT / "data" / "stripe_balance_transactions.csv")))
    limit = int(os.environ.get("SEED_LIMIT", "40"))
    charges_by_order: dict[str, str] = {}
    with httpx.Client(base_url="https://api.stripe.com/v1", auth=(key, ""), timeout=30) as c:
        n = 0
        for r in rows:
            if r["type"] != "charge" or n >= limit:
                continue
            amount = int(round(float(r["amount"]) * 100))
            resp = c.post("/payment_intents", data={
                "amount": amount, "currency": currency, "payment_method": "pm_card_visa", "confirm": "true",
                "automatic_payment_methods[enabled]": "true", "automatic_payment_methods[allow_redirects]": "never",
                "description": r["description"], "metadata[order_id]": r["order_id"],
                "metadata[customer]": r["customer"]})
            if resp.status_code >= 400:
                print("stripe error:", resp.json().get("error", {}).get("message"))
                return 1
            pi = resp.json()
            charges_by_order.setdefault(r["order_id"], pi["latest_charge"])
            n += 1
            print(f"charged {r['order_id']} {r['amount']} -> {pi['latest_charge']}")
        for r in rows:
            if r["type"] == "refund" and r["order_id"] in charges_by_order:
                amt = int(round(-float(r["amount"]) * 100))
                resp = c.post("/refunds", data={"charge": charges_by_order[r["order_id"]], "amount": amt,
                                                "metadata[order_id]": r["order_id"]})
                print(f"refunded {r['order_id']} {amt / 100:.2f}: {resp.status_code}")
    print(f"done: {n} test charges created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
