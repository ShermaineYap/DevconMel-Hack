import csv
import shutil
from pathlib import Path

import pytest

from closecrew.seed import Plan, generate

ROOT = Path(__file__).resolve().parent.parent


class Workspace:
    def __init__(self, path: Path):
        self.path = path
        (path / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "sources.yaml", path / "sources.yaml")
        shutil.copy(ROOT / "policy.yaml", path / "policy.yaml")

    @property
    def kw(self) -> dict:
        return {"config": self.path / "sources.yaml", "policy_path": self.path / "policy.yaml",
                "state_dir": self.path / "state", "write_log": False}

    def seed(self, seed: int = 42, plan: Plan | None = None) -> dict:
        return generate(self.path / "data", seed=seed, plan=plan)

    def write(self, name: str, header: list[str], rows: list[list]) -> None:
        with open(self.path / "data" / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    def set_policy(self, text_replacements: dict[str, str]) -> None:
        p = self.path / "policy.yaml"
        s = p.read_text()
        for a, b in text_replacements.items():
            assert a in s, a
            s = s.replace(a, b)
        p.write_text(s)


@pytest.fixture
def ws(tmp_path) -> Workspace:
    return Workspace(tmp_path)


LEDGER_H = ["id", "date", "description", "reference", "amount", "kind", "method", "customer"]
STRIPE_H = ["id", "created", "type", "amount", "fee", "net", "currency", "order_id", "customer", "description",
            "payout_id", "available_on", "arrival"]
BANK_H = ["id", "date", "description", "amount"]


def charge(id, day, amount, order, customer, fee=None, payout=""):
    fee = fee if fee is not None else round(amount * 0.03 + 1, 2)
    return [id, f"2026-10-{day:02d}", "charge", f"{amount:.2f}", f"{fee:.2f}", f"{amount - fee:.2f}", "myr",
            order, customer, f"Order {order}", payout, f"2026-10-{min(day + 2, 31):02d}", ""]


def sale(id, day, amount, ref, customer, desc=None):
    return [id, f"2026-10-{day:02d}", desc or f"Sale {ref} - {customer}", ref, f"{amount:.2f}", "sale", "card",
            customer]
