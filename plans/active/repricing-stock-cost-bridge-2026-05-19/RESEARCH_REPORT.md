# Research Report

Created UTC: 2026-05-19

## 1. Short Answer
The repricer and stock-decider pieces exist, but the buy-cost bridge is not built yet.

The repo currently has:
- H repricing live and active, but still stability-gated.
- F price-list manager live and actively scanning supplier price-list rows.
- O restock/stock decision scaffolding present, but not live-ready and not using the new F price-list manager as its cost source.
- Product DB SQL authority work mostly present, but O restock still reads the legacy `out/product_db_preview.csv` path for supplier cost.

The missing piece is a clear cost-truth layer between F price lists, actual purchase records, Product DB, and O restock recommendations.

## 2. Current Repricing Position
Evidence checked:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- active H plans under `plans/active/`
- current runtime artifacts under `out/`

Current position:
- H is the live repricing runtime.
- H uses A-prepared daily intel and floor data.
- H current runtime source files include `out/phase1_runtime_floor_snapshot_latest.csv`, `out/h_strategy_outcome_daily.csv`, `out/h_strategy_outcome_log.csv`, and `out/h_ceiling_events.csv`.
- H is not marked replacement-complete. The roadmap marks it `Needs Stabilising`.

Current H artifact counts seen during this research:
- `out/phase1_runtime_floor_snapshot_latest.csv`: 89 rows, modified 2026-05-19 12:23:07 local.
- `out/h_strategy_outcome_daily.csv`: 306 rows, modified 2026-05-19 12:31:14 local.
- `out/h_strategy_outcome_log.csv`: 111493 rows, modified 2026-05-19 12:30:53 local.
- `out/h_ceiling_events.csv`: 79164 rows, modified 2026-05-19 12:31:25 local.

Current health position from existing `out/system_health_checklist.csv`:
- ok: 191
- warn: 5
- fail: 2

Relevant H alert:
- `h_strategy_outcome_daily_count_integrity` is currently `fail`.
- H strategy sample-size warnings are still present.

Meaning:
- Repricing is running and producing current data.
- Strategy/output quality is still not fully signed off.
- Do not use H strategy outputs as a fully mature buying decision engine yet.

## 3. Current Price-List Position
Evidence checked:
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/td-synnex-email-price-files-2026-05-19/CODING_PLAN.md`
- `plans/active/tropicana-email-price-files-2026-05-19/CODING_PLAN.md`
- `plans/active/clf-api-price-files-2026-05-19/CODING_PLAN.md`
- F price-list manager artifacts under `out/systems/F/price_list_manager/`

The price-list manager now has real supplier intake paths:
- TD Synnex email zip intake: real file downloaded and converted.
- CLF API intake: live API probe succeeded and converter-valid rows exist.
- Tropicana email attachment intake: download works, but current attachment is stock-only and missing cost.

Current price-list manager batch-row counts:
- TD Synnex: 103543 rows, 103457 scan-now rows, 86 held.
- CLF: 16456 rows, 16172 scan-now rows, 284 held.
- Tropicana Wholesale: 6462 rows, 0 scan-now rows, 6462 held because cost is missing.
- Stax: 54402 rows in manager batch rows.
- Entertainment Trading: 42717 rows in manager batch rows.
- Heo: 15854 rows in manager batch rows.
- Shure Cosmetics: 9656 rows in manager batch rows.
- Bliss Distribution: 4648 rows in manager batch rows.
- DHB: 959 rows in manager batch rows.

Important current blocker:
- The active live F scanner state currently shows `active_f061_run_id=fpm_td_synnex_20260519T090704Z`.
- That is the same run the TD Synnex plan says was bad and retired.
- Current active-run rows still look shifted:
  - example active run row has `supplier_sku=ADDON NETWORKING`, `supplier_title=104.75`, `unit_cost=177.55`.
  - expected clean TD row shape is like `supplier_sku=AP9815`, `supplier_title=UPS INTERFACE EXTENSION`, `unit_cost=30.93`.
- The clean manager batch rows do exist in `out/systems/F/price_list_manager/test_mode/batch_rows.csv`.
- The live active run appears to have reverted or continued from the bad 090704 active queue.

Meaning:
- F has real price-list data now.
- The manager-side TD Synnex converted batch is clean.
- The live scanner active queue currently conflicts with the plan's success claim.
- Before feeding F price-list cost into stock decisions, Phase 1 must make sure the live F active queue is clean or quarantined.

## 4. Current Stock-Decider Position
Evidence checked:
- `project_control/O_REORDER_INPUT_RULES.md`
- `project_control/OPERATIONS_LOOP_RESTOCK_IMPLEMENTATION_PLAN_2026-04-03.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/CODING_PLAN.md`
- O scripts under `scripts/flows/O/`
- O artifacts under `out/systems/O/live/`

Current O position:
- O restock scripts exist for source view, recommendations, review queue, decision events, purchase order drafts, ordered stock, receiving, send-to-Amazon queue, and UI.
- The active O plan says real SKU onboarding is still blocked pending approval.
- The latest O source view has 608 rows.
- Current recommendation and review queue files have 10 UI preview/sample rows, not a true live recommendation set.
- The readiness summary is old and says 608 rows considered, 0 actionable.

Current O artifact counts:
- `restock_source_view.csv`: 608 rows, modified 2026-04-29.
- `restock_recommendations_live.csv`: 10 rows, modified 2026-04-29.
- `restock_review_queue.csv`: 10 rows, modified 2026-04-29.
- `reorder_input_coverage_report.csv`: 608 rows, modified 2026-04-29.
- `purchase_orders_live.csv`: 1 row, header or placeholder state.

Current O cost behavior:
- `O001_build_restock_source_view.py` chooses cost from `supplier_catalog_price` first.
- If catalog price is missing, it falls back to `last_purchase_price`.
- If both are missing, the row is blocked as missing cost.

Current evidence from `out/product_db_preview.csv`:
- Rows: 608.
- Supplier catalog prices present: 0.
- Last purchase prices present: 132.
- Missing usable cost for O: 476.

Current evidence from `out/systems/O/live/restock_source_view.csv`:
- Cost source `last_purchase_price`: 132 rows.
- Cost source `missing_cost`: 476 rows.

Meaning:
- O has the right place to use a current supplier buy cost.
- O is not yet connected to the new F price-list manager cost truth.
- O cannot yet handle "actual paid was lower than price list, assume same discount next time but ask user".

## 5. Product DB Position
Evidence checked:
- `project_control/PRODUCT_DB_CONTRACT.md`
- `project_control/CURRENT_STATE.md`
- O source contracts

Current position:
- Product DB target authority is SQL, edited through UI.
- Legacy `out/product_db_preview.csv` is a stale mirror/export and is not the future authority.
- SQL Product DB proof has 659 rows, but O restock source view still uses `out/product_db_preview.csv`.

Meaning:
- The stock decider should not be expanded by patching `out/product_db_preview.csv`.
- The cost bridge should either read SQL Product DB safely or create an O-owned cost snapshot that can later be linked to SQL authority.
- Sheets must not be changed in this phase.

## 6. Exact Missing Information For Stock Decider
The stock decider needs a new buy-cost truth packet with these fields:

Identity:
- `seller_sku`
- `asin`
- `supplier_id`
- `supplier_name`
- `supplier_sku`
- `barcode`

Latest price-list evidence:
- `latest_price_list_unit_cost_gbp`
- `price_list_currency`
- `price_list_vat_basis`
- `price_list_stock_qty`
- `price_list_source_type`
- `price_list_batch_id`
- `price_list_row_key`
- `price_list_received_at_utc`
- `price_list_source_hash`

Actual purchase evidence:
- `last_purchase_unit_cost_gbp`
- `last_purchase_qty`
- `last_purchase_date_utc`
- `last_purchase_po_id`
- `last_purchase_supplier_invoice_ref`
- `last_purchase_was_discounted`

Discount logic:
- `last_list_cost_at_purchase_gbp`
- `actual_paid_vs_list_ratio`
- `assumed_next_discount_pct`
- `expected_next_unit_cost_gbp`
- `cost_confidence`
- `user_price_check_required`
- `user_price_check_reason`

Profit guard:
- `market_price_gbp`
- `market_price_basis_used`
- `expected_refund_cost_per_unit_gbp`
- `estimated_amazon_fee_gbp`
- `estimated_supplier_shipping_per_unit_gbp`
- `max_break_even_purchase_price_gbp`
- `max_target_roi_purchase_price_gbp`
- `target_roi_pct`
- `buy_allowed_at_expected_cost`

Stock/availability:
- `supplier_stock_status`
- `supplier_stock_qty`
- `supplier_stock_asof_utc`
- `supplier_stock_confidence`

## 7. Proposed Cost Rule
The proposed rule should work like this:

1. If actual paid cost equals the price-list cost used at that purchase, set discount ratio to 1.0000.
2. If actual paid cost is lower than the price-list cost used at that purchase, store the ratio:
   - example: actual GBP 1.80 / list GBP 2.00 = 0.9000.
3. When a new list price arrives:
   - if ratio is 1.0000, expected next cost is the new list price.
   - if ratio is below 1.0000, expected next cost is `new list price * ratio`.
4. If a discount ratio is being applied to a new list price, mark the row `user_price_check_required=1`.
5. If the user confirms the discounted price, update the actual purchase or user confirmation record.
6. If the user rejects it, use the confirmed price and reset the confidence state.

Example:
- old list price: GBP 2.00
- actual paid: GBP 1.80
- discount ratio: 0.90
- new list price: GBP 2.50
- expected next cost: GBP 2.25
- user check required: yes

## 8. Proposed Max Purchase Price Rule
The stock decider should show two separate numbers:

- Break-even max purchase price: the highest cost where profit is roughly zero.
- Target-ROI max purchase price: the highest cost where the product still meets the chosen margin target.

Simple formula for target ROI:

```txt
max_target_roi_purchase_price_gbp =
  net_sale_revenue_after_known_costs_gbp / (1 + target_roi_pct / 100)
```

Where `net_sale_revenue_after_known_costs_gbp` should subtract known selling-side costs before buy cost:
- Amazon fees
- expected refund drag
- VAT basis where applicable
- allocated supplier shipping where applicable

The first implementation should reuse the current O fields only where they are already trusted, then add missing fee/shipping fields as explicit blockers instead of guessing.

## 9. Plans Waiting To Be Implemented Or Finished
Relevant active work:
- `h-repricer-ceiling-floor-conversion-v2`: strategy conversion is still parked pending proof windows and sample thresholds.
- `h-phase1-pilot-timeout-budget-2026-05-11`: later proof exists, but current due register still tracks fresh-owner timeout-progressing proof from 2026-05-18.
- `h-repricer-tracker UI observation`: due-check register still needs user decision or fresh UI usage proof before retiring Sheet fallback.
- `f-price-list-process-manager-v1`: live manager exists and scans supplier rows, but current TD Synnex live active-run evidence conflicts with the clean-run success note.
- `td-synnex-email-price-files-2026-05-19`: manager-side import/conversion works, live scanner active queue currently needs source-truth triage.
- `clf-api-price-files-2026-05-19`: CLF is queued behind current TD run; due check `F_CLF_NEXT_BATCH_SELECTION` is open.
- `tropicana-email-price-files-2026-05-19`: intake works, but current file is stock-only and missing cost, so it cannot feed cost decisions yet.
- `o-restock-pack-and-db-through-use-v1`: Phase 3 pack-aware readiness and Phase 4 small real-data onboarding are still planned.

## 10. Research Conclusion
Do not start by changing the stock decider formula.

The right first move is to create a cost-truth bridge:
- clean F price-list evidence
- actual paid purchase evidence
- discount assumption state
- user confirmation state
- max purchase price thresholds

Only after that should O restock recommendations consume the new cost field.
