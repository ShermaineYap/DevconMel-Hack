"""The owner's policy controls autonomy, and new payment sources plug in by config."""

import yaml

from closecrew import pipeline
from tests.conftest import BANK_H, LEDGER_H, STRIPE_H, charge, sale


def test_zero_caps_mean_nothing_is_automatic(ws):
    ws.seed()
    ws.set_policy({"max: 200.00": "max: 0.00", "max: 0.05": "max: 0.00", "max: 30.00": "max: 0.00"})
    res = pipeline.run(**ws.kw)
    assert res["summary"]["auto_fixed"] == 0
    assert all(c["ok"] for c in res["audit"])


def test_raising_a_cap_lets_the_large_refund_through(ws):
    ws.seed()
    before = pipeline.run(**ws.kw)["summary"]["auto_fixed"]
    ws.set_policy({"refund_not_booked: { max: 30.00 }": "refund_not_booked: { max: 500.00 }"})
    after = pipeline.run(**ws.kw)["summary"]["auto_fixed"]
    assert after == before + 1


def test_human_only_causes_never_auto_fix_even_if_tiny(ws):
    ws.seed()
    res = pipeline.run(**ws.kw)
    for x in res["exceptions"]:
        if x["cause"] in ("duplicate_charge", "missing_ledger_entry", "transposition", "ledger_without_payment"):
            assert x["status"] == "open"


def test_auditor_catches_a_policy_violation(ws):
    ws.seed()
    from closecrew import auditor, fixer, investigator, matcher
    from closecrew.ingest import load_sources
    from closecrew.policy import load_policy

    ds = load_sources(ws.path / "sources.yaml")
    pol = load_policy(ws.path / "policy.yaml")
    mr = matcher.match(ds, pol)
    excs = investigator.investigate(ds, mr, pol)
    fixes = fixer.decide(excs, pol, {}, ds.period_end)
    rogue = next(x for x in excs if x.cause == "duplicate_charge")
    rogue.status = "auto_fixed"  # an agent trying to act outside policy
    fixes.append(fixer.FixEntry("FIX-ROGUE", rogue.id, ds.period_end, "rogue", "", rogue.impact, "liability", "policy"))
    rep = auditor.audit(ds, mr, excs, fixes, pol)
    failed = {c.name for c in rep.checks if not c.ok}
    assert "auto-fixes within owner policy" in failed


def test_new_wallet_source_plugs_in_by_config(ws):
    """Curveball rehearsal: add a TnG eWallet export without touching code."""
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 3, 20.0, "ORD-1", "Aisyah Tan"),
                                      sale("LED-2", 4, 15.0, "ORD-2", "Ravi Kumar")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 3, 20.0, "ORD-1", "Aisyah Tan")])
    ws.write("bank_statement.csv", BANK_H, [["BNK-1", "2026-10-09", "TNG SETTLEMENT S-9", "14.70"]])
    ws.write("tng_export.csv", ["Transaction ID", "Date", "Type", "Amount", "MDR Fee", "Merchant Ref", "Payer",
                                "Settlement ID"],
             [["T1", "04/10/2026", "Payment", "15.00", "0.30", "ORD-2", "Ravi Kumar", "S-9"],
              ["S9", "08/10/2026", "Settlement", "14.70", "0.00", "", "", "S-9"]])
    cfg = yaml.safe_load((ws.path / "sources.yaml").read_text())
    cfg["sources"]["extra_processors"] = [{
        "adapter": "generic_csv", "name": "tng", "path": "data/tng_export.csv",
        "mapping": {"id": "Transaction ID", "created": "Date", "amount": "Amount", "fee": "MDR Fee", "type": "Type",
                    "order_id": "Merchant Ref", "customer": "Payer", "payout_id": "Settlement ID"},
        "type_map": {"Payment": "charge", "Refund": "refund", "Settlement": "payout"}}]
    cfg_text = yaml.safe_dump(cfg)
    (ws.path / "sources.yaml").write_text(cfg_text)
    ws.set_policy({"processor_keywords: [STRIPE]": "processor_keywords: [STRIPE, TNG]"})
    res = pipeline.run(**ws.kw)
    assert all(c["ok"] for c in res["audit"]), res["audit"]
    assert {(m["left"], m["right"]) for m in res["matches"]} >= {("LED-2", "tng:T1"), ("tng:S-9", "BNK-1")}
    assert not [x for x in res["exceptions"] if x["cause"] not in ("processor_fee",)]
