# Hometime Plan - 2026-06-05

Status check time: 2026-06-05 evening preflight

## Plain English Goal

Tonight is about getting the data ready for manual restocking tomorrow morning.

This does not mean automatic buying, purchase orders, price changes, queue edits, Sheet writes, or local DB alignment.

The goal is to make the trust chain clear:

```text
sales -> token COGS -> P&L/ROI -> velocity -> O restock view
```

If a row is not trustworthy, it must stay blocked or warning-labelled. Hometime must not hide weak proof just to make the restocking screen look ready.

## Current Evidence

- Sales and token allocation are fresh this afternoon:
  - `order_master.csv` has 11,562 rows and reaches 2026-06-05 14:52 UTC.
  - `orders_all.csv` has 11,865 rows and reaches 2026-06-05 14:52 UTC.
  - `token_ledger_live.csv` has 17,977 rows and was updated at 16:05 UK.
  - `token_allocations_live.csv` has 13,446 rows and was updated at 16:05 UK.
- Restocking outputs exist but are not buy-ready:
  - `restock_source_view.csv` has 608 rows.
  - `restock_recommendations_live.csv` has 608 rows.
  - all 608 recommendation rows are still `wait`.
  - all 608 source rows have `profit_input_confidence=missing_profit_inputs`.
  - 23 SKUs have weak fallback token cost trust.
- Sheet/token comparison evidence exists through the B manager lane:
  - direct Sheet batch token count proof is already proved.
  - the remaining issue is fallback tokens and stock-receipt/token sync proof, not a blanket Sheet batch-token mismatch.

## Tonight Priority Order

1. B stock-receipt/token sync proof
   - New MOT warning: `B-STOCK-RECEIPT-TOKEN`.
   - Purpose: prove whether the current stock receipt/token mismatch is only timing or a real stock-cost evidence issue.
   - Allowed: read-only proof, manager packet work, B MOT retest.
   - Blocked: stock correction, token correction, Sheet write, local DB alignment, live B run without approved proof.

2. B fallback-cost proof guard
   - Keep fallback-token cost risk visible.
   - Use existing Sheet comparison evidence and B071 reconciliation.
   - Do not correct historical tokens tonight unless Luke explicitly approves a protected correction packet.

3. O restock proof-file readiness
   - Work `O-ACTIVE-RESTOCK-FILES`.
   - Purpose: make sure tomorrow's restock screen has the expected proof files and does not silently rely on stale evidence.
   - Allowed: read-only proof mapping and manager-safe code/proof work.
   - Blocked: purchase actions, PO creation, receiving, send-to-Amazon, H market scans, H pause, DB alignment, output deletion.

4. O user-working readiness
   - Work `O-USER-WORKING-READINESS`.
   - Purpose: keep the manual restocking workspace usable while showing blocked rows honestly.
   - Success means Luke can see candidates and missing proof clearly, not that the system buys automatically.

5. E/B/O handoff proof
   - Confirm ROI and velocity are current enough after B changes.
   - If E/O outputs remain from the morning while B sales/token data changed in the afternoon, keep tomorrow status as `needs refresh before buying`.
   - Do not call E/O business-ready unless refreshed or explicitly proven from current data.

6. F Seller Central Dashboard Yes/No proof
   - The job is not general BBP login anymore.
   - BBP is a prerequisite only: F must stay BBP-authenticated enough to reach the scanner page.
   - The actual task is the further Amazon/Seller Central login that allows the Dashboard Yes/No value to be read.
   - Luke forwards the Seller Central login code to the email source for F to read.
   - F must focus on proving the Dashboard Yes/No value path: Seller Central login/code handling, then Yes/No extraction.
   - The active F heartbeat should keep checking `F-SELLER-CENTRAL-ELIGIBILITY`, scanner-owned browser evidence, Seller Central code evidence, and Dashboard Yes/No extraction evidence.
   - Allowed: safe login/proof classification, manager packet checks, F MOT retest, email-code evidence reading if the approved proof path allows it, and waiting for scanner-owned browser evidence.
   - Blocked: F061 manual run, scanner restart, queue edits, separate browser workaround, forced Chrome kill, Gmail fetch/download/delete, Sheet write, price change, output deletion, or controlled owner reload unless the approved packet proves restoration.
   - If Luke must log in through the scanner-owned browser, that is a real user action and should be surfaced once. Do not keep emailing repeat login noise.
   - Approval recorded after Hometime start: Luke approved the controlled FPM130 owner reload proof on 2026-06-05 only because the old owner was blocking the scanner-owned login path.
   - That owner reload proof is support work only. The real success target is Seller Central code login plus Dashboard Yes/No extraction.
   - This approval is narrow: the F manager may only perform bounded proof work that supports the scanner-owned Seller Central/Yes-No path and proves restoration afterward. It is not approval for F061 manual runs, queue edits, separate browser login, broad worker restarts, Sheet writes, price changes, DB alignment, output deletion, or scope widening.
   - No-progress rule: if the next controlled F proof window does not move `F-LOGIN-MODE` or `F-BBP-IFRAME-STALL` forward within two F manager checks, stop treating F as "still trying".
   - When that happens, classify the blocker plainly as one of: needs Luke login/code in scanner-owned browser, BBP/plugin/profile fault, owner reload proof failed, or supplier/page evidence blocked.
   - Then park F with that exact reason, keep it visible on the Manager Task Board, and move Hometime priority back to B/O restocking readiness.
   - Seller Central email-code route: if the scanner-owned browser reaches a Seller Central code prompt and the approved proof path allows code-forwarding, F should read the forwarded code email and use that path instead of waiting passively.
   - Adaptation rule: F must not repeat the same login attempt without new evidence. Every two checks it must either show progress toward Yes/No extraction, change tactic inside the approved boundary, or park itself with the exact blocker.
   - Email update rule for tonight: email Luke at `laprice90@gmail.com` when F proves Dashboard Yes/No extraction after Seller Central login, or after about two hours with a plain-English progress update if it is not complete. The email should say what changed, what F tried next, and whether Luke is needed.

7. H
   - H stays read-only tonight.
   - No H run, no publish, no scheduler ownership change, no price write.

## Pre-Approved Tonight Boundaries

Allowed:

- manager MOT refreshes
- Hometime pulses
- safe manager-approved code/proof work
- read-only Sheet/token comparison evidence
- read-only B/O/E proof checks
- updating manager task status from evidence

Blocked unless Luke explicitly approves:

- price changes
- queue edits
- Google Sheets writes
- local DB alignment
- historical token correction
- stock correction
- output deletion
- publishing
- purchase orders
- receiving
- send-to-Amazon
- live worker run without approved proof
- scheduler ownership change without restore proof
- business judgement

## Email Rule

Do not email Luke for known blockers.

Email only if a surprise protected decision appears after Hometime starts and Codex cannot safely continue another useful task.

Known parked/protected items stay quiet:

- B-B008-TOKEN-STATE-CONFLICT
- B-B009-RETURN-REUSE-APPLY
- F-BBP-IFRAME-STALL
- F-RESCAN-PRIORITY-02
- F-SELLER-CENTRAL-ELIGIBILITY

F is the exception to "quiet parked" only when new scanner-owned browser evidence appears, a real Luke login/code action is needed, the login path proves complete, or the two-hour F login progress update is due. The F manager should keep cracking on the proof path, adapt from evidence, and must not use a separate browser or force protected scanner actions.

## Morning Acceptance

Tomorrow morning is acceptable only if the manager can say:

- sales data is fresh enough for the morning review
- token allocation/COGS proof is either current or clearly blocked
- ROI and velocity are either refreshed after current sales data or labelled stale
- O restock rows are either safe manual candidates or clearly blocked with reasons
- weak fallback-token SKUs are not treated as clean buy-ready

If B stock/token proof is still warning-only, O must still block affected SKUs from clean reorder-ready status.

## Next Move

Hometime should continue with `B-STOCK-RECEIPT-TOKEN` first, keep F Seller Central Dashboard Yes/No proof active in parallel, then continue `O-ACTIVE-RESTOCK-FILES` and `O-USER-WORKING-READINESS`.

Latest F evidence: BBP is authenticated, Seller Central/Dashboard Yes-No proof has cleared, and Dashboard Yes/No is being read as `YES`. Treat the remaining F fail as the separate protected rescan-priority row, not a Seller Central login problem.
