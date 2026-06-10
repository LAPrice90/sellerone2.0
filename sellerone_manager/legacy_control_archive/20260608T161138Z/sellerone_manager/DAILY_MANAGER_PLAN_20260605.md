# Daily Manager Plan - 2026-06-05

Status check time: 2026-06-05 11:36 UK

## Main Goal

Get SellerOne closer to safe reordering.

This does not mean automatic purchase orders today. It means getting the restock workspace trustworthy enough that Luke can use it for manual buying decisions without the system hiding weak proof.

## Current Position

- A is calm.
- B has a new high-priority token-cost problem: fallback stock tokens can carry old costs into current available stock.
- E is warning-only and still depends on B money confidence.
- H is warning-only and controlled, but H floor trust now depends on the B token-cost repair.
- F is blocked by a protected rescan decision.
- O is the practical reordering lane today, but affected SKUs must stay blocked from clean reorder-ready status until B token-cost proof clears.

## Today Priority Order

1. O-ACTIVE-RESTOCK-FILES
   - Fix the O proof-file mapping gap.
   - Do not run O worker actions.
   - Do not run H pause or market scans.
   - Do not create purchase actions.

2. O-USER-WORKING-READINESS
   - Make the restock workspace usable and honest.
   - Keep weak rows blocked instead of pretending they are ready.
   - Do not send anything to Amazon, create receiving, or approve purchase decisions.

3. B-FALLBACK-COST-AUDIT
   - Prove the full scale of fallback-token cost risk.
   - Start with `A2-T2AC-TW3L` and include the wider scan.
   - Do not correct token data from the audit job.

4. B-FALLBACK-COST-SOURCE
   - Stop future fallback tokens from copying unproved latest SKU costs.
   - This is safe code/test work only.
   - Do not run B live or change existing tokens.

5. H-TOKEN-FLOOR-SOURCE-GUARD
   - Make H manager proof show when a floor is calculated from unproved fallback token cost.
   - Do not change price logic or run H.

6. O-TOKEN-COST-TRUST-GATE
   - Keep affected SKUs out of clean reorder-ready status.
   - Do not make purchase decisions.

7. B-STOCK-RECEIPT-TOKEN
   - Continue the receipt/token proof lane.
   - This supports profit and restock confidence.
   - Do not correct stock, tokens, DB data, or Sheets from this packet.

8. F-RESCAN-PRIORITY-02
   - Leave parked unless Luke approves preview-first rescan recovery.
   - Do not rewrite scanner queue/output rows from MOT evidence.

## Reordering Readiness Target

Today is successful if O can show:

- which products are candidates
- what proof is missing
- which rows are blocked
- whether profit inputs are weak because of refund, inbound cost, or B money confidence
- what Luke can decide manually without the system pretending it is automated

## Do Not Do Today

- no automatic purchase orders
- no send-to-Amazon actions
- no receiving actions
- no price changes
- no queue edits
- no Google Sheets writes
- no local DB alignment
- no output deletion
- no live worker cycles without approved proof
- no H pause or market proof unless separately approved

## Next Move

Continue with B fallback-token cost audit first, because O reordering and H repricing cannot be trusted for affected SKUs until the B token-cost source is clean or clearly parked.
