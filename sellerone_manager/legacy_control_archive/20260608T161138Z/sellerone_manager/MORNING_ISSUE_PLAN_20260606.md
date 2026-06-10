# SellerOne Morning Issue Plan - 2026-06-06

Observed: 2026-06-06 morning manager refresh

## Plain English Summary

The system stayed safe overnight, but it is not ready to trust automatic restocking.

The main problem is B. B is the order, money, refund, and token-cost truth layer. O depends on B before it can safely say a product is profitable to restock. H also depends on B for token-cost floor protection.

## Current Issues

### 1. B order truth is not clean

What this means:
- B has order data, and Sellerboard is not currently showing missing shipped orders.
- The remaining problem is proof quality: some marketplace cursor proof is stale, and B cannot yet prove every marketplace/order path is fresh enough.

Why it matters:
- If B order truth is not clean, sales velocity, ROI, refund rate, and restock urgency may be incomplete.

Safe Codex fix:
- Repair B manager proof and per-marketplace cursor proof.
- Retest with B MOT only.
- Do not run B live, edit data, correct tokens, write Sheets, or change DB facts.

Luke input likely needed:
- None for proof repair.
- Luke may later need to approve a live B proof run if the proof repair shows the only missing evidence requires a real B-owned refresh.

### 2. B fallback token costs are still not trusted

What this means:
- Some fallback stock tokens do not cleanly tie back to the receipt/batch cost proof.
- This affects SKU cost truth.

Why it matters:
- H repricing floors may use the wrong cost.
- O restock profit may look better or worse than reality.

Safe Codex fix:
- Continue proof-only audit and source-linking.
- Keep affected SKUs blocked from clean H/O trust until proof is clean.

Luke input likely needed:
- Yes, if we decide to correct historical token data.
- That must be preview-first. Luke should see the affected SKUs, old cost, proposed corrected cost, and impact before anything is applied.

### 3. O restock view is not ready for buying decisions

What this means:
- O has restock files, but two proof files are stale or not accepted by the manager.
- O also still lacks clean refund drag and inbound/FBA cost proof for expected profit.

Why it matters:
- O can help review candidates, but it should not be trusted as an automatic reorder authority yet.

Safe Codex fix:
- Repair O proof-file mapping.
- Repair O user-working readiness proof.
- Keep purchase orders, receiving, send-to-Amazon, H market scans, DB alignment, Sheets, and output deletion blocked.

Luke input likely needed:
- Yes for business judgement: which products you actually want to buy, supplier constraints, MOQs, cash limits, and whether to accept weak-profit rows manually.
- No for proof-file mapping repair.

### 4. F scanner is mostly okay, but one protected rescan issue remains

What this means:
- Seller Central/Dashboard Yes-No login worked.
- The scanner heartbeat recovered.
- Remaining F issue is old RESCAN rows with timeout dates.

Why it matters:
- This affects future product scanning, not today's core restocking truth.

Safe Codex fix:
- Classify warnings and keep scanner state visible.

Luke input likely needed:
- Yes, only if we want to approve preview-first rescan recovery for parked rows.
- No urgent action for today's restocking work.

### 5. E and H are warning layers, not today's main blockers

What this means:
- E can provide confidence and velocity signals, but it depends on B money/token truth.
- H is protecting pricing, but its floor source depends on B token cost proof.

Why it matters:
- Do not use E/H as final buying authority while B token-cost proof is unresolved.

Safe Codex fix:
- Keep warnings visible.
- Do not change prices or run H proof windows today unless separately approved.

## Recommended Fix Order

1. B order truth proof
   - Fix stale marketplace cursor proof and B management readiness proof.
   - Expected result: B moves from hard fail to warning/clear for order-truth freshness.

2. B fallback token proof
   - Continue source-linking and impact preview.
   - Expected result: affected SKUs are either trusted, warning-labelled, or presented to Luke for correction approval.

3. O restock proof readiness
   - Fix stale proof-file mapping and user-working readiness.
   - Expected result: O becomes usable as a review screen, but still blocks rows with weak profit inputs.

4. Manual restock support
   - Luke can still buy manually.
   - Use O/E/B evidence as advisory only.
   - Treat weak token-cost or missing inbound/refund proof as a caution label, not an automatic no.

5. F rescan decision later
   - Park until B/O restocking work is under control.

## Things Luke Can Usefully Input

- Which SKUs are urgent to restock today.
- Supplier MOQs and pack sizes.
- Cash/budget limits for this buying round.
- Whether a product can be bought manually despite weak proof.
- Whether to approve a preview-only token correction decision later.
- Whether to approve F rescan recovery later.

## Things Luke Should Not Need To Manage

- Marketplace cursor proof repair.
- B MOT retests.
- O proof-file mapping repair.
- O readiness proof repair.
- F warning classification.

## Safety Rules

Do not do these without explicit Luke approval:
- change token data
- change stock data
- write Google Sheets
- edit queues
- change prices
- publish
- align local DB facts
- delete outputs
- create purchase orders
- receive stock
- send stock to Amazon
- run live worker cycles without an approved proof window

## Next Manager Move

Claim or continue `B-ACTIVE-FAIL-GROUP`, then work the narrower B proof cards:
- `B-FUTURE-MARKETPLACE-ORDER`
- `B-MANAGEMENT-READY-FOR`
- `B-ORDER-TRUTH-COMPLETION`

After B proof improves, continue:
- `O-ACTIVE-RESTOCK-FILES`
- `O-USER-WORKING-READINESS`
