# Using Mel on CloseCrew

"Use of Mel" is 20% of the score. Judges look for: **agents working in parallel, reviewing edits as diffs,
approvals, and connecting tools through MCP.** Do every section below inside Mel, keep the panes visible
while you record, and screenshot each one for the submission.

> Setup: download Mel from openmel.dev, sign in with the email you registered with, open this repo folder
> in Mel. Point Mel at `mel/PROJECT_BRIEF.md` first so its project memory knows the rules.

---

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
