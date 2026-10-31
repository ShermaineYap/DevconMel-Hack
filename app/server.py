"""CloseCrew dashboard + approvals API.

Run locally:  uvicorn app.server:app --reload
Deploy:       see render.yaml / Dockerfile (needs no secrets; fake data only)
Optional env: DASHBOARD_TOKEN (require ?token= for approvals), TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from closecrew import pipeline
from closecrew.ingest import IngestError
from closecrew.seed import generate

ROOT = pipeline.home()
STATE = ROOT / "state"
DATA = ROOT / "data"
LOCK = threading.Lock()
MAX_UPLOAD = 2_000_000


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup()
    yield




def _auth(token: str | None) -> None:
    want = os.environ.get("DASHBOARD_TOKEN")
    if want and token != want:
        raise HTTPException(401, "approvals need the owner's token")


def _latest() -> dict:
    p = STATE / "latest.json"
    if not p.exists():
        with LOCK:
            return pipeline.run(note="first run on startup")
    return json.loads(p.read_text())


def startup() -> None:
    if not (DATA / "ledger.csv").exists():
        generate(DATA)
    with LOCK:
        pipeline.run(note="server start")
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        from closecrew.telegram_bot import poll_forever
        threading.Thread(target=poll_forever, daemon=True).start()


app = FastAPI(title="CloseCrew", version="0.1.0", lifespan=lifespan)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/state")
def state() -> dict:
    return _latest()


@app.get("/api/health")
def health() -> dict:
    s = _latest()["summary"]
    return {"ok": True, "status": s["status"], "checks": f"{s['checks_passed']}/{s['checks_total']}"}


@app.post("/api/run")
def run(x_token: str | None = Header(None), token: str | None = Query(None)) -> dict:
    _auth(x_token or token)
    with LOCK:
        return pipeline.run(note="run requested from dashboard")


class Decision(BaseModel):
    id: str
    status: str
    by: str = "owner"
    note: str = ""


@app.post("/api/decide")
def decide(d: Decision, x_token: str | None = Header(None), token: str | None = Query(None)) -> dict:
    _auth(x_token or token)
    if d.status not in ("approved", "rejected"):
        raise HTTPException(400, "status must be approved or rejected")
    if not any(x["id"] == d.id and x["status"] == "open" for x in _latest()["exceptions"]):
        raise HTTPException(404, f"{d.id} is not waiting for a decision")
    with LOCK:
        return pipeline.decide(d.id, d.status, by=d.by[:40] or "owner", note=d.note[:200])


@app.post("/api/reset")
def reset(seed: int = 42, x_token: str | None = Header(None), token: str | None = Query(None)) -> dict:
    _auth(x_token or token)
    with LOCK:
        shutil.rmtree(STATE, ignore_errors=True)
        generate(DATA, seed=seed)
        return pipeline.run(note=f"demo reset (seed {seed})")


@app.post("/api/upload")
async def upload(ledger: UploadFile = File(...), processor: UploadFile = File(...), bank: UploadFile = File(...),
                 x_token: str | None = Header(None), token: str | None = Query(None)) -> JSONResponse:
    """Run the crew on edited copies of the sample CSVs. Fake data only (track rule): never real customer data."""
    _auth(x_token or token)
    blobs = {}
    for name, f in (("ledger.csv", ledger), ("stripe_balance_transactions.csv", processor),
                    ("bank_statement.csv", bank)):
        b = await f.read()
        if len(b) > MAX_UPLOAD:
            raise HTTPException(413, f"{name} too large")
        blobs[name] = b
    backup = DATA.with_name("data_backup")
    with LOCK:
        shutil.rmtree(backup, ignore_errors=True)
        shutil.copytree(DATA, backup)
        for name, b in blobs.items():
            (DATA / name).write_bytes(b)
        shutil.rmtree(STATE, ignore_errors=True)
        try:
            res = pipeline.run(note="run on uploaded files")
        except (IngestError, KeyError, ValueError) as e:
            shutil.rmtree(DATA)
            shutil.copytree(backup, DATA)
            pipeline.run(note="restored demo data after a bad upload")
            raise HTTPException(422, f"could not read your files: {e}")
    return JSONResponse(res)


@app.get("/api/report", response_class=PlainTextResponse)
def report() -> str:
    _latest()
    return (STATE / "close_report.md").read_text()


@app.get("/api/log", response_class=PlainTextResponse)
def log() -> str:
    p = STATE / "AGENT_LOG.md"
    return p.read_text() if p.exists() else ""


@app.get("/download/{name}")
def download(name: str) -> FileResponse:
    allowed = {"ledger_reconciled.csv", "ledger.diff", "close_report.md", "AGENT_LOG.md"}
    if name not in allowed or not (STATE / name).exists():
        raise HTTPException(404)
    return FileResponse(STATE / name, filename=name)
