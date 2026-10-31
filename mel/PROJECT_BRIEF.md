# Project brief for Mel's project memory

**What:** CloseCrew, a team of agents that does month-end reconciliation for a small business: books (ledger CSV)
vs card processor (Stripe test mode) vs bank statement.

**Pipeline (closecrew/pipeline.py is the lead):** Ingest → Matcher → Investigator → Fixer → Auditor → Explainer.

**Non-negotiables — never break these:**
1. All money is integer cents. Never use floats for amounts.
2. Never modify the owner's original ledger (`data/ledger.csv`). Fixes go to `state/ledger_reconciled.csv` + `state/ledger.diff`.
3. Autonomy only comes from `policy.yaml`. Agents must not edit it; only the human does.
4. Every exception must cite source rows and carry its exact signed impact; the Auditor proves Σ impacts == difference.
5. Anything ambiguous, low-confidence, or outside policy goes to a human. No guessing.
6. No real money: Stripe test mode only (`sk_test_`); live keys must be refused.
7. LLMs only write English; any amount in model text must exist in the Auditor's numbers.
8. Every change ships with a test. `python -m pytest -q` and `python -m closecrew run` (9/9 checks) must pass.

**Useful commands:** `make demo` · `python -m closecrew pending` · `python -m closecrew approve EXC-…` · `make serve`
