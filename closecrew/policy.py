"""The owner's policy: the only place autonomy is granted. Editable YAML, hashed per run."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

INFO_CAUSES = {"payout_in_transit"}


@dataclass
class Policy:
    currency: str = "RM"
    auto_fix: dict[str, int] = field(default_factory=dict)  # cause -> max abs cents
    date_window_days: int = 2
    fuzzy_accept: float = 0.75
    ambiguity_margin: float = 0.05
    min_auto_confidence: float = 1.0
    fee_bps: int = 300
    fee_fixed: int = 100
    fee_tolerance: int = 1
    rounding_max: int = 50  # a ref-matched difference up to this is treated as FX/rounding
    processor_keywords: list[str] = field(default_factory=lambda: ["STRIPE"])
    sha256: str = ""

    def decide(self, cause: str, impact: int, confidence: float = 1.0, blocked: str = "") -> tuple[str, str]:
        """Return (decision, reason). decision is auto | approval | info."""
        if cause in INFO_CAUSES:
            return "info", "informational only, no ledger change needed"
        if blocked:
            return "approval", blocked
        if cause not in self.auto_fix:
            return "approval", f"policy requires a human for '{cause}'"
        cap = self.auto_fix[cause]
        if abs(impact) > cap:
            return "approval", f"{abs(impact) / 100:.2f} is above the auto-fix cap of {cap / 100:.2f}"
        if confidence < self.min_auto_confidence:
            return "approval", f"confidence {confidence:.2f} below {self.min_auto_confidence:.2f}"
        return "auto", f"'{cause}' within policy cap of {cap / 100:.2f}"


def load_policy(path: str | Path) -> Policy:
    raw = Path(path).read_bytes()
    cfg = yaml.safe_load(raw) or {}
    m = cfg.get("matching", {})
    fees = cfg.get("fees", {})
    auto = {k: int(round(float(v["max"]) * 100)) for k, v in (cfg.get("auto_fix") or {}).items()}
    return Policy(
        currency=cfg.get("currency_symbol", "RM"),
        auto_fix=auto,
        date_window_days=int(m.get("date_window_days", 2)),
        fuzzy_accept=float(m.get("fuzzy_accept", 0.75)),
        ambiguity_margin=float(m.get("ambiguity_margin", 0.05)),
        min_auto_confidence=float(cfg.get("min_auto_confidence", 1.0)),
        fee_bps=int(round(float(fees.get("percent", 3.0)) * 100)),
        fee_fixed=int(round(float(fees.get("fixed", 1.0)) * 100)),
        fee_tolerance=int(round(float(fees.get("tolerance", 0.01)) * 100)),
        rounding_max=int(round(float(m.get("rounding_max", 0.50)) * 100)),
        processor_keywords=[k.upper() for k in cfg.get("processor_keywords", ["STRIPE"])],
        sha256=hashlib.sha256(raw).hexdigest(),
    )
