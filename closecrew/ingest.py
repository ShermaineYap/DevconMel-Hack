"""Ingest agent: load every source into clean, typed records and check them.

Adapters are chosen in `sources.yaml`, so adding a new payment source (the most
likely Sunday curveball) is a config change plus, at most, a column mapping.
"""

from __future__ import annotations

import csv
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from .models import BankLine, LedgerEntry, ProcessorTxn, to_cents


class IngestError(ValueError):
    pass


def _d(s: str) -> date:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    if s.isdigit():  # unix timestamp (Stripe API)
        return datetime.fromtimestamp(int(s), timezone.utc).date()
    raise IngestError(f"unrecognised date: {s!r}")


def _rows(path: Path, required: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise IngestError(f"missing file: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in required if c not in cols]
        if missing:
            raise IngestError(f"{path.name}: missing columns {missing}")
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in reader]


# ---- adapters ---------------------------------------------------------------

def ledger_csv(cfg: dict, base: Path) -> list[LedgerEntry]:
    path = base / cfg["path"]
    out = []
    for i, r in enumerate(_rows(path, ["id", "date", "description", "amount", "kind", "method"]), start=2):
        out.append(LedgerEntry(id=r["id"], date=_d(r["date"]), description=r["description"],
                               reference=r.get("reference", ""), amount=to_cents(r["amount"]),
                               kind=r["kind"].lower(), method=r["method"].lower(),
                               customer=r.get("customer", ""), row=i, source=path.name))
    return out


def stripe_csv(cfg: dict, base: Path) -> list[ProcessorTxn]:
    path = base / cfg["path"]
    name = cfg.get("name", "stripe")
    out = []
    for i, r in enumerate(_rows(path, ["id", "created", "type", "amount", "fee"]), start=2):
        out.append(ProcessorTxn(
            id=r["id"], created=_d(r["created"]), type=r["type"].lower(), amount=to_cents(r["amount"]),
            fee=to_cents(r["fee"]), currency=r.get("currency", "myr"), order_id=r.get("order_id", ""),
            customer=r.get("customer", ""), description=r.get("description", ""),
            payout_id=r.get("payout_id", ""), processor=name, row=i, source=path.name,
            available_on=_d(r["available_on"]) if r.get("available_on") else None,
            arrival=_d(r["arrival"]) if r.get("arrival") else None))
    return out


def generic_csv(cfg: dict, base: Path) -> list[ProcessorTxn]:
    """Any wallet/processor export (TnG eWallet, GrabPay, PayPal...) via a column mapping.

    sources.yaml example:
      adapter: generic_csv
      name: tng
      path: data/tng_export.csv
      mapping: {id: "Transaction ID", created: "Date", amount: "Amount", fee: "MDR Fee",
                type: "Type", order_id: "Merchant Ref", customer: "Payer", payout_id: "Settlement ID"}
      type_map: {"Payment": charge, "Refund": refund, "Settlement": payout}
      fee_is_negative: false
    """
    path = base / cfg["path"]
    m: dict[str, str] = cfg["mapping"]
    tmap = {k.lower(): v for k, v in cfg.get("type_map", {}).items()}
    name = cfg.get("name", path.stem)
    out = []
    for i, r in enumerate(_rows(path, [m["id"], m["created"], m["amount"]]), start=2):
        raw_type = r.get(m.get("type", ""), "charge") or "charge"
        typ = tmap.get(raw_type.lower(), raw_type.lower())
        amount = to_cents(r[m["amount"]])
        if typ in ("refund", "payout") and amount > 0:
            amount = -amount
        fee = abs(to_cents(r.get(m.get("fee", ""), "0") or "0"))
        tid = f"{name}:{r[m['id']]}"
        raw_payout = r.get(m.get("payout_id", ""), "")
        payout_id = f"{name}:{raw_payout}" if raw_payout else (tid if typ == "payout" else "")
        out.append(ProcessorTxn(
            id=tid, created=_d(r[m["created"]]), type=typ, amount=amount, fee=fee,
            currency=cfg.get("currency", "myr"), order_id=r.get(m.get("order_id", ""), ""),
            customer=r.get(m.get("customer", ""), ""), description=r.get(m.get("description", ""), raw_type),
            payout_id=payout_id, processor=name, row=i, source=path.name))
    return out


def stripe_api(cfg: dict, base: Path) -> list[ProcessorTxn]:
    """Pull balance transactions live from Stripe TEST mode. Refuses live keys."""
    import httpx

    key = os.environ.get(cfg.get("key_env", "STRIPE_SECRET_KEY"), "")
    if not key.startswith(("sk_test_", "rk_test_")):
        raise IngestError("stripe_api adapter only runs with a TEST mode key (sk_test_/rk_test_)")
    period = cfg["period"]
    y, mth = map(int, period.split("-"))
    gte = int(datetime(y, mth, 1, tzinfo=timezone.utc).timestamp())
    lt = int(datetime(y + (mth == 12), mth % 12 + 1, 1, tzinfo=timezone.utc).timestamp())
    out: list[ProcessorTxn] = []
    params: dict[str, Any] = {"limit": 100, "created[gte]": gte, "created[lt]": lt,
                              "expand[]": "data.source"}
    with httpx.Client(base_url="https://api.stripe.com/v1", auth=(key, ""), timeout=30) as c:
        while True:
            resp = c.get("/balance_transactions", params=params)
            resp.raise_for_status()
            body = resp.json()
            for t in body["data"]:
                src = t.get("source") or {}
                meta = src.get("metadata", {}) if isinstance(src, dict) else {}
                typ = {"payment": "charge", "charge": "charge", "refund": "refund",
                       "payout": "payout"}.get(t["type"], "adjustment")
                billing = (src.get("billing_details") or {}) if isinstance(src, dict) else {}
                out.append(ProcessorTxn(
                    id=t["id"], created=datetime.fromtimestamp(t["created"], timezone.utc).date(), type=typ,
                    amount=t["amount"], fee=t["fee"], currency=t["currency"],
                    order_id=meta.get("order_id", ""), customer=billing.get("name") or meta.get("customer", ""),
                    description=t.get("description") or "", payout_id=meta.get("payout_id", ""),
                    processor="stripe", row=len(out) + 1, source="stripe:api",
                    available_on=datetime.fromtimestamp(t["available_on"], timezone.utc).date()))
            if not body.get("has_more"):
                break
            params["starting_after"] = body["data"][-1]["id"]
    return out


def bank_csv(cfg: dict, base: Path) -> list[BankLine]:
    path = base / cfg["path"]
    out = []
    for i, r in enumerate(_rows(path, ["date", "description", "amount"]), start=2):
        out.append(BankLine(id=r.get("id") or f"BNK-{i - 1:04d}", date=_d(r["date"]),
                            description=r["description"], amount=to_cents(r["amount"]), row=i,
                            source=path.name))
    return out


ADAPTERS: dict[str, Callable[[dict, Path], list]] = {
    "ledger_csv": ledger_csv, "stripe_csv": stripe_csv, "stripe_api": stripe_api,
    "generic_csv": generic_csv, "bank_csv": bank_csv,
}


# ---- the agent --------------------------------------------------------------

@dataclass
class Dataset:
    period: str
    ledger: list[LedgerEntry]
    processor: list[ProcessorTxn]
    bank: list[BankLine]
    checks: list[str] = field(default_factory=list)

    @property
    def period_start(self) -> date:
        y, m = map(int, self.period.split("-"))
        return date(y, m, 1)

    @property
    def period_end(self) -> date:
        y, m = map(int, self.period.split("-"))
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        return date.fromordinal(nxt.toordinal() - 1)


def load_sources(config_path: str | Path, base: str | Path | None = None) -> Dataset:
    config_path = Path(config_path)
    base = Path(base) if base else config_path.parent
    cfg = yaml.safe_load(config_path.read_text())
    period = str(cfg["period"])
    src = cfg["sources"]
    processors = [src["processor"]] + list(src.get("extra_processors") or [])
    for p in processors:
        p.setdefault("period", period)

    jobs = {"ledger": (src["ledger"], None)} | {f"processor{i}": (p, None) for i, p in enumerate(processors)} \
        | {"bank": (src["bank"], None)}
    # Sources are independent, so load them in parallel like a mini agent team.
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {k: pool.submit(ADAPTERS[c["adapter"]], c, base) for k, (c, _) in jobs.items()}
        results = {k: f.result() for k, f in futures.items()}

    processor: list[ProcessorTxn] = []
    for i in range(len(processors)):
        processor.extend(results[f"processor{i}"])
    ds = Dataset(period=period, ledger=results["ledger"], processor=processor, bank=results["bank"])
    ds.checks = validate(ds)
    return ds


def validate(ds: Dataset) -> list[str]:
    """Schema-level self checks. Raises on anything that would make matching unsafe."""
    checks = []
    for name, recs in (("ledger", ds.ledger), ("processor", ds.processor), ("bank", ds.bank)):
        ids = [r.id for r in recs]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise IngestError(f"{name}: duplicate ids {sorted(dupes)[:5]}")
        checks.append(f"{name}: {len(recs)} rows, ids unique")
    bad = [t.id for t in ds.processor if t.type not in ("charge", "refund", "payout", "adjustment")]
    if bad:
        raise IngestError(f"processor: unknown txn types on {bad[:5]}")
    neg_fee = [t.id for t in ds.processor if t.fee < 0]
    if neg_fee:
        raise IngestError(f"processor: negative fees on {neg_fee[:5]}")
    wrong_sign = [t.id for t in ds.processor if (t.type == "charge" and t.amount <= 0)
                  or (t.type in ("refund", "payout") and t.amount >= 0)]
    if wrong_sign:
        raise IngestError(f"processor: amount sign wrong for type on {wrong_sign[:5]}")
    checks.append("processor: types valid, fees non-negative, signs consistent")
    return checks
