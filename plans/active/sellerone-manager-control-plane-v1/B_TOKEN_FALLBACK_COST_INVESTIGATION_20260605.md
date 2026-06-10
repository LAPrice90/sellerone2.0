# B Token Fallback Cost Investigation - 2026-06-05

## Plain English Finding

B has created local fallback stock tokens that can carry the wrong cost.

H is not making up the 4.51 cost. H is reading the local live token ledger and using the first available token for the SKU. For `A2-T2AC-TW3L`, the first available local token is a `stock_adjustment_fallback` token at 4.51, even though later real stock receipt tokens exist at 4.44.

This is a root-source problem in B token truth. If it is not fixed at B, it can affect:

- H minimum price floors
- B P&L cost of goods
- E ROI confidence
- O restocking confidence

## Specific SKU Evidence

Target:

- SKU: `A2-T2AC-TW3L`
- ASIN: `B006PFN3BW`

Local live token ledger evidence:

- Total local tokens for SKU: 2383
- Allocated tokens: 1769
- Returned complete tokens: 4
- Available tokens: 610
- Available 4.44 `stock_receipt` tokens: 267
- Available 4.51 `stock_adjustment_fallback` tokens: 343

H floor proof:

- H latest floor proof uses COGS 4.510
- H latest hard floor is 10.75
- H source is `token_ledger_live_next_available`

Why H picked 4.51:

- The first available H-sorted token is `ADJ-A2-T2AC-TW3L-FBA15LKBY55D-0138`
- Its source is `stock_adjustment_fallback`
- Its cost is 4.51
- Its received date is 2026-03-18

Receipt truth visible in the local ledger:

- 2026-01-05 stock receipt: 120 tokens at 4.51
- 2026-02-09 stock receipt: 360 tokens at 4.44
- 2026-03-26 stock receipt: 360 tokens at 4.44
- 2026-04-28 stock receipt: 120 tokens at 4.44

Fallback token batches visible in the local ledger:

- 2026-02-10 fallback: 120 tokens at 4.51
- 2026-03-04 fallback: 120 tokens at 4.51
- 2026-03-18 fallback: 240 tokens at 4.51
- 2026-04-02 fallback: 120 tokens at 4.51
- 2026-04-08 fallback: 120 tokens at 4.51

## Code Root Cause

The B script `B009_apply_stock_adjustments_to_tokens.py` has a helper called `_latest_cost_basis`.

When a stock adjustment or receipt event cannot be matched to a returned-pending token, B creates `stock_adjustment_fallback` tokens.

The current fallback token creator gets the fallback cost from the latest existing local ledger cost for that SKU. It does not prove that the fallback cost matches the actual receipt batch or supplier-cost truth for the stock event.

That means an old cost can be copied forward into new fallback stock.

## Wider Risk Scan

Current available `stock_adjustment_fallback` tokens:

- Total available fallback tokens: 2029
- Allocated fallback tokens already used in sales: 912
- SKUs with available fallback risk pattern found: 10

Highest visible risk counts:

- `6V-EEC1-2S9Z`: 1248 available fallback tokens at 2.25, while later receipt cost evidence includes 2.22
- `A2-T2AC-TW3L`: 343 available fallback tokens at 4.51, while later receipt cost evidence includes 4.44
- `EV-CHU5-XU3G`: 148 available fallback tokens at 2.37, with first available local token evidence needing closer audit
- `C6-XGZB-J6QA`: 78 available fallback tokens at 2.75
- `LV-425G-BY4X`: 59 available fallback tokens at 16.38

## Sheet Comparison Result

Read-only comparison against Google Sheet:

- Spreadsheet: `Amazon Supplier Process`
- Tab: `Tokens`
- Rows read: 90 token-batch rows
- Sheet total quantity: 5348
- Local live token ledger rows: 17977

Direct Sheet batch result:

- Direct Sheet batch tokens with wrong cost: 0
- Missing local stock-receipt tokens versus Sheet quantity: 1
- Extra local stock-receipt tokens versus Sheet quantity: 3

Small direct count mismatches:

- Sheet row 74, `5Q-LUQ1-L14K`, batch `SR-20260413-009`: Sheet says 11 tokens at 29.96, local stock-receipt tokens found 10.
- Sheet row 77, `MY-KL21-NMV5`, batch `SR-20260318-014`: Sheet says 4 tokens at 20.00, local stock-receipt tokens found 7.

Fallback-token cost result:

- Total fallback tokens checked: 3120
- Fallback tokens whose cost differs from the latest prior Sheet cost: 1473
- Of those, currently available: 1096
- Of those, already allocated: 377
- Fallback tokens with no Sheet cost for the SKU: 198
- Fallback tokens with no prior Sheet cost for that fallback date: 5

Main affected SKUs:

- `6V-EEC1-2S9Z`: 753 fallback tokens at 2.25 where latest prior Sheet cost is 2.22. All 753 are currently available.
- `A2-T2AC-TW3L`: 720 fallback tokens at 4.51 where latest prior Sheet cost is 4.44. 343 are currently available and 377 are already allocated.

H next-available floor risk:

- `A2-T2AC-TW3L` is the only current Sheet-backed H next-available wrong-cost row found in this comparison.
- H first available token is `stock_adjustment_fallback` at 4.51.
- Latest prior Sheet cost is 4.44 from Sheet row 33.

Generated read-only outputs:

- `out/systems/M/b_token_sheet_comparison/summary.md`
- `out/systems/M/b_token_sheet_comparison/summary.json`
- `out/systems/M/b_token_sheet_comparison/sheet_batch_token_comparison.csv`
- `out/systems/M/b_token_sheet_comparison/fallback_cost_mismatch_tokens.csv`
- `out/systems/M/b_token_sheet_comparison/fallback_cost_mismatch_by_sku.csv`
- `out/systems/M/b_token_sheet_comparison/h_next_available_cost_mismatch.csv`

## What Must Not Happen

Do not fix this by changing H output downstream.

Do not hand-edit the live token ledger to make the current SKU look better.

Do not let O treat affected rows as clean reorder-ready while the token-cost source is unproved.

## Manager Jobs Created

- `B-FALLBACK-COST-AUDIT`
- `B-FALLBACK-COST-SOURCE`
- `H-TOKEN-FLOOR-SOURCE-GUARD`
- `O-TOKEN-COST-TRUST-GATE`
- `B-FALLBACK-DATA-CORRECTION`

## Success Condition

The system is not clean until:

- B can list every fallback token cost risk.
- B stops creating future fallback tokens from unproved latest-cost copying.
- Existing affected fallback tokens are either corrected through an approved protected repair or parked as untrusted.
- H marks floors based on unproved fallback tokens as not clean.
- O blocks affected SKUs from reorder-ready status until B token-cost proof clears.
