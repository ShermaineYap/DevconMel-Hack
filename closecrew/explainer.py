"""Explainer agent: write the close report an owner (or her accountant) can read.

Numbers come only from the Auditor. If a language model is configured it may
write a short summary, but any amount it mentions must appear in the audited
numbers or the summary is thrown away and a template is used instead.
"""

from __future__ import annotations

import re
from collections import Counter

from . import llm
from .auditor import AuditReport
from .fixer import FixEntry
from .models import Exception_, money

LABELS = {
    "processor_fee": "Card processing fees not booked",
    "missing_ledger_entry": "Sale paid but never entered",
    "duplicate_charge": "Customer charged twice",
    "refund_not_booked": "Refund not in the books",
    "transposition": "Typo: digits swapped",
    "rounding": "FX / rounding difference",
    "amount_mismatch": "Amount differs (unknown cause)",
    "ledger_without_payment": "Card sale with no payment",
    "refund_without_processor": "Refund never processed",
    "ambiguous_match": "Could match several payments",
    "processor_adjustment": "Processor adjustment",
    "ledger_fee_unlinked": "Fee booked against no payout",
    "payout_in_transit": "Payout still in transit",
    "payout_missing": "Payout missing from bank",
    "bank_unmatched_processor": "Unexplained processor deposit",
}

AMOUNT_RE = re.compile(r"(?:RM|MYR)\s?-?\(?([\d,]+\.\d{2})")


def status_of(audit: AuditReport, exceptions: list[Exception_]) -> str:
    if not audit.passed:
        return "BLOCKED"
    if any(x.status == "open" for x in exceptions):
        return "AWAITING_APPROVAL"
    return "CLOSED"


def summary(audit: AuditReport, exceptions: list[Exception_], fixes: list[FixEntry], match_stats: dict,
            n_ledger: int, n_txns: int) -> dict:
    by_status = Counter(x.status for x in exceptions)
    matched = sum(match_stats.values())
    return {
        "status": status_of(audit, exceptions),
        "processor_net": audit.processor_net, "ledger_before": audit.ledger_before,
        "ledger_after": audit.ledger_after, "diff_before": audit.diff_before, "diff_after": audit.diff_after,
        "bank_diff": audit.bank_diff, "matches": match_stats, "matched_total": matched,
        "ledger_rows_in_scope": n_ledger, "processor_txns_in_scope": n_txns,
        "exceptions": len(exceptions), "auto_fixed": by_status.get("auto_fixed", 0),
        "approved": by_status.get("approved", 0), "awaiting_approval": by_status.get("open", 0),
        "rejected": by_status.get("rejected", 0), "info": by_status.get("info", 0),
        "auto_fixed_amount": sum(f.amount for f in fixes if f.applied_by == "policy"),
        "checks_passed": sum(c.ok for c in audit.checks), "checks_total": len(audit.checks),
    }


def template_narrative(s: dict) -> str:
    head = {"CLOSED": "October is closed.", "AWAITING_APPROVAL": "The month is almost closed.",
            "BLOCKED": "The close is blocked: the Auditor found a problem and nothing was published."}[s["status"]]
    parts = [head,
             f"The card processor shows {money(s['processor_net'])} of net card income; the books started at "
             f"{money(s['ledger_before'])}, a gap of {money(s['diff_before'])}.",
             f"Every ringgit of that gap is traced to {s['exceptions']} specific causes, and {s['auto_fixed']} small "
             f"ones were fixed inside your policy."]
    if s["awaiting_approval"]:
        parts.append(f"The {s['awaiting_approval']} item(s) waiting for your decision account for the remaining "
                     f"{money(s['diff_after'])}.")
    elif s["diff_after"] == 0:
        parts.append("Books and money now agree to the cent.")
    else:
        parts.append(f"The remaining {money(s['diff_after'])} is from item(s) you chose not to post, "
                     f"kept on record as an acknowledged difference.")
    return " ".join(parts)


def allowed_amounts(s: dict, exceptions: list[Exception_]) -> set[str]:
    vals = [s["processor_net"], s["ledger_before"], s["ledger_after"], s["diff_before"], s["diff_after"],
            s["bank_diff"], s["auto_fixed_amount"]] + [x.impact for x in exceptions]
    return {f"{abs(v) / 100:,.2f}" for v in vals} | {f"{abs(v) / 100:.2f}" for v in vals}


def narrative(s: dict, exceptions: list[Exception_]) -> tuple[str, str]:
    """Return (text, source) where source is 'llm' or 'template'."""
    if not llm.available():
        return template_narrative(s), "template"
    facts = template_narrative(s) + "\n" + "\n".join(
        f"- {LABELS.get(x.cause, x.cause)}: {money(x.impact)} ({x.status})" for x in exceptions)
    text = llm.complete(
        "You write a 3-sentence month-end summary for a small business owner in plain, warm English. "
        "Use ONLY the amounts given, written exactly as given (RM x.xx). No advice on tax or investments.",
        facts)
    if not text:
        return template_narrative(s), "template"
    ok = allowed_amounts(s, exceptions)
    if any(a not in ok for a in AMOUNT_RE.findall(text)):
        return template_narrative(s), "template (model text rejected: amount not in audited numbers)"
    return text.strip(), "llm (amounts verified)"


def report_markdown(period: str, s: dict, audit: AuditReport, exceptions: list[Exception_],
                    fixes: list[FixEntry], narration: str) -> str:
    L = [f"# Month-end close: {period}", "", f"**Status: {s['status'].replace('_', ' ')}**", "", narration, "",
         "## Reconciliation statement", "", "| | Amount |", "|---|---:|",
         f"| Net card income per processor | {money(s['processor_net'])} |",
         f"| Card income per books (before) | {money(s['ledger_before'])} |",
         f"| **Difference before** | **{money(s['diff_before'])}** |"]
    for cause, label in LABELS.items():
        xs = [x for x in exceptions if x.cause == cause and x.side == "processor"]
        if xs:
            L.append(f"| {label} ({len(xs)}) | {money(sum(x.impact for x in xs))} |")
    L += [f"| **Explained** | **{money(sum(x.impact for x in exceptions if x.side == 'processor'))}** |",
          f"| Fixes posted | {money(sum(f.amount for f in fixes))} |",
          f"| **Difference after fixes** | **{money(s['diff_after'])}** |", "",
          "## What the crew fixed", ""]
    done = [x for x in exceptions if x.status in ("auto_fixed", "approved")]
    L += [f"- `{x.id}` {LABELS.get(x.cause, x.cause)} · {money(x.impact)} · {x.decision_reason}" for x in done] or ["- nothing"]
    L += ["", "## Needs your decision", ""]
    todo = [x for x in exceptions if x.status == "open"]
    for x in todo:
        L.append(f"- `{x.id}` **{LABELS.get(x.cause, x.cause)}** · {money(x.impact)}: {x.explanation}"
                 + (f" Suggested action: {x.action}." if x.action else ""))
    if not todo:
        L.append("- nothing")
    L += ["", "## For information", ""]
    L += [f"- {x.explanation}" for x in exceptions if x.status in ("info", "rejected")] or ["- nothing"]
    L += ["", "## Auditor checks", ""]
    L += [f"- {'PASS' if c.ok else 'FAIL'} · {c.name}: {c.detail}" for c in audit.checks]
    L += ["", "_Prepared by CloseCrew. Test data and sandbox payments only. Not tax or investment advice._", ""]
    return "\n".join(L)
