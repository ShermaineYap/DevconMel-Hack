# Submission draft

Submit at **https://www.globalaihackathon.com/submissions** (and Devpost if asked).
Submit the **Mel-built repo**, not this prototype (see `mel/BUILD_FROM_SCRATCH.md`).

Deadline: **Sunday Nov 1, 2:00 PM EST = Monday Nov 2, 3:00 AM Malaysia time.** Aim to submit by 1:30 AM MYT.

## Checklist (from globalaihackathon.com/rules)
- [ ] Builder name, contact email, track: Agentic Banking, Finance & Payments
- [ ] **Public repo**: https://github.com/ShermaineYap/closecrew (Mel-built)
- [ ] **Live deployed link** (Render)
- [ ] **Mel session recording** (video ≤ 5 min) — REQUIRED, no recording = not accepted
- [ ] Mel session export .zip (⋯ → Export conversation → tick both → save)
- [ ] **Demo video ≤ 5 min** (include customer reaction + passing tests)
- [ ] **Description ≤ 300 characters**
- [ ] Up to 3 attachments: agent work log, test output screenshot, customer quote
- [ ] Four Mel ratings + consent box
- [ ] Sunday curveball shipped

> The write-up below describes the old prototype. Rewrite it from what **Mel** actually builds.

---

## Project name
CloseCrew: Agents on Duty for month-end close

## Tagline
A crew of AI agents that reconciles a small business's books against Stripe and the bank, fixes the small stuff inside the owner's rules, and proves every ringgit to the cent.

## Inspiration
Small business owners in Malaysia sell through cards, e-wallets and bank transfers, then spend an evening every month matching a spreadsheet against payouts that arrive net of fees, refunds and timing gaps. Mistakes are invisible until the accountant (or the taxman) finds them. <!-- add your customer's quote here -->

## What it does
CloseCrew is a team of six agents with separation of duties, like a real finance department:
- **Ingest** loads the ledger, Stripe (test mode) and the bank statement in parallel and validates them.
- **Matcher** pairs bookings with payments (exact → same order → fuzzy with a confidence score) and payouts with bank lines.
- **Investigator** names the cause of every mismatch: unbooked card fees, duplicate charges, unbooked refunds, digit-swap typos, FX rounding, sales never entered, card sales never paid, payouts in transit. Every finding cites the exact source rows and its exact ringgit impact.
- **Fixer** drafts journal entries as a reviewable diff. It applies only what the owner's `policy.yaml` allows (e.g. fees under RM 200, rounding under 5 sen) and sends everything else to her for one-tap approval on the dashboard or Telegram. It never edits her original spreadsheet.
- **Auditor**, an independent agent, recomputes everything from raw sources and checks 9 invariants, including *the difference equals the sum of open items to the cent* and *every auto-fix was within policy*. If any fails, the close is BLOCKED and the last decision rolls back.
- **Explainer** writes a plain-English close report. If an LLM writes the summary, any amount it mentions must match the Auditor's numbers or the text is discarded.

On our demo month (130 Stripe transactions), the books are off by RM 94.00. The crew traces 100% of it to 16 causes, auto-fixes 8, asks the owner about 7, and after her approvals the books agree with the money to RM 0.00.

## How we built it
Python (integer-cents money model), FastAPI dashboard, Telegram Bot API for approvals, Stripe test mode, pytest + Hypothesis. Built in **Mel**: a lead agent orchestrated parallel workers per module, Stripe connected via MCP, approvals on for anything outside the repo or touching `policy.yaml`, and every edit reviewed as a diff. <!-- add specifics + screenshots of your Mel session -->

## Proof
- Finds 16/16 planted problems with 0 false positives; 4/4 fuzzy matches correct
- Property test across random messy months; stress run of 300 months, 0 failures
- Red-team tests: look-alike payments, true vs false duplicates, over-rate fees, wrong bank amounts, live-key refusal, malformed files, hallucinated LLM amounts
- 30 automated tests passing

## Sunday curveball
<!-- "The customer asked for … We shipped … in N minutes, with test …" -->

## Challenges
Making "the agent is right" provable rather than plausible: we moved all money to integer cents and designed the exception model so impacts sum exactly to the difference, which lets an independent Auditor verify every step.

## What's next
Live bank feeds (e.g. Open Finance APIs), TnG/GrabPay/DuitNow adapters out of the box, Bahasa Malaysia reports, a scheduled nightly close with Telegram alerts.

## Built with
python, fastapi, stripe, telegram, mel, pytest, hypothesis, mcp

## Safety
Fake data and Stripe test mode only. No money moves without explicit human approval; live keys are refused. Not tax or investment advice.
