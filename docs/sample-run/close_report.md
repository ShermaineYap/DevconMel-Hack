# Month-end close: 2026-10

**Status: CLOSED**

October is closed. The card processor shows RM 16,909.67 of net card income; the books started at RM 17,003.67, a gap of -RM 94.00. Every ringgit of that gap is traced to 16 specific causes, and 8 small ones were fixed inside your policy. The remaining -RM 51.90 is from item(s) you chose not to post, kept on record as an acknowledged difference.

## Reconciliation statement

| | Amount |
|---|---:|
| Net card income per processor | RM 16,909.67 |
| Card income per books (before) | RM 17,003.67 |
| **Difference before** | **-RM 94.00** |
| Card processing fees not booked (6) | -RM 661.83 |
| Sale paid but never entered (2) | RM 445.70 |
| Customer charged twice (2) | RM 376.70 |
| Refund not in the books (2) | -RM 193.70 |
| Typo: digits swapped (1) | -RM 9.00 |
| FX / rounding difference (1) | RM 0.03 |
| Card sale with no payment (1) | -RM 51.90 |
| **Explained** | **-RM 94.00** |
| Fixes posted | -RM 42.10 |
| **Difference after fixes** | **-RM 51.90** |

## What the crew fixed

- `EXC-9C1AF3BD` Typo: digits swapped · -RM 9.00 · policy requires a human for 'transposition'; approved by Owner
- `EXC-ED63266E` FX / rounding difference · RM 0.03 · 'rounding' within policy cap of 0.05
- `EXC-D280BC13` Refund not in the books · -RM 181.20 · 181.20 is above the auto-fix cap of 30.00; approved by Owner
- `EXC-7BE255E6` Sale paid but never entered · RM 243.90 · policy requires a human for 'missing_ledger_entry'; approved by Owner
- `EXC-2A8AF88D` Customer charged twice · RM 249.80 · policy requires a human for 'duplicate_charge'; approved by Owner
- `EXC-B379C568` Customer charged twice · RM 126.90 · policy requires a human for 'duplicate_charge'; approved by Owner
- `EXC-CF312264` Refund not in the books · -RM 12.50 · 'refund_not_booked' within policy cap of 30.00
- `EXC-84A88D8E` Sale paid but never entered · RM 201.80 · policy requires a human for 'missing_ledger_entry'; approved by Owner
- `EXC-0BC5D70B` Card processing fees not booked · -RM 48.16 · 'processor_fee' within policy cap of 200.00
- `EXC-A11BC9C6` Card processing fees not booked · -RM 121.86 · 'processor_fee' within policy cap of 200.00
- `EXC-95AE0C1D` Card processing fees not booked · -RM 100.52 · 'processor_fee' within policy cap of 200.00
- `EXC-053EF53B` Card processing fees not booked · -RM 196.59 · 'processor_fee' within policy cap of 200.00
- `EXC-D888DDB1` Card processing fees not booked · -RM 106.19 · 'processor_fee' within policy cap of 200.00
- `EXC-876F22A5` Card processing fees not booked · -RM 88.51 · 'processor_fee' within policy cap of 200.00

## Needs your decision

- nothing

## For information

- The books show a card sale of RM 51.90 (ORD-19001) on 2026-10-16, but no card payment arrived. The payment may have failed.
- Payout po_35755ade7c55dc of RM 2,716.58 left stripe on 2026-10-31 and lands on 2026-11-02, after month end. Timing only; nothing is missing.

## Auditor checks

- PASS · conservation: 258 source rows: 0 unaccounted, 0 counted twice
- PASS · every ringgit explained (before fixes): difference -RM 94.00 vs sum of exception impacts -RM 94.00
- PASS · every ringgit explained (after fixes): remaining difference -RM 51.90 vs open exceptions -RM 51.90
- PASS · payouts reconcile to bank: payouts RM 15,652.23 - bank RM 12,935.65 = RM 2,716.58, explained by bank exceptions RM 2,716.58
- PASS · payouts equal net of settled transactions: all payouts tie out
- PASS · auto-fixes within owner policy: 8 auto-fixes checked against policy 2a5024b9c2
- PASS · no double posting: 14 fix entries, unique, one per approved/auto exception
- PASS · integer cents only: 418 amounts checked
- PASS · original ledger untouched: sha256 46bccfb603… before and after

_Prepared by CloseCrew. Test data and sandbox payments only. Not tax or investment advice._
