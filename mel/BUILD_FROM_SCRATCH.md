# Build CloseCrew A to Z in Mel

Repo for the build: **https://github.com/ShermaineYap/closecrew** (public, empty: Mel makes every commit).
All times are Malaysia time (MYT). Deadline **Monday 3:00 AM** (Sun 2 PM EST). Curveball **Sunday 9:00 PM**.

## The rules that matter (globalaihackathon.com/rules)
- **Mel only.** "Not allowed: building with another AI coding agent or assistant." That includes Claude, ChatGPT,
  Copilot and Cursor for writing or debugging code. When something breaks, ask **Mel** to fix it.
- **No pre-written application code.** Ideas and notes (like `SPEC.md`) are allowed. The old prototype repo
  (DevconMel-Hack) is **not**: don't open it in Mel, copy from it, or link it in the submission.
- **Required to submit:** builder name · contact email · **public repo** · **live deployed link** ·
  **Mel session recording** (no recording = not accepted) · **demo video ≤ 5 min** · **description ≤ 300 chars** ·
  consent box. Optional but strongly recommended: the **Mel session export (.zip)**.
- Mel sessions during the hackathon are recorded by Mel for training.

## Timeline (MYT, Sunday)
| By | Done |
|---|---|
| 12:30 PM | Mel installed, signed in, credits email sent ✅, screen recorder running |
| 1:00 PM | Stage 1 plan approved |
| 2:00 PM | Stage 2 tests and fake data |
| 4:30 PM | Stages 3–4 crew built, tests green |
| 5:00 PM | Stage 5 red team |
| 6:30 PM | Stage 6 dashboard |
| 7:30 PM | Stage 8 deployed on Render (live link) · Stage 7 Stripe if time |
| 8:30 PM | Real person tries it (Stage 9) |
| 9:00 PM | **Curveball** (Stage 10) |
| 11:30 PM | Curveball shipped, redeployed |
| 1:00 AM | Videos recorded, session exported |
| **1:30 AM** | **Submitted** (hard close 3:00 AM) |

**If credits haven't arrived:** Mel is free on your own model key ("bring your own model"), so you can start with
your own API key and switch once credits land. Ask in the WhatsApp group if you're blocked.

## 0. Setup (15 min)
1. Install Mel from https://www.openmel.dev/download and sign up **with the same email you registered with**.
2. Email hello@openmel.dev **from that address**, subject `Hackathon credits` (draft at the bottom).
3. `git clone https://github.com/ShermaineYap/closecrew` into an empty folder and open that folder in Mel.
4. Copy **only** `SPEC.md` into the folder. It's your idea notes and is allowed. Rewrite any part in your own words if you like.
5. In Mel's settings, turn on approvals for: shell commands outside the folder, `git push`, and any edit to
   `policy.yaml`. Leave diff review on for every edit.
6. Start screen recording (OBS, or Win+G on Windows, or Cmd+Shift+5 on Mac) and keep it running for every stage.
   The **Mel session video** (≤ 5 min) is required, so you'll cut it from this footage.
7. Keep the whole build in as few Mel sessions as possible. At the end you'll export each one
   (⋯ top corner → Export conversation → tick both boxes → save) for the session .zip.

## Stage 1. Plan (Mel's plan step), ~20 min
```
Read SPEC.md. I'm the owner's developer. Plan the build before writing any code:
the folder layout, the data model (money as integer cents), how each of the six agents works, the order you'll
build them in, and the test list mapped to the 10 acceptance criteria. Write the plan to PLAN.md.
Ask me anything that's unclear. Don't write code yet.
```
Read the plan, push back on anything you don't like, then approve it. **Screenshot it.**

## Stage 2. Tests and fake data first, ~45 min
```
Following PLAN.md: build the fake-data generator (one month, the planted mistakes from SPEC.md,
ground_truth.json) and write the tests for all 10 acceptance criteria, using pytest. They'll fail for now.
Run them and show me the failures.
```

## Stage 3. Build the crew in parallel (the headline Mel moment), ~1.5–2 h
Use `/orchestrate-agent`:
```
Build the crew from PLAN.md in parallel. One worker per part, each owning only its own files:
1. Ingest + Matcher
2. Investigator
3. Fixer + policy.yaml loader (do not change the caps in policy.yaml)
4. Auditor (independent: recompute from the raw files, don't import the other agents' results)
5. Explainer + agent work log
Shared memory: money is integer cents; never edit the original ledger; every exception cites rows.
Integrate, then run the full test suite. Show me each worker's diff before applying it.
```
**Record the parallel panes.** This is your best "Use of Mel" clip.

## Stage 4. Debug until green, ~1 h
```
Run the tests. For each failure, investigate the cause, propose the fix as a diff, and wait for my approval.
Repeat until every acceptance test passes. Then run the crew on 20 random generated months and report any failure.
```

## Stage 5. Red team, ~30 min
```
Act as an attacker against the Matcher and Investigator. Add red-team tests: look-alike payments,
a true vs a false duplicate, a fee above the agreed rate, a payout that doesn't match the bank, a live Stripe key,
a broken CSV. Run them, then fix any failure as a diff for my approval.
```

## Stage 6. Dashboard and approvals, ~1.5 h
```
Build the web dashboard described in SPEC.md (FastAPI + one HTML page is fine): the difference before and after,
the six agents' status, an approval queue with evidence and Approve/Reject, the reconciliation statement,
the Auditor checks, the ledger diff, the agent work log, and a "generate a new random month" button.
Every Approve re-runs the crew and the Auditor; roll back if any check fails. Add API tests.
```

## Stage 7. Stripe test mode + MCP (optional, ~45 min)
1. In the Stripe dashboard (test mode / sandbox): Developers → API keys → **create a restricted key** (`rk_test_…`)
   with read access to charges, payment intents, balance transactions and payouts, and **write access to refunds only**.
   Enable MCP for the sandbox under Settings → MCP.
2. In Mel's MCP settings, add Stripe: hosted `https://mcp.stripe.com/` (OAuth), or local
   `npx -y @stripe/mcp` with env `STRIPE_SECRET_KEY=rk_test_…`.
3. Prompt:
```
Using ordinary Stripe API calls from a small script (TEST mode, key from an env var), create 20 test
payments that mirror part of our generated month, including one duplicate charge. Then add an ingest option
that reads balance transactions from Stripe test mode, and refuse any key that isn't a test key.
Finally, when the owner approves a "customer charged twice" item, use the Stripe MCP create_refund tool to
refund that test charge, but only after my approval in Mel. Show me the tool call before it runs.
```
Recording **Mel's approval prompt pausing before an MCP refund** is the strongest single proof of
"a human approves before money moves" plus "MCP" for the Use-of-Mel score.

## Stage 8. Ship, ~45 min
```
Add a README (problem, crew diagram, how to run, proof), a Dockerfile, and a render.yaml for a free Render deploy.
Run all tests one final time, commit, and push. Ask me before pushing.
```
Then deploy on Render (New → Blueprint → your repo) to get the public link.

## Stage 9. Real person + the agents on duty (~45 min)
**Real person (required by the brief):** send them the live link early (message below), and get a short
clip or quote plus their permission. Fake data only: they try the demo month, never their real books.

**Agents on duty in Mel:** record Mel operating the close for the owner:
```
You are the month-end close team for our customer. Run the crew on this month's data. Then, in parallel:
one worker re-checks the evidence for the 3 largest open items against the source CSVs, one independently
recomputes the books-vs-Stripe difference and runs the tests, one drafts a 5-line WhatsApp update for the owner
using only the audited numbers. Then walk me through each open item; approve or reject only after my explicit yes,
and stop if any Auditor check fails.
```

### Message to recruit your real person (send now so they're free around 8 PM)
> Hi! I'm in a 30-hour AI hackathon and built a tool that checks a small shop's sales records against card
> payments and the bank, finds the mistakes, and asks the owner before fixing anything. Could you spare
> 5–10 minutes tonight around 8–9 PM to try it on a fake shop's data and tell me honestly what you think?
> I'd love to quote you (or use a short screen clip) in my submission, only with your OK. Thank you!

## Stage 10. Curveball (9:00 PM MYT)
```
New request from our customer: "<paste it>". Plan it first, split it across parallel workers, write the test
first, show me the diffs, and finish with every test and Auditor check passing.
```

## Submit by ~1:30 AM at https://www.globalaihackathon.com/submissions
Required: name · email · track (Agentic Banking/Finance & Payments) · public repo · live link ·
**Mel session video ≤ 5 min** · demo video ≤ 5 min · description ≤ 300 chars · consent.
Recommended: Mel session export .zip · up to 3 attachments (e.g. AGENT_LOG.md, test output screenshot,
customer quote) · the four Mel ratings.
Put the customer reaction and the passing tests inside the demo video too; the Luma brief asks for both.

---

### Email for credits
**To:** hello@openmel.dev  **Subject:** Hackathon credits
```
Hi Mel team,

I'm registered for the Global AI Hackathon (Devcon 2026) and have signed up in Mel with this email address.
Could you please add my hackathon credits?

Track: Agentic Banking, Finance & Payments (Reconciliation Agent)

Thank you,
Shermaine Yap
```
