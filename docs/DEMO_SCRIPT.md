# 3-minute demo video script

Record at 1280×720+. Hit **Reset demo** before recording. Keep Mel open in a second window.

| Time | Screen | Say (roughly) |
|---|---|---|
| 0:00–0:20 | Customer clip or voice note (see CUSTOMER_TEST.md) | *Let the customer say the pain in their words: "Every month I spend X hours matching…"* |
| 0:20–0:40 | Mermaid diagram in README | "So we hired a crew. Six agents with separation of duties like a real finance team: one matches, one investigates, one fixes, and an independent Auditor that can veto the fixer. Autonomy comes from one file the owner writes: policy.yaml." |
| 0:40–1:05 | Dashboard, click **Run the crew** | "One click: 130 Stripe transactions, 122 ledger rows, 6 bank lines. The books are off by RM 94. The crew traces 100% of that to 16 causes, and every one cites the exact rows it's based on." |
| 1:05–1:30 | Approval queue: open evidence on *Typo: digits swapped* and *Customer charged twice* | "It caught a digit-swap typo, a customer charged twice, two sales never entered, a refund nobody booked. Small things, card fees, 3 sen of FX rounding, a RM 12.50 refund, it fixed itself because they're under the owner's caps. Everything else waits for her." |
| 1:30–1:50 | Phone: Telegram approve tap → dashboard updates | "She approves from her phone. Every approval re-runs the whole crew and re-audits; if any check fails it rolls back automatically." |
| 1:50–2:10 | **Ledger diff** tab, then **Auditor checks** 9/9 | "Nothing edits her spreadsheet. Every change is a diff. The Auditor proves the difference equals the sum of open items to the cent, and that every auto-fix was within policy." Approve the rest → **RM 0.00, CLOSED**. |
| 2:10–2:30 | Mel orchestrator with parallel panes | "Built and hardened in Mel: a lead agent split the work across parallel workers, Stripe connected through MCP, every edit reviewed as a diff with approvals on." |
| 2:30–2:45 | Curveball feature running | "Sunday's curveball: <request>. Shipped with a test in N minutes." |
| 2:45–3:00 | Terminal: `pytest -q` → 30 passed; customer reaction | "30 tests, including a red team and a property test over 300 random months with zero failures. Zero money moved. Every ringgit explained." |

Tips: zoom the browser to 110%; hide bookmarks; record audio separately if your room is noisy.
