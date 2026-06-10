# Plan

## Goal
- Final outcome:
  - connect supplier price-list costs and actual purchase costs into one trusted buy-cost decision layer
  - let the stock decider know the expected next purchase cost
  - flag discount assumptions for user confirmation
  - show a max purchase price so the user knows when a product no longer makes enough money

## Non-goals
- Do not do:
  - no Google Sheets writes
  - no direct patching of `out/product_db_preview.csv`
  - no local DB alignment changes without approval
  - no new live F061 handoff without F owner boundary proof
  - no repricer strategy change in H
  - no O real-SKU purchase-order activation until the cost bridge is proven

## Current state
- What exists already:
  - H repricer is live and producing current pricing/floor/strategy artifacts.
  - F price-list manager can ingest real supplier price lists from email, API, and files.
  - O restock scaffold exists and has source view, recommendation, review queue, decision, PO, ordered-stock, receiving, send-to-Amazon, and UI scripts.
  - Product DB target authority is SQL, but many runtime paths still read legacy CSV mirror data.
- Known pain points:
  - O restock currently reads `out/product_db_preview.csv` for supplier cost.
  - `out/product_db_preview.csv` has 608 rows, 0 supplier catalog prices, and only 132 last purchase prices.
  - Current O source view has 476 rows blocked by missing cost.
  - F price-list data is not yet a first-class O cost source.
  - Actual paid purchase price is not stored as a reusable discount rule for future price-list changes.
- Known alerts or reliability concerns:
  - Current health has 2 FAIL and 5 WARN in `out/system_health_checklist.csv`.
  - H has a current `h_strategy_outcome_daily_count_integrity` FAIL.
  - TD Synnex live active F run currently appears to be the old shifted-column run `fpm_td_synnex_20260519T090704Z`, even though the plan says it was retired and replaced by `fpm_td_synnex_20260519T095000Z`.

## Target state
- What changes:
  - add an explicit buy-cost truth layer before O recommendations
  - store current price-list cost separately from actual paid cost
  - calculate discount ratio from actual paid versus list cost at purchase time
  - estimate next expected cost from the latest price list and stored discount ratio
  - mark discount-estimated costs as user-confirm-needed
  - calculate max purchase price from market price, known costs, and target ROI
- What stays the same:
  - F remains owner of supplier price-list intake and scanner flow
  - O remains owner of restock recommendation and purchase workflow state
  - H remains owner of repricing runtime
  - Product DB authority rules remain unchanged

## Systems touched
- Flow(s):
  - F as supplier price-list source
  - O as stock/reorder decision owner
  - Product DB as product/supplier identity context
  - H and E as market/economic context only
- Shared dependencies:
  - `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
  - `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `out/systems/O/live/restock_source_view.csv`
  - `out/systems/O/live/restock_recommendations_live.csv`
  - `out/product_db_preview.csv` until O is moved to SQL read authority
  - `out/sql/sellerone_dev.sqlite3` for SQL Product DB proof path
  - `out/listing_offer_snapshot_latest.csv`
  - `out/sku_performance_summary.csv`
- Runtime or scheduler ownership concerns:
  - F is active now and must not be overlapped.
  - Any F active-run replacement must wait for a controlled drain boundary.
  - A scripts must not be run ad hoc as proof.
  - H proof, if later needed, must use controlled H proof rules.

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| F manager batch rows | F price-list manager | input | `out/systems/F/price_list_manager/test_mode/batch_rows.csv` | Contains clean price-list row cost, supplier SKU, barcode, and batch id. |
| F live active run | FPM130/F061 | live input/output | `out/systems/F/inbox/supplier_price_list_active_run.csv` | Currently appears to conflict with TD Synnex clean-run proof. |
| O restock source view | `O001_build_restock_source_view.py` | output | `out/systems/O/live/restock_source_view.csv` | Current O cost source is Product DB catalog/last purchase only. |
| O recommendations | `O002_build_restock_recommendations.py` | output | `out/systems/O/live/restock_recommendations_live.csv` | Uses `current_supplier_buy_cost_gbp` for ROI. |
| O decision events | `O010_apply_restock_decisions.py` | input/log | `out/systems/O/inbox/restock_decision_events.csv` | Requires confirmed cost before approval. |
| O purchase order draft | `O100_build_purchase_orders.py` | output | `out/systems/O/live/purchase_orders_live.csv` | Uses confirmed cost from decision log. |
| Proposed cost bridge | new O-owned output | output | `out/systems/O/live/supplier_buy_cost_truth.csv` | New file proposed in this plan. |
| Proposed user confirmation queue | new O-owned output | output | `out/systems/O/live/supplier_cost_confirmation_queue.csv` | Rows where discount assumption or price conflict needs user check. |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| F manager batch rows | 1 supplier refresh cycle | 3 supplier refresh cycles | required before O cost bridge consumes price-list rows | Must reject shifted-column rows. |
| F live active run | current F run boundary | stale after active run mismatch | TD Synnex active-run clean-shape check | Phase 1 blocker. |
| O supplier buy-cost truth | 24h | 48h | new required O check | Must reconcile source rows, confidence, and review-required counts. |
| O confirmation queue | 24h | 72h | new required O check | Must list all discount assumptions and bad price conflicts. |
| O restock source view | 24h | 48h | existing plus new cost-source check | Should show cost source and confidence explicitly. |

## Integration points
- APIs:
  - none added in the first O cost bridge phase
  - use existing F manager API/email/file intake outputs
- Sheets:
  - none
- Local DB:
  - read-only SQL Product DB proof may be used after approval
  - no SQL Product DB write without approval
- CSV or file handoffs:
  - F manager batch rows feed O cost bridge
  - O cost bridge feeds O source view
  - O recommendations feed O decision event and PO flow

## Risks and mitigations
- Risk:
  - Bad F price-list rows feed stock decisions.
  - Mitigation:
  - Phase 1 blocks the cost bridge until active F source-shape checks pass.
- Risk:
  - The system treats an assumed discount as guaranteed.
  - Mitigation:
  - Discount-derived expected costs must set `user_price_check_required=1`.
- Risk:
  - The max purchase price is calculated from incomplete economics.
  - Mitigation:
  - First output must separate `break_even_max`, `target_roi_max`, and `blocked_missing_fee_or_shipping`.
- Risk:
  - Product DB CSV mirror is patched to make O look better.
  - Mitigation:
  - Do not patch `out/product_db_preview.csv`; use an O-owned cost truth output or approved SQL read.

## Proof rules
- What counts as code fix applied:
  - only after approved implementation files are patched and the plan status records the exact file list
- What counts as isolated verification passed:
  - targeted F/O tests pass
  - cost bridge test fixtures cover same-as-list, discounted, price-list increase with discount assumption, missing cost, bad shifted row, and over-max-cost cases
- What counts as live loop verification confirmed:
  - F active source shape is clean or quarantined
  - O cost truth output builds without bad shifted rows
  - O recommendations use the expected cost with confidence and review-required fields
  - rows above max purchase price are blocked or marked wait

## Batch list
- Batch 001:
  - source truth stabilization
  - confirm or fix the TD Synnex active-run contradiction at a safe F boundary
  - add a read-only source-shape check for price-list rows before any O consumption
- Batch 002:
  - design and implement O supplier buy-cost truth output
  - include discount ratio, expected next cost, confidence, and user-confirm-required fields
- Batch 003:
  - add max purchase price calculation and blocker reasons
  - feed the new cost truth into O source view and recommendations
- Batch 004:
  - build a small user review queue for discount assumptions and cost conflicts
  - no automatic Product DB or Sheet writes
- Batch 005:
  - approved small real-SKU proof only
  - verify recommendation movement and decision safety before any wider rollout

## Archive rule
- When this plan can move to archive:
  - F source-shape guard is proven
  - O cost truth output is built and tested
  - discount assumption examples pass
  - max purchase price fields are present and tested
  - user review queue exists for unconfirmed discount assumptions
  - no Google Sheets or Product DB authority boundary was violated
