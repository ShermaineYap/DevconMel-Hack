"""End-to-end: the crew finds every planted problem, nothing else, and proves it to the cent."""

import json

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from closecrew import pipeline
from closecrew.seed import Plan


def findings(res):
    return {(x["cause"], frozenset(x["refs"])) for x in res["exceptions"]}


def truth_set(truth):
    return {(e["cause"], frozenset(e["refs"])) for e in truth["exceptions"]}


def test_finds_every_planted_problem_and_nothing_else(ws):
    truth = ws.seed()
    res = pipeline.run(**ws.kw)
    assert findings(res) == truth_set(truth)
    fuzzy = {(m["left"], m["right"]) for m in res["matches"] if m["method"] == "fuzzy"}
    assert fuzzy == {tuple(p) for p in truth["fuzzy_matches"] + truth["fuzzy_bank_matches"]}


def test_all_auditor_checks_pass(ws):
    ws.seed()
    res = pipeline.run(**ws.kw)
    failed = [c for c in res["audit"] if not c["ok"]]
    assert not failed, failed
    assert len(res["audit"]) == 9


def test_every_ringgit_explained(ws):
    ws.seed()
    res = pipeline.run(**ws.kw)
    s = res["summary"]
    proc = [x for x in res["exceptions"] if x["side"] == "processor"]
    assert sum(x["impact"] for x in proc) == s["diff_before"]


def test_approving_everything_closes_to_zero(ws):
    ws.seed()
    res = pipeline.run(**ws.kw)
    for x in [x for x in res["exceptions"] if x["status"] == "open"]:
        res = pipeline.decide(x["id"], "approved", by="tester", **ws.kw)
        assert not res.get("rolled_back")
    assert res["summary"]["status"] == "CLOSED"
    assert res["summary"]["diff_after"] == 0


def test_rejected_items_stay_explained_but_unfixed(ws):
    ws.seed()
    res = pipeline.run(**ws.kw)
    target = next(x for x in res["exceptions"] if x["status"] == "open")
    res = pipeline.decide(target["id"], "rejected", by="tester", **ws.kw)
    x = next(x for x in res["exceptions"] if x["id"] == target["id"])
    assert x["status"] == "rejected"
    assert all(c["ok"] for c in res["audit"])
    assert not any(f["exception_id"] == target["id"] for f in res["fixes"])


def test_reruns_are_idempotent(ws):
    ws.seed()
    a = pipeline.run(**ws.kw)
    rec1 = (ws.path / "state" / "ledger_reconciled.csv").read_text()
    b = pipeline.run(**ws.kw)
    rec2 = (ws.path / "state" / "ledger_reconciled.csv").read_text()
    assert rec1 == rec2
    assert [x["id"] for x in a["exceptions"]] == [x["id"] for x in b["exceptions"]]


def test_original_ledger_never_modified(ws):
    ws.seed()
    before = (ws.path / "data" / "ledger.csv").read_bytes()
    res = pipeline.run(**ws.kw)
    for x in [x for x in res["exceptions"] if x["status"] == "open"]:
        pipeline.decide(x["id"], "approved", **ws.kw)
    assert (ws.path / "data" / "ledger.csv").read_bytes() == before


def test_auditor_rollback_when_it_objects(ws, monkeypatch):
    ws.seed()
    res = pipeline.run(**ws.kw)
    target = next(x for x in res["exceptions"] if x["status"] == "open")
    from closecrew import auditor as aud
    real = aud.audit

    def sabotaged(*a, **k):
        r = real(*a, **k)
        if any(f.exception_id == target["id"] for f in a[3]):
            r.add("sabotage", False, "simulated failure")
        return r

    monkeypatch.setattr(pipeline.auditor, "audit", sabotaged)
    res = pipeline.decide(target["id"], "approved", **ws.kw)
    assert res["rolled_back"] == target["id"]
    assert target["id"] not in json.loads((ws.path / "state" / "approvals.json").read_text())


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(seed=st.integers(0, 10_000), n=st.integers(40, 200), missing=st.integers(0, 3), dup=st.integers(0, 3),
       transp=st.integers(0, 2), fuzzy=st.integers(0, 4), lwp=st.integers(0, 2))
def test_property_any_messy_month_is_fully_explained(tmp_path_factory, seed, n, missing, dup, transp, fuzzy, lwp):
    from tests.conftest import Workspace

    ws = Workspace(tmp_path_factory.mktemp("prop"))
    plan = Plan(n_charges=n, missing_ledger_entry=missing, duplicate_charge=dup, transposition=transp,
                missing_reference=fuzzy, ledger_without_payment=lwp)
    truth = ws.seed(seed, plan)
    res = pipeline.run(**ws.kw)
    assert all(c["ok"] for c in res["audit"]), [c for c in res["audit"] if not c["ok"]]
    assert findings(res) == truth_set(truth)
