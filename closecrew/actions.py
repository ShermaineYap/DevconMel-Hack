"""Actions that happen in the outside world, only AFTER a human approves.

The only one wired up is refunding a duplicate charge in Stripe TEST mode.
It is off unless CLOSECREW_ENABLE_STRIPE_ACTIONS=1 and the key is a test key.
"""

from __future__ import annotations

import os


def after_approval(exception: dict) -> str:
    if exception.get("cause") != "duplicate_charge":
        return "no external action for this cause"
    if os.environ.get("CLOSECREW_ENABLE_STRIPE_ACTIONS") != "1":
        return "suggested action recorded (Stripe actions disabled)"
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        return "refused: Stripe actions only run with a TEST mode key"
    charge_id = exception["refs"][0]
    if not charge_id.startswith(("ch_", "py_")):
        return f"refused: {charge_id} is not a Stripe charge id"
    import httpx

    r = httpx.post("https://api.stripe.com/v1/refunds", auth=(key, ""), timeout=30,
                   data={"charge": charge_id, "reason": "duplicate",
                         "metadata[closecrew_exception]": exception["id"]})
    if r.status_code >= 400:
        return f"Stripe refused refund: {r.json().get('error', {}).get('message', r.text)[:200]}"
    return f"refunded in Stripe test mode: {r.json()['id']}"
