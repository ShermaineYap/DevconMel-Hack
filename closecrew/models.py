"""Shared data structures. Every amount is an integer number of cents (sen)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional


def money(cents: int, currency: str = "RM") -> str:
    """Format cents as a human string, e.g. -1250 -> '-RM 12.50'."""
    sign = "-" if cents < 0 else ""
    return f"{sign}{currency} {abs(cents) / 100:,.2f}"


def to_cents(value: str | float | int) -> int:
    """Parse '12.50', '-1,234.5', 12.5 into integer cents without float drift."""
    if isinstance(value, int):
        return value * 100
    s = str(value).strip().replace(",", "").replace("RM", "").replace("MYR", "").strip()
    if s == "":
        return 0
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()+ ")
    whole, _, frac = s.partition(".")
    frac = (frac + "00")[:2]
    cents = int(whole or "0") * 100 + int(frac)
    return -cents if neg else cents


@dataclass
class LedgerEntry:
    """A row in the owner's books (the spreadsheet a small business keeps)."""

    id: str
    date: date
    description: str
    reference: str  # order / invoice number, may be blank
    amount: int  # signed cents: sales +, refunds/fees -
    kind: str  # sale | refund | fee | adjustment | expense
    method: str  # card | cash | bank
    customer: str = ""
    row: int = 0  # 1-based row number in the source file, for citations
    source: str = "ledger.csv"

    def cite(self) -> str:
        return f"{self.source} row {self.row} ({self.id})"


@dataclass
class ProcessorTxn:
    """A balance transaction from a payment processor (Stripe, TnG, GrabPay...)."""

    id: str
    created: date
    type: str  # charge | refund | payout | adjustment
    amount: int  # gross, signed: charge +, refund -, payout -
    fee: int  # positive cents charged by the processor
    currency: str
    order_id: str
    customer: str
    description: str
    payout_id: str = ""  # payout that settled this txn (blank if pending)
    processor: str = "stripe"
    row: int = 0
    source: str = "stripe_balance_transactions.csv"
    available_on: Optional[date] = None
    arrival: Optional[date] = None  # payouts only

    @property
    def net(self) -> int:
        return self.amount - self.fee

    def cite(self) -> str:
        return f"{self.source} row {self.row} ({self.id})"


@dataclass
class BankLine:
    id: str
    date: date
    description: str
    amount: int
    row: int = 0
    source: str = "bank_statement.csv"

    def cite(self) -> str:
        return f"{self.source} row {self.row} ({self.id})"


@dataclass
class Match:
    left: str  # ledger id or payout id
    right: str  # processor txn id or bank line id
    kind: str  # ledger-processor | payout-bank
    method: str  # exact | reference | fuzzy
    confidence: float
    reason: str


@dataclass
class Exception_:
    """Something the books and the money disagree on, with its exact ringgit impact."""

    cause: str
    side: str  # processor (ledger vs processor) | bank (payouts vs bank)
    refs: list[str]
    impact: int  # signed cents contribution to the unexplained difference
    explanation: str
    evidence: list[str]
    confidence: float = 1.0
    proposed_entry: Optional[dict[str, Any]] = None
    action: str = ""  # recommended human action outside the ledger
    blocked: str = ""  # reason auto-fix is not allowed even if under cap
    decision: str = ""  # auto | approval | info (set by Fixer)
    decision_reason: str = ""
    status: str = "open"  # open | auto_fixed | approved | rejected | info
    id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.id:
            key = self.cause + "|" + "|".join(sorted(self.refs))
            self.id = "EXC-" + hashlib.sha1(key.encode()).hexdigest()[:8].upper()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["impact_display"] = money(self.impact)
        return d
