> Superseded by `BUILD_FROM_SCRATCH.md` for the hackathon build. Commands below refer to the old prototype.

# Using Mel on CloseCrew

"Use of Mel" is 20% of the score. Judges look for: **agents working in parallel, reviewing edits as diffs,
approvals, and connecting tools through MCP.** Do every section below inside Mel, keep the panes visible
while you record, and screenshot each one for the submission.

> Setup: download Mel from openmel.dev, sign in with the email you registered with, open this repo folder
> in Mel. Point Mel at `mel/PROJECT_BRIEF.md` first so its project memory knows the rules.

---

## 0. The crew on duty, inside Mel (show this in the demo)
The brief says *"build a team of AI agents **in Mel** that does a real job"*. So the month-end close itself is
run by Mel agents: the Python package is their toolbox, Mel's lead agent is the manager, Mel's parallel panes are
the crew, and **Mel's approval prompt is the human gate** before any ledger change. Use `/orchestrate-agent`:

```
You are the month-end close team for a small kuih & coffee shop (fake data, Stripe test mode).
Read mel/PROJECT_BRIEF.md. Never edit policy.yaml or data/ledger.csv.

Lead: run `python -m closecrew run`, then split the review across three workers in parallel:

1. Investigator worker: read state/latest.json. For the 3 largest open exceptions, open the cited rows in
   data/*.csv yourself and confirm the cause and amount are right. Report any disagreement.
2. Auditor worker: independently of the others, recompute (sum of Stripe net) - (sum of card rows in
   data/ledger.csv) with a short script and confirm it equals the "difference before" in state/latest.json.
   Then run `python -m pytest -q`. Report pass/fail with numbers.
3. Explainer worker: read state/close_report.md and write a 5-line WhatsApp-style message to the owner
   explaining what happened this month in plain words, using only numbers from the report.

Then, as lead: show me each open item one by one (cause, amount, evidence). For each one I approve, run
`python -m closecrew approve <EXC-ID> --by <my name>`; for each I reject, run
`python -m closecrew reject <EXC-ID> --by <my name> --note "<my reason>"`.
Never run approve or reject without my explicit yes. After each decision, check that the Auditor still
shows 9/9; if not, stop and tell me. Finish by running `python -m closecrew run` and summarising.
```
With approvals on (§1), Mel pauses before each `approve` command, so a human signs off every change.
That clip covers *agents in Mel*, *parallel*, *approvals*, *checks its own work* and *knows its limits* at once.

## 1. Approvals (do this first)
In Mel's settings, set approvals so that **every shell command that writes outside the repo, every `git push`,
and every edit to `policy.yaml` asks you first**. Edits inside `closecrew/`, `tests/`, `docs/` can show as diffs
for review. This mirrors the product itself: autonomy inside a policy, a human for everything else.

## 2. Connect Stripe through MCP
Add Stripe's MCP server in Mel's MCP settings, with a **test-mode** key only:

```json
{
  "mcpServers": {
    "stripe": {
      "command": "npx",
      "args": ["-y", "@stripe/mcp", "--tools=all"],
      "env": { "STRIPE_SECRET_KEY": "sk_test_..." }
    }
  }
}
```
(Stripe also offers a hosted MCP endpoint; check Stripe's docs for the current package name / URL.)

Prompt to try in Mel once connected:
```
Using the Stripe MCP tools in TEST mode only, list the last 20 balance transactions and compare them with
data/stripe_balance_transactions.csv. Report any transaction types or fields our stripe_api adapter in
closecrew/ingest.py does not handle. Do not create or refund anything.
```

## 3. Parallel orchestration (the headline Mel moment)
Use `/orchestrate-agent` and paste:

```
Goal: harden CloseCrew for a real customer's month-end close. Read mel/PROJECT_BRIEF.md first.
Split into these independent workers, each owning only the files listed, running in parallel:

1. Matcher worker (closecrew/matcher.py, tests/test_red_team.py): add a red-team test where a customer
   pays the same order in two partial payments that sum to the booked amount. Make the matcher handle it
   or route it to a human. Must keep every existing test green.
2. Explainer worker (closecrew/explainer.py): add a Bahasa Malaysia version of the close report
   (report_markdown(..., lang="ms")). Numbers must still come only from the Auditor.
3. Dashboard worker (app/static/index.html): add a "language" toggle that requests the BM report.
4. Docs worker (docs/): update README "Proof it works" with the new test.

Shared memory: policy.yaml is owner-controlled — no worker may edit it.
Integrate: run `python -m pytest -q` and `python -m closecrew run`; all 9 Auditor checks must pass.
Show me every edit as a diff before applying.
```
Record the four panes working at once. That clip is your "Use of Mel" proof.

## 4. Review as diffs
Before committing, ask Mel:
```
Review the uncommitted changes as diffs. For each file, tell me if anything could let an agent move money,
edit the original ledger, or bypass policy.yaml. Then run the tests.
```

## 5. Red team (Mel's beta red-team feature, or this prompt)
```
Act as an attacker against CloseCrew's Matcher and Investigator. Write 5 adversarial CSV fixtures
(look-alike customers, same-day same-amount orders, a refund larger than its charge, a payout split across
two bank lines, unicode names) as pytest cases in tests/test_red_team.py. Run them. For each failure,
propose a fix as a diff but do not apply it until I approve.
```

## 6. The Sunday curveball (8:00 AM EST = 9:00 PM MYT)
Paste the customer's new request into Mel with:
```
New customer request: "<paste it>".
Read docs/CURVEBALL_PLAYBOOK.md for the likely path. Plan first, then split the work across parallel
workers. Constraints: no edits to policy.yaml without asking me; every change ships with a test;
the run must end with all 9 Auditor checks passing and the agent log updated. Show diffs before applying.
```

## What to capture for the submission
- Screenshot / clip of the orchestrator with parallel panes
- A diff review screen with you approving
- The MCP Stripe tool call
- Mel's test run output (pass)
- Fill in Mel's feedback form (required, 5 minutes)
