# Build CloseCrew A to Z in Mel

The rules say **every project must be built from A to Z with Mel**. So Mel builds it from an **empty folder**,
using only `SPEC.md` as the brief. Don't paste code into Mel and don't copy files from the old prototype.

All times are Malaysia time (MYT). Deadline: **Monday 3:00 AM**. Curveball: **Sunday 9:00 PM**.

## 0. Setup (15 min)
1. Install Mel from https://www.openmel.dev/download and sign up **with the same email you registered with**.
2. Email hello@openmel.dev **from that address**, subject `Hackathon credits` (draft at the bottom).
3. Make a new empty GitHub repo, e.g. `closecrew`. Clone it into an empty folder and open that folder in Mel.
4. Copy **only** `SPEC.md` into the empty folder.
5. In Mel's settings, turn on approvals for: shell commands outside the folder, `git push`, and any edit to
   `policy.yaml`. Leave diff review on for every edit.
6. Start screen recording (OBS or Win+G) and keep it running in the background for each stage. You'll cut
   clips from it later.

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

## Stage 7. Stripe via MCP (optional, ~30 min)
Add Stripe's MCP server in Mel with a **test** key (`sk_test_…`), then:
```
Using the Stripe MCP tools in TEST mode only, create 20 test payments that mirror part of the generated month,
then add an ingest option that reads balance transactions from Stripe test mode. Refuse any non-test key.
```

## Stage 8. Ship, ~45 min
```
Add a README (problem, crew diagram, how to run, proof), a Dockerfile, and a render.yaml for a free Render deploy.
Run all tests one final time, commit, and push. Ask me before pushing.
```
Then deploy on Render (New → Blueprint → your repo) to get the public link.

## Stage 9. The real-person test and the agents on duty
- Have a real person use the live link (see `CUSTOMER_TEST.md` in the old repo), and get their consent.
- Record Mel running the close as the operator: the lead runs the crew, workers re-check the evidence, and Mel's
  approval prompt pauses before each approve (the prompt is in `MEL_PLAYBOOK.md` §0).

## Stage 10. Curveball (9:00 PM MYT)
```
New request from our customer: "<paste it>". Plan it first, split it across parallel workers, write the test
first, show me the diffs, and finish with every test and Auditor check passing.
```

## Submit by ~1:30 AM at https://www.globalaihackathon.com/submissions
Live link · repo · video ≤ 3 min · agent work log · proof the tests passed · customer reaction · Mel feedback form.

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
