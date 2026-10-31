"""Adversarial cases: things that should NOT fool the crew."""

import pytest

from closecrew import explainer, pipeline
from closecrew.ingest import IngestError, stripe_api
from tests.conftest import BANK_H, LEDGER_H, STRIPE_H, charge, sale


def causes(res):
    return sorted(x["cause"] for x in res["exceptions"] if x["cause"] != "processor_fee")


def test_same_amount_same_day_different_customers_is_not_a_duplicate(ws):
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 5, 50.0, "ORD-1", "Aisyah Tan"),
                                      sale("LED-2", 5, 50.0, "ORD-2", "Ravi Kumar")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 5, 50.0, "ORD-1", "Aisyah Tan"),
                                                           charge("ch_b", 5, 50.0, "ORD-2", "Ravi Kumar")])
    ws.write("bank_statement.csv", BANK_H, [])
    res = pipeline.run(**ws.kw)
    assert causes(res) == []
    assert all(c["ok"] for c in res["audit"])


def test_same_customer_two_real_orders_same_amount_is_not_a_duplicate(ws):
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 5, 30.0, "ORD-1", "Aisyah Tan"),
                                      sale("LED-2", 5, 30.0, "ORD-2", "Aisyah Tan")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 5, 30.0, "ORD-1", "Aisyah Tan"),
                                                           charge("ch_b", 5, 30.0, "ORD-2", "Aisyah Tan")])
    ws.write("bank_statement.csv", BANK_H, [])
    assert causes(pipeline.run(**ws.kw)) == []


def test_true_duplicate_is_caught(ws):
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 5, 30.0, "ORD-1", "Aisyah Tan")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 5, 30.0, "ORD-1", "Aisyah Tan"),
                                                           charge("ch_b", 5, 30.0, "ORD-1", "Aisyah Tan")])
    ws.write("bank_statement.csv", BANK_H, [])
    res = pipeline.run(**ws.kw)
    dup = [x for x in res["exceptions"] if x["cause"] == "duplicate_charge"]
    assert len(dup) == 1 and dup[0]["refs"] == ["ch_b"] and dup[0]["status"] == "open"


def test_lookalike_payments_go_to_a_human_not_a_guess(ws):
    # Ledger row has no reference and no name: two equal payments on the same day are indistinguishable.
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 5, 42.0, "", "", desc="Card sale")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 5, 42.0, "ORD-1", "Aisyah Tan"),
                                                           charge("ch_b", 5, 42.0, "ORD-2", "Ravi Kumar")])
    ws.write("bank_statement.csv", BANK_H, [])
    res = pipeline.run(**ws.kw)
    assert "ambiguous_match" in causes(res)
    assert not any(m["method"] == "fuzzy" for m in res["matches"])
    assert all(c["ok"] for c in res["audit"])


def test_overcharged_fee_blocks_auto_fix(ws):
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 5, 100.0, "ORD-1", "Aisyah Tan"),
                                      sale("LED-2", 6, 100.0, "ORD-2", "Ravi Kumar")])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [charge("ch_a", 5, 100.0, "ORD-1", "Aisyah Tan"),
                                                           charge("ch_b", 6, 100.0, "ORD-2", "Ravi Kumar", fee=9.0)])
    ws.write("bank_statement.csv", BANK_H, [])
    res = pipeline.run(**ws.kw)
    fee = next(x for x in res["exceptions"] if x["cause"] == "processor_fee")
    assert fee["status"] == "open" and "agreed rate" in fee["decision_reason"]
    assert any("expected" in e for e in fee["evidence"])


def test_wrong_bank_amount_is_not_matched_to_a_payout(ws):
    ws.write("ledger.csv", LEDGER_H, [sale("LED-1", 2, 100.0, "ORD-1", "Aisyah Tan")])
    s = charge("ch_a", 2, 100.0, "ORD-1", "Aisyah Tan", fee=4.0, payout="po_1")
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [
        s, ["po_1", "2026-10-06", "payout", "-96.00", "0.00", "-96.00", "myr", "", "", "STRIPE PAYOUT", "po_1",
            "2026-10-06", "2026-10-07"]])
    ws.write("bank_statement.csv", BANK_H, [["BNK-1", "2026-10-07", "STRIPE TRANSFER", "69.00"]])
    res = pipeline.run(**ws.kw)
    assert {"payout_missing", "bank_unmatched_processor"} <= set(causes(res))
    assert all(c["ok"] for c in res["audit"])


def test_live_stripe_keys_are_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_123")
    with pytest.raises(IngestError, match="TEST mode"):
        stripe_api({"period": "2026-10"}, tmp_path)


def test_broken_input_stops_the_run(ws):
    ws.write("ledger.csv", ["id", "date", "amount"], [["LED-1", "2026-10-01", "5.00"]])
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [])
    ws.write("bank_statement.csv", BANK_H, [])
    with pytest.raises(IngestError, match="missing columns"):
        pipeline.run(**ws.kw)


def test_processor_sign_errors_are_rejected(ws):
    ws.write("ledger.csv", LEDGER_H, [])
    bad = charge("ch_a", 5, 10.0, "ORD-1", "X")
    bad[2] = "refund"  # positive refund is impossible
    ws.write("stripe_balance_transactions.csv", STRIPE_H, [bad])
    ws.write("bank_statement.csv", BANK_H, [])
    with pytest.raises(IngestError, match="sign"):
        pipeline.run(**ws.kw)


def test_hallucinated_amounts_are_rejected(ws, monkeypatch):
    ws.seed()
    res = pipeline.run(**ws.kw)
    from closecrew import llm

    monkeypatch.setattr(llm, "available", lambda: "anthropic")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "Great month! You made RM 99,999.99 in profit.")
    from closecrew.models import Exception_
    excs = [Exception_(**{k: v for k, v in x.items() if k != "impact_display"}) for x in res["exceptions"]]
    text, source = explainer.narrative(res["summary"], excs)
    assert "rejected" in source and "99,999.99" not in text

    good = f"Net card income was RM {res['summary']['processor_net'] / 100:,.2f}."
    monkeypatch.setattr(llm, "complete", lambda *a, **k: good)
    text, source = explainer.narrative(res["summary"], excs)
    assert text == good and source.startswith("llm")
