"""The dashboard API: approvals from the web go through the same audited path."""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(ws, monkeypatch):
    monkeypatch.setenv("CLOSECREW_HOME", str(ws.path))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    import app.server as server
    importlib.reload(server)
    with TestClient(server.app) as c:
        yield c


def test_dashboard_serves_and_state_is_audited(client):
    assert "CloseCrew" in client.get("/").text
    s = client.get("/api/state").json()
    assert s["summary"]["status"] == "AWAITING_APPROVAL"
    assert all(c["ok"] for c in s["audit"])
    assert client.get("/api/health").json()["ok"]


def test_approve_everything_from_the_web(client):
    s = client.get("/api/state").json()
    for x in [x for x in s["exceptions"] if x["status"] == "open"]:
        r = client.post("/api/decide", json={"id": x["id"], "status": "approved", "by": "Judge"})
        assert r.status_code == 200, r.text
        s = r.json()
    assert s["summary"]["status"] == "CLOSED" and s["summary"]["diff_after"] == 0
    assert "applied by Judge" in client.get("/download/ledger_reconciled.csv").text


def test_cannot_decide_twice_or_on_unknown_items(client):
    s = client.get("/api/state").json()
    x = next(x for x in s["exceptions"] if x["status"] == "open")
    assert client.post("/api/decide", json={"id": x["id"], "status": "approved"}).status_code == 200
    assert client.post("/api/decide", json={"id": x["id"], "status": "approved"}).status_code == 404
    assert client.post("/api/decide", json={"id": "EXC-NOPE", "status": "approved"}).status_code == 404
    assert client.post("/api/decide", json={"id": x["id"], "status": "maybe"}).status_code == 400


def test_token_protects_approvals(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    s = client.get("/api/state").json()
    x = next(x for x in s["exceptions"] if x["status"] == "open")
    assert client.post("/api/decide", json={"id": x["id"], "status": "approved"}).status_code == 401
    assert client.post("/api/decide?token=s3cret", json={"id": x["id"], "status": "approved"}).status_code == 200


def test_reset_and_bad_upload_recovers(client, ws):
    assert client.post("/api/reset").json()["summary"]["awaiting_approval"] > 0
    bad = {"ledger": ("l.csv", b"nope\n1\n"), "processor": ("p.csv", b"x\n"), "bank": ("b.csv", b"y\n")}
    assert client.post("/api/upload", files=bad).status_code == 422
    assert client.get("/api/state").json()["summary"]["checks_passed"] == 9


def test_good_upload_runs_on_customer_files(client, ws):
    files = {k: (n, (ws.path / "data" / n).read_bytes()) for k, n in
             (("ledger", "ledger.csv"), ("processor", "stripe_balance_transactions.csv"), ("bank", "bank_statement.csv"))}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200 and all(c["ok"] for c in r.json()["audit"])
