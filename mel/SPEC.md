# CloseCrew — product spec (input for Mel)

This is the idea and the acceptance criteria. **No code.** Mel plans, builds, tests and ships it.

## Customer and job
A small kuih & coffee shop (or any small business you know) that takes card payments through Stripe.
Every month the owner matches her sales spreadsheet against Stripe payouts and her bank statement.
It takes an evening and mistakes slip through. CloseCrew is a team of agents that does this job for her,
while she stays in charge.

## Hard rules (from the hackathon)
- Fake data only. Stripe **test mode** only; refuse any key that is not `sk_test_`.
- A human approves before anything changes the books or any money moves.
- Runs live on a public link. Checks its own work after every step. Hands off to a human when unsure.
- No tax or investment advice.

## Inputs (fake)
1. `ledger.csv`: the owner's books (id, date, description, reference/order no., amount, kind, method, customer)
2. Stripe balance transactions (charges, refunds, payouts, each with fee and payout id): CSV export or the
   Stripe test-mode API / Stripe MCP
3. `bank_statement.csv`: date, description, amount

A generator should create one realistic month with **planted mistakes** and a `ground_truth.json` listing them:
unbooked card fees, a sale paid but never entered, a customer charged twice, a refund not booked (one small, one
large), a digit-swap typo (RM 76 vs RM 67), a few sen of FX rounding, a card sale with no payment,
bookings missing an order number (needs fuzzy matching), a payout landing after month end.

## The crew (each is an agent with one job)
| Agent | Job | Must check its own work by |
|---|---|---|
| Ingest | load all sources, normalise | unique ids, valid types, sane signs; stop the run on bad input |
| Matcher | pair bookings with payments, payouts with bank lines | every pair has a reason and a confidence; ambiguous look-alikes go to a human, never a guess |
| Investigator | name the cause of each mismatch | cite the exact source rows; give the exact signed amount |
| Fixer | draft correcting entries | never edit the original ledger; write a reconciled copy plus a diff; only auto-apply what `policy.yaml` allows |
| Auditor | prove the result | independent recomputation; block the close if any check fails |
| Explainer | tell the owner in plain words | use only the Auditor's numbers |

## The owner's policy (`policy.yaml`, only a human edits it)
Auto-fix caps per cause, e.g. card fees up to RM 200 per payout, rounding up to RM 0.05, unbooked refunds up to
RM 30. Everything else (duplicates, missing sales, typos, unpaid sales, ambiguous matches) needs her approval.

## Acceptance criteria (write these as tests first)
1. On the generated month the crew finds **every** planted mistake and **no** others.
2. All money is integer cents.
3. Books-vs-Stripe difference **equals** the sum of the exceptions' amounts, to the cent, before and after fixes.
4. Stripe payouts minus bank lines equals the payouts still in transit.
5. Every auto-fix is allowed by the policy and under its cap.
6. No fix is posted twice; re-running gives the same result.
7. The original ledger file is byte-for-byte unchanged.
8. After the owner approves every open item, the difference is RM 0.00.
9. Red team: two different customers paying the same amount on the same day is **not** a duplicate; a fee above
   the agreed rate blocks auto-fix; a live Stripe key is refused; a broken CSV stops the run.
10. Any decision that breaks a check is rolled back automatically.

## Surfaces
- Web dashboard (public link): the difference before and after, the six agents' status, an approval queue with
  evidence and Approve/Reject, the reconciliation statement, the Auditor's checks, the diff, the agents' work log,
  a "generate a new random month" button.
- Optional: Telegram Approve/Reject buttons for the owner.
- `AGENT_LOG.md`: every agent action with its evidence and how it was verified.
