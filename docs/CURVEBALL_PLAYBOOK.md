# Curveball playbook

The curveball lands **Sunday 8:00 AM EST = Sunday 9:00 PM Malaysia time**. Submissions close **2:00 PM EST =
Monday 3:00 AM MYT**. You have ~6 hours. Most likely requests for a reconciliation customer, and the fastest path:

| If the customer asks… | Path | Time |
|---|---|---|
| **"We also take TnG / GrabPay / PayPal / DuitNow QR"** | Add an `extra_processors` entry in `sources.yaml` with `adapter: generic_csv` and a column `mapping`; add its keyword to `processor_keywords` in `policy.yaml`. Already tested in `test_new_wallet_source_plugs_in_by_config`. Make a fake export in `data/`. | 30–45 min |
| **"Handle chargebacks / disputes"** | Processor `adjustment` rows already become `processor_adjustment` exceptions (human). Add a `dispute` cause in `investigator.py` when description contains "dispute"; seed one in `seed.py`; add a test. | 1 h |
| **"Give my accountant a monthly PDF / Excel"** | Render `state/close_report.md` to PDF (e.g. `markdown` + `weasyprint`) or export `ledger_reconciled.csv` + exceptions to xlsx (`openpyxl`); add a `/download/close_report.pdf` route. | 45 min |
| **"Multiple currencies"** | Ingest already keeps `currency`; add a `fx_rates` block to `sources.yaml`, convert to MYR in `ingest.py` before matching, and widen `rounding_max`. Add a test with an SGD charge. | 1–1.5 h |
| **"Alert me when something's wrong"** | Telegram bot exists (`CLOSECREW_NOTIFY=telegram`). Add a daily scheduled run (Render cron job running `python -m closecrew run`). | 30 min |
| **"Explain it in Malay"** | `report_markdown(..., lang="ms")` with a BM label table; LLM narration with `"Write in Bahasa Malaysia"` (numbers still verified). | 45 min |
| **"SST summary"** | Sum taxable sales from the reconciled ledger; show as a report section **labelled informational, not tax advice**. | 45 min |
| **"Partial payments / instalments"** | Matcher pass 2b: group unmatched charges by `order_id`, accept if Σ == ledger amount; new red-team test. | 1 h |

## Routine for any curveball
1. Paste the request into Mel with the prompt in `mel/MEL_PLAYBOOK.md` §6 (parallel workers, diffs, approvals).
2. Write the test **first** (it's your "proof that tests passed").
3. `python -m pytest -q` and `python -m closecrew run` → 9/9 checks.
4. Add one line to the README "Proof it works" and one bullet to the Devpost write-up: *"Sunday curveball: … shipped in X minutes."*
5. Redeploy (Render redeploys on push), reset demo, re-record the 20-second curveball clip.
