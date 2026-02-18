# WORK_LOG

[2026-02-06 10:48 UTC]
Layer: Setup
Scope: Work log initialization

Change:
- Created WORK_LOG.md
- Added work log rules to AGENTS.md

Files:
- WORK_LOG.md
- AGENTS.md

State:
- No pipeline changes
- No scripts run

Next:
- Add first real log entry after approved code change
---
[2026-02-10 13:29 UTC]
Layer: H Cycle / Head of Sales
Scope: Implement approved Phase 2 minimum price rule (10% ROI floor) and run proof

Change:
- Updated `scripts/H003_build_hos_guidelines_snapshot.py` to compute `min_price_gross` for each SKU row.
- Implemented formula:
  - `min_exvat = break_even_price_gbp + 0.10 * current_token_cost_gbp`
  - `min_price_gross = min_exvat * (1 + vat_rate_pct/100)` using E-aligned VAT fallback default.
- Added `reason_codes=missing_cost` when minimum price cannot be computed.
- Regenerated `out/hos_guidelines_snapshot_2026-02-10.csv` via `python scripts/H003_build_hos_guidelines_snapshot.py`.

Files:
- scripts/H003_build_hos_guidelines_snapshot.py
- out/hos_guidelines_snapshot_2026-02-10.csv
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/H003_build_hos_guidelines_snapshot.py` passed.
- Required proof:
  - created_file=`out/hos_guidelines_snapshot_2026-02-10.csv`
  - listing rows=10
  - hos rows=10
  - row_match=True
  - min_price_blank_count=0
  - sample_rows printed=3
- Latest cycle health snapshot after change (from `out/B_cycle.log`):
  - `health_snapshot_utc=2026-02-10T13:23:27Z`
  - `fail=0`, `warn=3`
  - warn checks: `h_e_inputs_fresh`, `h_e_outputs_latest_asof`, `h_refund_adjustment_history_idempotent_today`

Carryover:
- None

Next:
- Implement Phase 3 max price rule (Buy Box suppression ceiling) in `scripts/H003_build_hos_guidelines_snapshot.py`.
---
LOG ENTRY TEMPLATE (do not edit past entries)

[YYYY-MM-DD HH:MM UTC]
Layer:
Scope:

Change:
-

Files:
-

State:
-

Next:
-
---

[2026-02-06 11:05 UTC]
Layer: Setup
Scope: Work log hardening

Change:
- Appended reusable log entry template to WORK_LOG.md
- Declared WORK_LOG.md as source of truth over chat history in AGENTS.md

Files:
- WORK_LOG.md
- AGENTS.md

State:
- No pipeline changes
- No scripts run

Next:
- Adopt one-chat-one-ticket rotation rule

---

[]
Layer: E Cycle
Scope: E run/decision log scaffolding

Change:
- Added E run log append in E cycle runner
- Ensured E decision log exists with headers
- Added schema checks for E logs in A015

Files:
- scripts/run_E_cycle.py
- scripts/A015_build_system_health_check.py
- out/e_run_log.csv
- out/e_decision_log.csv

State:
- E cycle run executed
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=200 rows
- Logs: e_run_log=1 row, e_decision_log=0 rows
- Warning observed: ROI snapshot performance warning (lexsort depth)

---

[2026-02-06 11:33 UTC]
Layer: E Cycle
Scope: E run/decision log scaffolding

Change:
- Added E run log append in E cycle runner
- Ensured E decision log exists with headers
- Added schema checks for E logs in A015

Files:
- scripts/run_E_cycle.py
- scripts/A015_build_system_health_check.py
- out/e_run_log.csv
- out/e_decision_log.csv

State:
- E cycle run executed
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=200 rows
- Logs: e_run_log=1 row, e_decision_log=0 rows
- Warning observed: ROI snapshot performance warning (lexsort depth)

[2026-02-06 11:44 UTC]
Layer: E Cycle
Scope: Task 1 value metrics in E outputs and decision log

Change:
- Added profit_per_unit_gbp_30d and value_velocity_gbp_per_day to sku_performance_summary.csv
- Expanded e_decision_log.csv headers to include value metrics and auto-upgrade if file exists
- Updated health check schema for performance summary and decision log

Files:
- scripts/E004_build_performance_summary.py
- scripts/run_E_cycle.py
- scripts/A015_build_system_health_check.py
- out/sku_performance_summary.csv
- out/e_decision_log.csv
- out/e_run_log.csv

State:
- E cycle run executed
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=200 rows
- Headers: sku_performance_summary includes profit_per_unit_gbp_30d and value_velocity_gbp_per_day
- Headers: e_decision_log includes profit_per_unit_gbp_30d and value_velocity_gbp_per_day
- Warning observed: ROI snapshot performance warning (lexsort depth)

Next:
- Optional: remove ROI snapshot performance warning by refactoring FX lookup
---

[2026-02-06 12:10 UTC] Correction: The historical entry with header "[]" is invalid because it lacks a timestamp. This entry supersedes that invalid entry. No historical entries were edited or removed.

[2026-02-06 12:17 UTC]
Layer: E Cycle
Scope: Task 2 training set config + loader + health check

Change:
- Created config/f_training_set.csv with 10 approved SKUs
- Added training set loader helper (load_training_set, load_enabled_training_skus)
- Added health check schema validation for training set file

Files:
- config/f_training_set.csv
- scripts/f_training_set.py
- scripts/A015_build_system_health_check.py

State:
- Ran A015 health check
- Result: WARN (order_master_blank_cogs_lvl1plus = 3)
- Training set schema check: ok

Next:
- Optional: resolve missing COGS for the 3 rows in out/health_order_master_blank_cogs_lvl1plus.csv

[2026-02-06 12:27 UTC]
Layer: Setup
Scope: Correction of original invalid log header

Change:
- Confirmed the historical entry with header "[]" is invalid and remains only for audit trail
- Declared the timestamped entry at [2026-02-06 11:33 UTC] as the valid canonical record for that work

Files:
- WORK_LOG.md

State:
- Append-only policy preserved
- No historical entries edited or removed

Next:
- None
---
[2026-02-09 16:19 UTC]
Layer: Setup
Scope: Work log rotation archive and fresh-start section

Change:
- Archived current canonical log snapshot to `out/process_guides/archives/WORK_LOG_archive_20260209_1619UTC.md`.
- Started a fresh active section below for new tickets while preserving full append-only history above.

Files:
- WORK_LOG.md
- out/process_guides/archives/WORK_LOG_archive_20260209_1619UTC.md

State:
- Canonical log remains `WORK_LOG.md`.
- Historical entries preserved unchanged.
- New work should use the fresh section template below.

Carryover:
- None

Next:
- None
---

# FRESH START SECTION (2026-02-09 16:19 UTC)

[YYYY-MM-DD HH:MM UTC]
Layer:
Scope:

Change:
- 

Files:
- 

State:
- 

Carryover:
- None

Next:
- None
---

[2026-02-06 13:08 UTC]
Layer: B Cycle
Scope: Order_Master one-pass write with token COGS holdback

Change:
- Moved token allocation sheet sync ahead of allocation to prevent stale overwrite in B cycle
- Added guard to skip overwriting local token allocations when local has more rows than sheet
- Added final missing-COGS holdback guard immediately before Order_Master write

Files:
- scripts/run_B_cycle.py
- scripts/B030_sync_token_allocations_from_sheet.py
- scripts/B004_build_order_master.py
- out/orders_missing_tokens.csv
- out/system_health_checklist.csv

State:
- Ran scripts/B030_sync_token_allocations_from_sheet.py, scripts/B007_allocate_tokens_live.py, scripts/B025_build_token_cogs_ledger.py, scripts/B004_build_order_master.py, scripts/A015_build_system_health_check.py (quiet mode, no sheet writes)
- Order_Master rows: 6296
- A015: order_master_blank_cogs_lvl1plus=0 (ok)
- A015: order_master_row_drop=2 (warn), l1_keys_missing_in_master=0 with note held_back_missing_tokens=2
- orders_missing_tokens.csv: 2 rows (Order IDs 203-2197019-0361957 and 203-7566389-6305945)

Next:
- None

[2026-02-06 12:36 UTC]
Layer: E Cycle
Scope: Task 3 H001 daily offer snapshot

Change:
- Added H001 snapshot script with manual input stub and history upsert
- Added H schema checks for listing offer history and snapshot

Files:
- scripts/H001_capture_offer_snapshot.py
- scripts/A015_build_system_health_check.py
- out/listing_offer_snapshot_2026-02-06.csv
- out/listing_offer_history.csv
- imports/offer_snapshot_manual_template.csv

State:
- Ran scripts/H001_capture_offer_snapshot.py
- Snapshot rows: 10
- History rows: 10
- Ran scripts/A015_build_system_health_check.py (status OK, 62 checks)

Next:
- None
---
## 2026-02-06 14:00:50
- Ticket: Fix E002 SKU key so ROI output uses plain SKU strings
- Change: Updated E002 groupby to use a single SKU key (prevents tuple style keys)
- Files changed: scripts/E002_build_roi_snapshot.py
- Run: python scripts/run_E_cycle.py
- Proof: sku_sales_velocity.csv rows=402; sku_roi_snapshot.csv rows=66; sku_restock_signals.csv rows=134; sku_performance_summary.csv rows=134
- Proof: sku_roi_snapshot.csv sample SKU values are plain strings (example: 2G-AYBQ-TUQG, 3B-3H3V-Z93T)
- Alerts: health_status WARN; order_master_blank_cogs_lvl1plus warn=3
- Remaining jobs:
- Add v_blended placeholder to E001 output schema (no behavior change)
- Add projected ROI fields required by blueprint (current_token_cost_gbp, break_even_price_gbp, expected_refund_cost_per_unit_gbp, roi_at_our_price_pct, roi_at_buy_box_price_pct)
- Align run log format in guides vs code (e_run_log.jsonl vs e_run_log.csv)
- Add reason codes and needs_review in E outputs
- Wire E to current data sources (token costs, inbound, refunds, live prices) instead of manual inputs
- Carryover: - None
- Next: Start with v_blended placeholder in E001 and rerun E cycle with proof

## 2026-02-06 14:14:09 - E cycle FX lookup warning fix
- Change: Sorted FX rate MultiIndex before lookup to avoid pandas PerformanceWarning (no results change).
- Files: scripts/E002_build_roi_snapshot.py.
- Proof: Re-ran E cycle. Row counts: sku_sales_velocity.csv 402, sku_roi_snapshot.csv 66, sku_restock_signals.csv 134, sku_performance_summary.csv 134.
- Carryover: - None
- Next: - None


## 2026-02-06 14:23:23 - Task tracking for next chats
- Change: Recorded remaining tasks as Next items for upcoming chats.
- Files: WORK_LOG.md.
- State: No pipeline changes. No scripts run.
- Carryover: - None
- Next:
  - Add projected ROI fields required by blueprint (current_token_cost_gbp, break_even_price_gbp, expected_refund_cost_per_unit_gbp, roi_at_our_price_pct, roi_at_buy_box_price_pct).
  - Align run log format in guides vs code (e_run_log.jsonl vs e_run_log.csv).
  - Add reason codes and needs_review in E outputs.
  - Wire E to current data sources (token costs, inbound, refunds, live prices) instead of manual inputs.

[]
Layer: E Cycle
Scope: Task - add projected ROI placeholder fields in E performance summary

Change:
- Added projected ROI fields as blank placeholders in sku_performance_summary output
- Updated A015 schema check to require projected ROI columns in sku_performance_summary

Files:
- scripts/E004_build_performance_summary.py
- scripts/A015_build_system_health_check.py
- out/sku_performance_summary.csv
- out/e_run_log.csv

State:
- Ran scripts/run_E_cycle.py
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=134 rows
- sku_performance_summary header includes current_token_cost_gbp, break_even_price_gbp, expected_refund_cost_per_unit_gbp, roi_at_our_price_pct, roi_at_buy_box_price_pct

Next:
- Align run log format in guides vs code (e_run_log.jsonl vs e_run_log.csv)
- Add reason codes and needs_review in E outputs
- Wire E to current data sources (token costs, inbound, refunds, live prices) instead of manual inputs
---
[2026-02-06 14:34 UTC]
Layer: E Cycle
Scope: Task - add projected ROI placeholder fields in E performance summary

Change:
- Added projected ROI fields as blank placeholders in sku_performance_summary output
- Updated A015 schema check to require projected ROI columns in sku_performance_summary

Files:
- scripts/E004_build_performance_summary.py
- scripts/A015_build_system_health_check.py
- out/sku_performance_summary.csv
- out/e_run_log.csv

State:
- Ran scripts/run_E_cycle.py
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=134 rows
- sku_performance_summary header includes current_token_cost_gbp, break_even_price_gbp, expected_refund_cost_per_unit_gbp, roi_at_our_price_pct, roi_at_buy_box_price_pct

Next:
- Align run log format in guides vs code (e_run_log.jsonl vs e_run_log.csv)
- Add reason codes and needs_review in E outputs
- Wire E to current data sources (token costs, inbound, refunds, live prices) instead of manual inputs
---
## 2026-02-06 14:42:11
- Change: Added a Level 1 file stability gate (default 60s) to prevent building Order_Master while Level 1 is still updating.
- Change: Treat all-zero Level 1 fee groups as missing and drop those rows from Order_Master.
- Proof: Ran `ORDER_MASTER_SKIP_SHEETS=1 python scripts/B004_build_order_master.py` and verified the five orders now have non-zero fee totals in `out/order_master.csv`.
- Files: `scripts/B004_build_order_master.py`
- Carryover: - None
- Next: - None

[2026-02-06 14:48 UTC]
Layer: E Cycle
Scope: Align run log format with guide (jsonl)

Change:
- Switched E run log output to out/e_run_log.jsonl (append-only JSONL)
- Updated A015 health check to validate e_run_log.jsonl schema

Files:
- scripts/run_E_cycle.py
- scripts/A015_build_system_health_check.py
- out/e_run_log.jsonl

State:
- Ran scripts/run_E_cycle.py
- Outputs: sku_sales_velocity=402 rows, sku_roi_snapshot=66 rows, sku_restock_signals=134 rows, sku_performance_summary=134 rows
- e_run_log.jsonl lines=1 (last run_id 20260206T144623Z)

Next:
- None

[2026-02-06 14:52 UTC]
Layer: E Cycle
Scope: Record remaining E cycle jobs for next chat

Change:
- Recorded remaining E cycle jobs in Next

Files:
- WORK_LOG.md

State:
- No pipeline changes
- No scripts run

Next:
- Add reason codes and needs_review in E outputs
- Wire E to current data sources (token costs, inbound, refunds, live prices) instead of manual inputs

[2026-02-06 15:05 UTC]
Layer: E Cycle
Scope: Guidebook corrections for H (API-only)

Change:
- Clarified H001 is SP-API only for daily runs
- Marked manual exports as emergency one-off only (explicit approval required)
- Updated checklist and specs to reflect API-only default

Files:
- out/process_guides/E Cycle/Codex_task_cards_EHF0_v1.md
- out/process_guides/E Cycle/EHF_phases_v1.md
- out/process_guides/E Cycle/H0_listing_offer_history_spec_v1.md
- out/process_guides/E Cycle/F0_checklist_v1.md
- out/process_guides/E Cycle/Blueprint_E_H_F0_v1.md

State:
- No pipeline changes
- No scripts run

Next:
- Upgrade H001 to SP-API and wire into A before A015 (fail-soft)
---
[2026-02-06 15:17 UTC]
Layer: E Cycle
Scope: Upgrade H001 to SP-API and wire into A before A015 (fail-soft)

Change:
- Removed manual CSV input from H001; SP-API only
- Wired H001 into A run order before A015
- Made H001 fail-soft in A cycle

Files:
- scripts/H001_capture_offer_snapshot.py
- scripts/run_A_all.py

State:
- Ran H001 locally (non-live env) to validate outputs and schema

Next:
- None
## 2026-02-06 15:20:34
- Change: B007 now includes `out/orders_missing_tokens.csv` orders in allocation input to break the token COGS deadlock.
- Change: Updated token system rulebook to document allocation input behavior.
- Proof: Ran `python scripts/B007_allocate_tokens_live.py` and `python scripts/B004_build_order_master.py` then `python scripts/A015_build_system_health_check.py` with all checks OK.
- Proof: Orders 204-8462600-0884334, 204-9111630-6685926, 206-2030245-5732304 now appear in `out/order_master.csv` with non-zero COGS and fees.
- Files: `scripts/B007_allocate_tokens_live.py`; `out/process_guides/token_system_rulebook.md`
- Carryover: - None
- Next: - None

[2026-02-06 16:04 UTC]
Layer: E Cycle
Scope: Phase 1 pricing parser root-cause fix (SKU extraction)

Change:
- Patched pricing adapter to extract SKU from both payload shapes: top-level SellerSKU/SellerSku and fallback Identifier.SellerSKU/SellerSku
- Kept scope limited to parser fix and validation only (no VAT work, no sheet changes)

Files:
- scripts/api/get_pricing.py
- out/listing_offer_snapshot_2026-02-06.csv

State:
- Ran direct unit-style probe before H001 using 5 SKUs
- Proof: len(price_map)=5 and keys present: 6V-EEC1-2S9Z, AX-NKNU-29C1, JB-RGB6-LZOJ, VF-3T0K-DR5O, XY-UM2X-TPS3
- Ran scripts/H001_capture_offer_snapshot.py
- Proof: snapshot rows=10, buy_box_price non-empty=10
- Ran scripts/A015_build_system_health_check.py for reporting
- A015 status: FAIL/WARN present (l1_keys_missing_in_master fail=1; warnings present)
- Known VAT guardrail FAILs remain out of scope for this ticket: fee_vat_missing_rows_gbp, vat_daily_fresh

Carryover:
- None

Next:
- Implement H001 minimum market context enrichment (buy_box_channel, lowest_fba_price, lowest_fbm_price, offer_count_fba, offer_count_fbm)
---
[2026-02-06 16:35 UTC]
Layer: E Cycle
Scope: Phase 1 - single SP-API owner, lock/throttle, and observability logs

Change:
- Added shared SP-API owner layer with cross-process lock, persistent throttle state, and call-level JSONL logging
- Created `run_api_collection.py` as the single API collection entrypoint and run-summary logger
- Rewired `scripts/H001_capture_offer_snapshot.py` to delegate to `run_api_collection.py` (no direct SP-API calls in H001)
- Added A015 health checks for new API observability outputs and lock-presence alerting

Files:
- scripts/api/spapi_owner.py
- scripts/api/get_pricing.py
- scripts/api/get_listing_item_price.py
- run_api_collection.py
- scripts/H001_capture_offer_snapshot.py
- scripts/A015_build_system_health_check.py

State:
- Ran `python run_api_collection.py` (live): produced `SKIPPED_LOCK_BUSY` row while lock was held, then successful runs
- Ran `python scripts/H001_capture_offer_snapshot.py` (delegated path) successfully
- Ran `python scripts/A015_build_system_health_check.py` with new checks active

Proof:
- `out/api_run_log.csv` now contains required rows and statuses: `SKIPPED_LOCK_BUSY` and `OK`
- `out/api_call_log.jsonl` now populated (33 lines)
- `out/api_rate_state.json` exists with endpoint state for `listings_items_get_item` and `products_pricing_get_price`
- Snapshot reconciliation: `rows=10`, `buy_box_price_filled=10`, `lowest_fba_filled=0`, `lowest_fbm_filled=0`
- A015 new checks: `h_schema_api_call_log=ok`, `h_schema_api_run_log=ok`, `h_schema_api_rate_state=ok`, `h_spapi_lock_present=ok`

Carryover:
- Populate Phase 3 market context fields in snapshot (`buy_box_channel`, `lowest_fba_price`, `lowest_fbm_price`, `offer_count_fba`, `offer_count_fbm`) via API-owner pipeline

Next:
- Resolve active WARN checks in A015 (`order_master_blank_cogs_lvl1plus`, `b_cycle_recent_fail_lines`, `fee_rules_unknown_countries`)
---
[2026-02-07 11:18 UTC]
Layer: E Cycle
Scope: Phase 3 minimum market context enrichment via API-owner pipeline

Change:
- Switched H001 market context source to SP-API ASIN offers endpoint (`/products/pricing/v0/items/{asin}/offers`) through shared owner layer
- Added parser support for buy_box_channel, lowest_fba_price, lowest_fbm_price, offer_count_fba, offer_count_fbm
- Kept fail-soft behavior: rows still write, blanks remain blank, reasons added in `notes` when buy box fields are missing
- Added A015 health check `h_market_context_fill_nonzero` to enforce non-zero fill visibility for Phase 3 fields

Files:
- scripts/api/get_pricing.py
- run_api_collection.py
- scripts/A015_build_system_health_check.py
- out/listing_offer_snapshot_2026-02-07.csv
- out/listing_offer_history.csv
- out/api_call_log.jsonl
- out/api_run_log.csv
- out/system_health_checklist.csv

State:
- Ran `python scripts/H001_capture_offer_snapshot.py`
- Snapshot rows: 10
- History rows: 20
- Fill proof (snapshot): buy_box_price=8, buy_box_channel=8, lowest_fba_price=10, lowest_fbm_price=9, offer_count_fba=10, offer_count_fbm=9
- API call log proof (tail): http_status 200 only; endpoint counts include `products_pricing_get_item_offers` and `listings_items_get_item`
- API run log latest OK run: `api_20260207T110817Z_fca6bb0f` with calls_products_pricing_get_price=10 and calls_listings_items_get_item=10
- Ran `python scripts/A015_build_system_health_check.py`
- A015 new check: `h_market_context_fill_nonzero=ok`
- Active WARNs remain outside this ticket: `order_master_blank_cogs_lvl1plus=7`, `b_cycle_recent_fail_lines=13`, `fee_rules_unknown_countries=1`

Carryover:
- None

Next:
- Clear active A015 WARN items in B/Fee pipeline root causes before publish gates
---
[2026-02-07 11:32 UTC]
Layer: B/Fee + A015 Health Gate
Scope: Clear active A015 WARN items in B/Fee pipeline root causes before publish gates

Change:
- Fixed B004 root-cause behavior so Level 1 file instability returns non-zero (retry path) instead of silent success.
- Hardened B004 token COGS merge by normalizing join keys and adding strict pre-write hold-back for qty>0 rows with zero token COGS.
- Fixed B004 hold-back artifact write order so `out/orders_missing_tokens.csv` persists dropped keys for health reconciliation.
- Added QA fee VAT rule to remove unknown country warning source.
- Tightened A015 log-fail parsing to count only real B-cycle script failures (`] fail `), not health gate skip lines.
- Updated A015 row-drop logic so explained hold-backs are treated as OK (no false WARN).

Files:
- scripts/B004_build_order_master.py
- scripts/A015_build_system_health_check.py
- reference/fee_vat_rules.csv
- out/orders_missing_tokens.csv
- out/system_health_checklist.csv

State:
- Ran `python scripts/B025_build_token_cogs_ledger.py`
- Ran `python scripts/B004_build_order_master.py` with `ORDER_MASTER_SKIP_SHEETS=1`, `ORDER_MASTER_INCREMENTAL=1`, `ORDER_MASTER_L1_STABLE_SECONDS=0`
- Ran `python scripts/A015_build_system_health_check.py`

Proof:
- `out/system_health_checklist.csv` now shows:
  - `order_master_blank_cogs_lvl1plus=ok (0)`
  - `b_cycle_recent_fail_lines=ok (0)`
  - `fee_rules_unknown_countries=ok (0)`
  - `l1_keys_missing_in_master=ok (0)` with `held_back_missing_tokens=2`
- `out/orders_missing_tokens.csv` now contains the held-back keys instead of being overwritten blank.

Carryover:
- None

Next:
- None
---
[2026-02-07 11:47 UTC]
Layer: E Cycle
Scope: Phase 4 inventory and inbound consolidation into single API owner

Change:
- Moved inventory summaries API calls onto the shared SP-API owner client path (`spapi_get`) with unified throttle and call logging.
- Extended `run_api_collection.py` to collect `inventory_inbound` datasets under lock control and write contract outputs:
  - `out/inventory_snapshot_YYYY-MM-DD.csv`
  - `out/inbound_snapshot_YYYY-MM-DD.csv`
  - `out/inventory_history.csv` (idempotent upsert by `asof_date+sku+marketplace`)
  - `out/inbound_history.csv` (idempotent upsert by `asof_date+sku+marketplace`)
- Kept compatibility output `out/inventory_summaries.csv` for downstream B/E scripts.
- Added root-cause hardening in history upsert to discard blank-key rows before dedupe.
- Updated `A003_run_inventory_to_sheet.py` default behavior to use API owner collection (`INVENTORY_USE_API_OWNER=1`) instead of direct SP-API calls.
- Added Phase 4 A015 health checks and alert conditions for:
  - inventory/inbound snapshot schema
  - inventory/inbound history schema
  - same-day idempotency duplicate-key checks

Files:
- scripts/api/get_inventory_summaries.py
- run_api_collection.py
- scripts/A003_run_inventory_to_sheet.py
- scripts/A015_build_system_health_check.py
- out/inventory_snapshot_2026-02-07.csv
- out/inbound_snapshot_2026-02-07.csv
- out/inventory_history.csv
- out/inbound_history.csv
- out/system_health_checklist.csv
- out/api_call_log.jsonl
- out/api_run_log.csv

State:
- Ran `python run_api_collection.py` with `API_COLLECTION_DATASETS=inventory_inbound` multiple times.
- Snapshot proof: inventory_snapshot_rows=336, inbound_snapshot_rows=336.
- History proof after rerun same day: inventory_history_rows=336, inbound_history_rows=336 (no growth on rerun).
- Idempotency proof: inventory_history_today_dup_keys=0, inbound_history_today_dup_keys=0 for 2026-02-07.
- Observability proof: `out/api_call_log.jsonl` shows endpoint `fba_inventory_get_summaries` with HTTP 200 entries; `out/api_run_log.csv` rows include `datasets=inventory_inbound`.
- Ran `python scripts/A015_build_system_health_check.py`.
- A015 status: all checks `ok`, including new Phase 4 checks (`h_schema_inventory_snapshot`, `h_schema_inbound_snapshot`, `h_schema_inventory_history`, `h_schema_inbound_history`, `h_inventory_history_idempotent_today`, `h_inbound_history_idempotent_today`).

Carryover:
- None

Next:
- None
---
[2026-02-07 11:53 UTC]
Layer: E Cycle
Scope: Phase 5 refund/adjustment signal capture via API-owner pipeline

Change:
- Added Phase 5 dataset collection to `run_api_collection.py` under `refunds_adjustments` through shared SP-API owner (`spapi_get`) with lock/throttle/call logging.
- Added contract outputs:
  - `out/refund_adjustment_snapshot_YYYY-MM-DD.csv`
  - `out/refund_adjustment_history.csv` (idempotent upsert by `asof_date+sku+marketplace`)
- Added fail-soft behavior: training-set SKUs still write daily rows with blank/zero metrics and `notes=no_financial_events_in_window` when no events are returned.
- Extended API run log schema/counts to include `calls_finances_get_financial_events`.
- Added A015 checks for refund/adjustment schema and same-day idempotency.
- Hardened financial window root cause by clamping `PostedBefore` to current UTC minus 3 minutes to avoid SP-API future-date rejection.
- Sanitized API run-log notes to single-line text.

Files:
- run_api_collection.py
- scripts/A015_build_system_health_check.py
- out/refund_adjustment_snapshot_2026-02-07.csv
- out/refund_adjustment_history.csv
- out/system_health_checklist.csv
- out/api_call_log.jsonl
- out/api_run_log.csv

State:
- Ran `python run_api_collection.py` with `API_COLLECTION_DATASETS=refunds_adjustments` twice (plus one final normalization run).
- Snapshot rows: 10
- History rows after reruns: 10 (no growth)
- Idempotency proof: `today_dup_keys=0` for `asof_date=2026-02-07`
- API call log proof: endpoint `finances_get_financial_events` with HTTP 200 entries in `out/api_call_log.jsonl`
- API run log proof: latest rows show `calls_finances_get_financial_events=1` and `datasets=refunds_adjustments`
- A015 run result: OK, including:
  - `h_schema_refund_adjustment_snapshot=ok`
  - `h_schema_refund_adjustment_history=ok`
  - `h_refund_adjustment_history_idempotent_today=ok`
- Current refund/adjustment counts are zero for the training SKUs in today window; gaps are explicit via notes.

Carryover:
- None

Next:
- None
---
[2026-02-07 12:49 UTC]
Layer: E Cycle
Scope: Phase 6 hardening - canonical asof_date key for listing history + idempotency and recent API FAIL visibility in A015

Change:
- Added `asof_date` to listing offer snapshot/history contract and set it at collection time.
- Switched listing offer history upsert key from `timestamp_utc+sku+marketplace` to `asof_date+sku+marketplace`.
- Extended A015 schema checks to require `asof_date` on listing offer snapshot/history.
- Added A015 check `h_listing_offer_history_idempotent_today`.
- Added A015 check `h_api_recent_fail_runs` (24h window, env override: `API_RUN_FAIL_LOG_HOURS`).

Files:
- run_api_collection.py
- scripts/A015_build_system_health_check.py
- out/listing_offer_snapshot_2026-02-07.csv
- out/listing_offer_history.csv
- out/system_health_checklist.csv
- out/health_status.csv

State:
- Ran `python run_api_collection.py` for listing offer reruns and inventory/refund refresh.
- Ran `python scripts/A015_build_system_health_check.py`.
- Proof row counts: listing_offer_history=10, inventory_history=336, inbound_history=336, refund_adjustment_history=10.
- Proof idempotency checks: `h_listing_offer_history_idempotent_today=ok (0)`, `h_inventory_history_idempotent_today=ok (0)`, `h_inbound_history_idempotent_today=ok (0)`, `h_refund_adjustment_history_idempotent_today=ok (0)`.
- Active alert: `h_api_recent_fail_runs=warn (1)` due historical FAIL in 24h window in `out/api_run_log.csv` (financial events date-window failure at 2026-02-07T11:51:40Z).

Carryover:
- None

Next:
- None
---
[2026-02-07 13:10 UTC]
Layer: E Cycle
Scope: Phase 7 activation - cadence enforcement + E freshness/lineage health checks

Change:
- Added cadence gate in `scripts/run_E_cycle.py` (default 24h) with explicit `skipped_cadence` run-log status when blocked.
- Hardened E run IDs to microsecond precision to avoid same-second run-id collisions.
- Added Phase 7 A015 checks for E cadence and data lineage:
  - `h_e_cadence_enforced`
  - `h_e_inputs_fresh`
  - `h_e_outputs_latest_asof`
- Added active guidebook `out/process_guides/e_cycle_runbook.md` with cadence controls, validation checks, and recovery steps.

Files:
- scripts/run_E_cycle.py
- scripts/A015_build_system_health_check.py
- out/process_guides/e_cycle_runbook.md
- out/e_run_log.jsonl
- out/system_health_checklist.csv
- out/health_status.csv

State:
- Ran `python scripts/run_E_cycle.py` with `E_CADENCE_HOURS=0` (proof run executed).
- Ran `python scripts/run_E_cycle.py` with `E_CADENCE_HOURS=24` (proof run skipped by cadence).
- Ran `python scripts/A015_build_system_health_check.py`.
- Proof outputs:
  - `out/sku_sales_velocity.csv` rows=402
  - `out/sku_roi_snapshot.csv` rows=66
  - `out/sku_restock_signals.csv` rows=134
  - `out/sku_performance_summary.csv` rows=134
- Proof E run log:
  - success run_id `20260207T130956589439Z`
  - skipped_cadence run_id `20260207T131006016780Z`
- A015 result: OK with new checks all `ok` (`h_e_cadence_enforced`, `h_e_inputs_fresh`, `h_e_outputs_latest_asof`).

Carryover:
- None

Next:
- None
---

[2026-02-07 15:48 UTC]
Layer: E Cycle
Scope: Phase 1.0 observation schema lock-candidate contract

Change:
- Upgraded Phase 1.0 schema guide from concept draft to lock-candidate contract format.
- Added explicit field-level schema contracts (type, nullability, units, notes) across all 6 domains.
- Added source mapping section showing current files, current script owners, and capture gaps.
- Added lock conditions and step-by-step execution plan to reach Locked v1.0.
- Updated status marker to Draft v0.2 (Lock candidate).

Files:
- out/process_guides/live_plan/phase_1_0_observation_schema.md

State:
- Documentation change only; no pipeline scripts changed.
- Validation evidence captured via section presence checks in updated schema file.
- Active health alert remains: order_master_date_gap_hours=3.84 (WARN) from out/system_health_checklist.csv.

Carryover:
- None

Next:
- Convert lock-candidate to Locked v1.0 after implementing missing upstream capture fields and passing A015 with clean proof.
---
[2026-02-07 16:04 UTC]
Layer: E Cycle
Scope: Phase 1.0 observation schema execution - seller-level capture + Phase1 history + A015 coverage

Change:
- Added seller-level offer capture from SP-API pricing payload in scripts/api/get_pricing.py.
- Added new collection outputs in un_api_collection.py:
  - out/listing_offer_seller_snapshot_YYYY-MM-DD.csv
  - out/listing_offer_seller_observation_history.csv (idempotent key: asof_date+marketplace+sku+asin+seller_id)
- Added Phase 1 seller history builder scripts/H002_build_phase1_seller_history.py producing:
  - out/phase1_seller_history.csv
  - materialized fields: first/last seen, continuous presence, absence gap, reentry flag, offer price, rolling min/max/median, time-at-min/max.
- Extended A015 in scripts/A015_build_system_health_check.py with schema and idempotency checks for new seller-level outputs:
  - h_schema_listing_offer_seller_history
  - h_schema_phase1_seller_history
  - h_schema_listing_offer_seller_snapshot
  - h_listing_offer_seller_history_idempotent_today

Files:
- scripts/api/get_pricing.py
- run_api_collection.py
- scripts/H002_build_phase1_seller_history.py
- scripts/A015_build_system_health_check.py
- out/listing_offer_seller_snapshot_2026-02-07.csv
- out/listing_offer_seller_observation_history.csv
- out/phase1_seller_history.csv
- out/system_health_checklist.csv
- out/health_status.csv
- out/api_run_log.csv

State:
- Ran python -m py_compile run_api_collection.py scripts/api/get_pricing.py scripts/H002_build_phase1_seller_history.py scripts/A015_build_system_health_check.py.
- Ran listing capture with API_COLLECTION_DATASETS=listing_offer: latest run pi_20260207T155332Z_555c850d status OK.
- Evidence row counts:
  - listing_offer_seller_observation_history = 91
  - phase1_seller_history = 91
- Evidence duplicate-key checks:
  - seller observation history duplicates on sof_date+marketplace+sku+asin+seller_id = 0
  - phase1 seller history duplicates on sof_date+marketplace+sku+asin+seller_id = 0
- Ran python scripts/A015_build_system_health_check.py.
- A015 proof result: status=success, ows=85, latest out/health_status.csv = OK, fail=0, warn=0.

Carryover:
- None

Next:
- Extend seller interaction metrics (price_move_initiations, ollow_events, eaction_lag_minutes, directional_bias, loor_set_events) in Phase 1 output.
---
---
[2026-02-09 09:33 UTC]
Layer: B Cycle
Scope: Remove E cycle from B run so B loop runs independently

Change:
- Removed E cycle invocation from scripts/run_B_cycle.py.
- Removed E scheduling state from B loop (E_INTERVAL_HOURS, E_STATE_PATH, _should_run_e, _mark_e_ran).
- Kept B fast-loop order and existing A015 publish gate unchanged.

Files:
- scripts/run_B_cycle.py
- out/B_cycle.log
- out/system_health_checklist.csv

State:
- Ran python -m py_compile scripts/run_B_cycle.py (pass).
- Verified code has no E hooks in B loop (un_E_cycle, _should_run_e, E_STATE_PATH not present).
- Ran B cycle validation attempt with B_RUN_ONCE=1 and B_CYCLE_SLEEP_SECONDS=0; command timed out after 10 minutes because child B tasks were still running, then test processes were stopped.
- Log evidence after patch: out/B_cycle.log on 2026-02-09 has ecent_lines=2969 and ecent_e_lines=0.
- A015 evidence from python scripts/A015_build_system_health_check.py:
  - orders_all rows=6649
  - order_items_all rows=6667
  - order_master rows=6490
  - token_ledger rows=9481
  - token_cogs rows=7418

Carryover:
- None

Next:
- Resolve order_master_orphans_count=3 in A015 so B publish can proceed (current B behavior: health_check FAIL - skip publish).
---
[2026-02-09 09:33 UTC]
Layer: B Cycle
Scope: Correction entry for previous log line formatting artifact

Change:
- Correction only. Previous entry remains unchanged to preserve append-only history.
- Canonical record: E cycle call path was removed from scripts/run_B_cycle.py so B no longer triggers run_E_cycle.py.
- Removed E scheduling fields and helpers from B loop: E_INTERVAL_HOURS, E_STATE_PATH, _should_run_e, _mark_e_ran.

Files:
- scripts/run_B_cycle.py
- out/B_cycle.log
- out/system_health_checklist.csv

State:
- py_compile check passed for scripts/run_B_cycle.py.
- Code grep confirms no E hooks remain in scripts/run_B_cycle.py.
- B log proof for 2026-02-09: recent_lines=2969, recent_e_lines=0.
- Health check proof snapshot:
  - orders_all rows=6649
  - order_items_all rows=6667
  - order_master rows=6490
  - token_ledger rows=9481
  - token_cogs rows=7418

Carryover:
- None

Next:
- Resolve order_master_orphans_count=3 in A015 so B publish can proceed. Current behavior in B log: health_check FAIL - skip publish.
---
[2026-02-09 10:07 UTC]
Layer: B Cycle
Scope: Fix order_master orphan FAIL caused by canceled orders dropping from Level 1

Change:
- Root cause confirmed: canceled orders were being removed from Level 1 as intended, but stale keys were retained in Order_Master during incremental behavior, causing false orphan FAILs.
- Added a root-cause fix in scripts/B004_build_order_master.py to purge existing Order_Master keys that are no longer present in current Level 1 keys before merge.
- This keeps Order_Master keyspace aligned to current Level 1 and prevents stale canceled-order rows from persisting.

Files:
- scripts/B004_build_order_master.py
- out/system_health_checklist.csv
- out/health_status.csv

State:
- Ran python scripts/B004_build_order_master.py (pass).
- Ran python scripts/A015_build_system_health_check.py after B004 completion.
- Proof before fix: order_master_orphans_count=3 (keys: 206-7674021-1046764||NN-TSZ1-X2RD, 202-4375137-4695516||C6-XGZB-J6QA, 206-4979514-5952330||T8-6UWL-I3E1).
- Proof after fix:
  - order_master rows: 6489 -> 6486
  - order_master_orphans_count: 3 -> 0
  - l1_keys_missing_in_master: 0
- Current alerts remaining after orphan fix:
  - WARN fee_rules_unknown_countries=1 (BE)
  - WARN h_e_inputs_fresh
  - WARN h_listing_offer_history_idempotent_today
  - WARN h_listing_offer_seller_history_idempotent_today
  - WARN h_refund_adjustment_history_idempotent_today

Carryover:
- None

Next:
- Resolve remaining WARN checks listed above to return health to OK.
[2026-02-09 12:08 UTC]
Layer: E Cycle
Scope: Phase 1.0 observation schema execution - extend seller history metrics and align A015 schema

Change:
- Extended `scripts/H002_build_phase1_seller_history.py` to materialize additional Phase 1 fields from upstream history context:
  - interaction: `price_move_initiations`, `directional_bias`, `floor_set_events`
  - delivery: `delivery_delta_vs_fastest_days`
  - our behavior: `our_price_changes`
- Added listing-history context loader in H002 to derive `our_price_changes` from `out/listing_offer_history.csv`.
- Updated `scripts/A015_build_system_health_check.py` Phase 1 schema check to require the new `phase1_seller_history` columns.
- Updated `out/process_guides/live_plan/phase_1_0_observation_schema.md` mapping and next steps to match implemented state.

Files:
- scripts/H002_build_phase1_seller_history.py
- scripts/A015_build_system_health_check.py
- out/process_guides/live_plan/phase_1_0_observation_schema.md
- out/phase1_seller_history.csv
- out/system_health_checklist.csv
- out/health_status.csv

State:
- Ran `python scripts/H002_build_phase1_seller_history.py`.
- Proof: `out/phase1_seller_history.csv` rows=91.
- Proof: duplicate keys on `asof_date+marketplace+sku+asin+seller_id` = 0.
- Proof: new columns present and filled across 91 rows (`price_move_initiations`, `directional_bias`, `floor_set_events`, `delivery_delta_vs_fastest_days`, `our_price_changes`).
- Ran `python scripts/A015_build_system_health_check.py` with updated schema checks.
- Latest health snapshot at 2026-02-09T12:07:26.243107+00:00: WARN fail=0 warn=6.
- Active alerts at log time: `order_master_blank_cogs_lvl1plus`, `fee_rules_unknown_countries`, `h_e_inputs_fresh`, `h_e_outputs_latest_asof`, `h_spapi_lock_present`, `h_refund_adjustment_history_idempotent_today`.

Carryover:
- Clear active A015 WARN items to restore clean publish gate state after Phase 1.0 execution updates.

Next:
- None
---
[2026-02-09 12:50 UTC]
Layer: E Cycle
Scope: Phase 1.0 lock proof hardening - add Phase 1 type and idempotency health checks

Change:
- Added Phase 1 contract-type health check `h_phase1_contract_types` in `scripts/A015_build_system_health_check.py`.
- Added Phase 1 global idempotency health check `h_phase1_history_idempotent` on key `asof_date+marketplace+sku+asin+seller_id`.
- Wired both checks into the A015 main health run after `h_schema_phase1_seller_history`.

Files:
- scripts/A015_build_system_health_check.py
- out/phase1_seller_history.csv
- out/system_health_checklist.csv
- out/health_status.csv

State:
- Ran `python scripts/H002_build_phase1_seller_history.py`.
- Proof: `out/phase1_seller_history.csv` rows=179; duplicate keys on `asof_date+marketplace+sku+asin+seller_id` = 0.
- Ran `python scripts/A015_build_system_health_check.py`.
- Proof checks:
  - `h_schema_phase1_seller_history=ok`
  - `h_phase1_contract_types=ok (0)`
  - `h_phase1_history_idempotent=ok (0)`
  - `h_listing_offer_history_idempotent_today=ok (0)`
  - `h_listing_offer_seller_history_idempotent_today=ok (0)`
- Latest health snapshot: `status=WARN`, `fail_count=0`, `warn_count=4` at `2026-02-09T12:46:00.626804+00:00`.

Carryover:
- Clear active A015 WARN items to restore clean publish gate state after Phase 1.0 execution updates.

Next:
- After WARN cleanup, update `out/process_guides/live_plan/phase_1_0_observation_schema.md` status to `Locked v1.0` and rerun proof.
---
[2026-02-09 13:40 UTC]
Layer: B Cycle
Scope: Maintenance guardrails to prevent overlap with background loop and make rules persistent for new chats

Change:
- Added maintenance stop controls to scripts/run_B_cycle.py:
  - env switch B_CYCLE_MAINTENANCE_MODE=1
  - file switch out/locks/b_cycle.maintenance (path override via B_CYCLE_MAINTENANCE_FLAG_PATH)
  - optional reason (B_CYCLE_MAINTENANCE_REASON or first line of flag file)
  - operator ETA message via B_CYCLE_MAINTENANCE_ETA_MINUTES (default 13)
- Added maintenance checks before each cycle, before each script, before retries, and before publish.
- Fixed un_B_cycle.py lock release parsing so lock files are removed correctly when lock payload uses pid= format.
- Updated AGENTS.md with mandatory "B cycle maintenance safety" rules so fresh Codex chats apply this immediately.
- Updated out/process_guides/b_cycle_runbook.md with pause/resume maintenance commands and behavior.

Files:
- scripts/run_B_cycle.py
- AGENTS.md
- out/process_guides/b_cycle_runbook.md

State:
- Validation run: created out/locks/b_cycle.maintenance, ran python scripts/run_B_cycle.py with B_RUN_ONCE=1.
- Proof: loop exited cleanly with message maintenance stop ... loop killed, check back in 13 minutes.
- Proof: exit code   and out/B_cycle.lock not present after exit (lock_present=0).

Carryover:
- None

Next:
- Add the same maintenance gate check to any manual maintenance wrapper scripts that can invoke B scripts directly.
---
[2026-02-09 13:40 UTC]
Layer: B Cycle
Scope: Correction entry for prior maintenance-guardrails log (append-only clarification)

Change:
- Clarified prior entry text where PowerShell escaping corrupted two literals.
- Correct literal path: scripts/run_B_cycle.py.
- Correct validation result: exit code  .

Files:
- WORK_LOG.md

State:
- Prior entry remains unchanged (append-only policy preserved).
- This correction entry is authoritative for the two corrupted literals only.

Carryover:
- None

Next:
- None
---
['2026-02-09 13:40 UTC']
Layer: B Cycle
Scope: Final plain-text correction for maintenance-guardrails log

Change:
- Correct file path text: scripts/run_B_cycle.py
- Correct validation result text: exit code zero

Files:
- WORK_LOG.md

State:
- This plain-text correction supersedes corrupted glyphs in the two previous entries.

Carryover:
- None

Next:
- None
---
[2026-02-09 13:42 UTC]
Layer: B Cycle
Scope: Maintenance mode auto-resume (sleep and recheck) instead of full stop

Change:
- Updated scripts/run_B_cycle.py so maintenance mode no longer exits the loop.
- New behavior: when maintenance is active, the loop pauses, sleeps, and rechecks until maintenance clears, then resumes automatically.
- Added env setting B_CYCLE_MAINTENANCE_SLEEP_SECONDS (default 900 seconds = 15 minutes).
- Kept operator message with check back in N minutes via B_CYCLE_MAINTENANCE_ETA_MINUTES.
- Updated AGENTS.md and out/process_guides/b_cycle_runbook.md to describe the new pause-and-resume behavior.

Files:
- scripts/run_B_cycle.py
- AGENTS.md
- out/process_guides/b_cycle_runbook.md

State:
- Ran function-level verification for maintenance wait/resume logic using test flag file out/locks/b_cycle.maintenance.test.
- Proof output showed repeated maintenance pause logs, then automatic resume after flag removal.
- Proof result: status ok, elapsed about 3 seconds with sleep interval forced to 1 second for test.

Carryover:
- None

Next:
- None
---
[2026-02-09 14:09 UTC]
Layer: A/B Orchestration
Scope: Implement cycle-safe maintenance handshake where A waits for B cycle boundary and B pauses only after full cycle completion

Change:
- Updated scripts/run_B_cycle.py:
  - Added handshake paths:
    - out/locks/maintenance.requested
    - out/locks/maintenance.ready
    - out/locks/maintenance.active
  - B now checks maintenance only at cycle boundaries for A handoff.
  - When maintenance is requested, B writes maintenance.ready only after finishing the current full cycle, then pauses.
  - B resumes automatically after maintenance flags are cleared.
  - Legacy manual toggle out/locks/b_cycle.maintenance remains supported.
- Updated scripts/run_A_all.py:
  - A now requests maintenance at startup (maintenance.requested).
  - A waits for B readiness signal (maintenance.ready) or proceeds immediately if B is not running.
  - A sets maintenance.active while running.
  - A always clears maintenance.active/requested/ready in finally block.
- Updated AGENTS.md and out/process_guides/b_cycle_runbook.md to document maintenance priority and handshake sequence.

Files:
- scripts/run_B_cycle.py
- scripts/run_A_all.py
- AGENTS.md
- out/process_guides/b_cycle_runbook.md

State:
- Validation: python -m py_compile scripts/run_B_cycle.py
- Validation: python -m py_compile scripts/run_A_all.py
- Both compilation checks passed.

Carryover:
- None

Next:
- Run one controlled morning handoff test with B active and A launch to capture timing proof in logs.
---
[2026-02-09 14:10 UTC]
Layer: Ticket Close
Scope: Confirmed B004 and A015 proof run; close ticket and sign out

Change:
- Verified manual run evidence provided by user:
  - B004 completed successfully with rows=6513.
  - A015 completed with all checks OK except cadence warning.
- No additional code changes in this close step.

Files:
- WORK_LOG.md

State:
- A015 status is WARN only on h_e_cadence_enforced (required_hours=24.00).
- All other checks are OK in the latest run.

Carryover:
- Clear h_e_cadence_enforced WARN after cadence window naturally passes.

Next:
- None
---
[2026-02-09 15:16 UTC]
Layer: Agent Policy
Scope: Prevent ad-hoc A script runs and enforce cycle-based verification handoff

Change:
- Updated AGENTS.md with new section `14) Verification policy (no ad-hoc A runs by Codex)`.
- Added rule: Codex must not run A015 or other A scripts unless explicitly requested by user.
- Added rule: default evidence must come from last completed cycle artifacts (`out/system_health_checklist.csv`, `out/B_cycle.log`, `out/run_cycle.log`).
- Added pending-verification handoff format with timestamps for post-change validation by next scheduled cycle.

Files:
- AGENTS.md

State:
- Rule is active in repo instructions and discoverable by grep.
- No runtime data scripts were executed for sign-off in this step.
- Verification status: Pending next cycle check
- Changed at: 2026-02-09T15:15:00Z
- Latest health snapshot at: 2026-02-09T15:12:34Z
- Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-09 15:21 UTC]
Layer: Phase 1.0 Live Plan Review
Scope: Read phase_1_0_observation_schema.md, assess completion status, define next step, provide evidence, and log after approval

Change:
- Reviewed `out/process_guides/live_plan/phase_1_0_observation_schema.md` against current artifacts and script ownership.
- Confirmed achieved items:
  - Phase 1.0 field contracts and status matrix are documented.
  - Upstream ownership aligned to `run_api_collection.py` and `scripts/H002_build_phase1_seller_history.py`.
  - A015 checks present for Phase 1 schema, contract types, and idempotency.
- Identified next step toward lock:
  - Run collection plus next scheduled A015 verification cycle and confirm clean proof bundle, then update status to `Locked v1.0`.

Files:
- out/process_guides/live_plan/phase_1_0_observation_schema.md
- scripts/A015_build_system_health_check.py
- scripts/H002_build_phase1_seller_history.py
- run_api_collection.py
- out/phase1_seller_history.csv
- out/listing_offer_seller_observation_history.csv
- out/system_health_checklist.csv
- out/B_cycle.log
- WORK_LOG.md

State:
- Evidence snapshot used (no ad-hoc A run):
  - out/phase1_seller_history.csv rows=179
  - phase1 global duplicate keys=0
  - out/listing_offer_seller_observation_history.csv rows=179
  - A015 latest snapshot includes `h_schema_phase1_seller_history=ok`, `h_phase1_contract_types=ok`, `h_phase1_history_idempotent=ok`
- Alert raised during review:
  - `order_master_blank_cogs_lvl1plus=warn` present in latest `out/system_health_checklist.csv`
- Suggested fix recorded:
  - investigate and clear blank COGS path, or move to explicit approved exception list if intentional.

Carryover:
- Confirm lock readiness on next scheduled collection+A015 cycle and update Phase 1.0 status to `Locked v1.0` only after clean proof.

Next:
- None
---
[2026-02-09 15:32 UTC]
Layer: B Cycle / Logging
Scope: Trim B cycle log to only the latest completed run and close ticket

Change:
- Cleaned `out/B_cycle.log` to keep only the most recent completed cycle block.
- Kept cycle id `2026-02-09T15:10:45Z` (the last block that reached `cycle sleep`).
- Removed older B cycle log history entries from this file.

Files:
- out/B_cycle.log
- WORK_LOG.md

State:
- B cycle lock remained active during trim (`out/B_cycle.lock` present), but log now contains only 24 lines for the last completed run.
- This supports easier read/debug without mid-cycle noise.

Carryover:
- None

Next:
- None
---
[2026-02-09 15:34 UTC]
Layer: Phase 1.0 Execution Evidence
Scope: Execute approved Phase 1.0 collection work and capture proof before lock decision

Change:
- Executed `python run_api_collection.py`.
- Collection completed successfully and rebuilt current observation artifacts.
- No code files changed in this step.

Files:
- run_api_collection.py
- out/listing_offer_seller_observation_history.csv
- out/phase1_seller_history.csv
- out/system_health_checklist.csv
- WORK_LOG.md

State:
- Runtime proof:
  - listing seller history rows=179
  - phase1 seller history rows=179
- Post-run integrity proof:
  - phase1 duplicate global keys=0
  - phase1 bad asof_date=0
  - phase1 bad seller_seen_flag=0
  - phase1 bad directional_bias=0
  - phase1 bad fulfilment_channel=0
  - seller observation duplicate keys=0
- Latest health snapshot is newer than this run, but includes active warning:
  - order_master_blank_cogs_lvl1plus=warn (value=1)

Carryover:
- Clear `order_master_blank_cogs_lvl1plus` warning, then finalize Phase 1.0 lock decision and status update.

Next:
- None
---
[2026-02-09 15:43 UTC]
Layer: B Cycle / Health Snapshot Logging
Scope: Add point-in-time A015 result snapshot into B cycle log

Change:
- Updated scripts/run_B_cycle.py to log a single-line JSON health_snapshot event after each end-of-cycle A015 run.
- Snapshot now records cycle_start_utc, health_snapshot_utc, ail, warn, ail_checks, and warn_checks.
- Added fallback log entry when health snapshot is missing or unreadable.

Files:
- scripts/run_B_cycle.py
- WORK_LOG.md

State:
- Validation run: python -m py_compile scripts/run_B_cycle.py (pass).
- No ad-hoc A scripts were run during this change.

Carryover:
- None

Next:
- Confirm next B cycle writes health_snapshot {...} line in out/B_cycle.log.
---
[2026-02-09 16:04 UTC]
Layer: B Cycle COGS Guard Hardening
Scope: Fix timing/race path that allowed qty>0 rows with zero COGS into Order_Master

Change:
- Updated `scripts/B004_build_order_master.py` to unify missing-token-COGS detection.
- Added `_missing_token_cogs_mask(df_master)` and wired all three guard stages to this shared rule.
- New rule marks rows as missing when qty>0 and either:
  - `COGS_ExVAT` is zero/blank in master, or
  - no positive `cogs_exvat` exists for that exact `Order ID+SKU` in token COGS ledger.
- This removes key-presence-only false passes during same-cycle timing windows.

Files:
- scripts/B004_build_order_master.py
- out/order_master.csv
- out/orders_missing_tokens.csv
- out/system_health_checklist.csv
- out/B_cycle.log
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/B004_build_order_master.py` passed.
- Live cycle evidence (no ad-hoc A run):
  - B cycle executed patched B004 successfully multiple times after change.
  - `out/order_master.csv` now has `blank_cogs_lvl1plus_now=0`.
  - Latest health snapshot: `out/system_health_checklist.csv` mtime `2026-02-09T16:03:13Z` with `warn_count=0` and `fail_count=0`.

Carryover:
- None

Next:
- Phase 1.0 close: update `out/process_guides/live_plan/phase_1_0_observation_schema.md` status to `Locked v1.0` and record lock proof.
---
[2026-02-09 16:09 UTC]
Layer: Phase 1.0 Governance
Scope: Lock Phase 1.0 and record completion evidence

Change:
- Updated `out/process_guides/live_plan/phase_1_0_observation_schema.md` status from draft to `Locked v1.0 (2026-02-09)`.
- Replaced "Next Execution Steps" with lock evidence tied to current cycle artifacts.
- Updated `out/process_guides/master_plan.md` to mark Phase 1 status complete and reference the lock document.

Files:
- out/process_guides/live_plan/phase_1_0_observation_schema.md
- out/process_guides/master_plan.md
- WORK_LOG.md

State:
- Evidence used from latest completed artifacts (no ad-hoc A run):
  - `out/B_cycle.log` contains `health_gate snapshot FAIL=0 WARN=0` at `2026-02-09T16:06:31Z`.
  - `out/system_health_checklist.csv` contains:
    - `h_schema_phase1_seller_history,ok,ok`
    - `h_phase1_contract_types,ok,0`
    - `h_phase1_history_idempotent,ok,0`
- Phase 1.0 lock criteria in guide now documented as satisfied with explicit proof.

Carryover:
- None

Next:
- None
---
[2026-02-10 13:10 UTC]
Layer: H Cycle / Head of Sales
Scope: Implement approved Phase 1 HOS output skeleton and run proof

Change:
- Added new script `scripts/H003_build_hos_guidelines_snapshot.py`.
- Script reads latest `out/listing_offer_snapshot_*.csv` and `out/sku_performance_summary.csv`.
- Joins on normalized SKU (strip + uppercase).
- Writes `out/hos_guidelines_snapshot_YYYY-MM-DD.csv` with required Phase 1 columns.
- Leaves Phase 2-4 fields blank by design (`min_price_gross`, `max_price_gross`, `posture`, `reason_codes`, `review_triggers`).
- Executed `python scripts/H003_build_hos_guidelines_snapshot.py` and captured proof output.

Files:
- scripts/H003_build_hos_guidelines_snapshot.py
- out/hos_guidelines_snapshot_2026-02-10.csv
- WORK_LOG.md

State:
- Proof lines from run:
  - created_file=out/hos_guidelines_snapshot_2026-02-10.csv
  - row_count=10
  - sample_rows printed=3
- Reconciliation proof:
  - listing snapshot rows=10
  - hos guidelines rows=10
- Output header check passed in `out/hos_guidelines_snapshot_2026-02-10.csv` with all required Phase 1 columns.
- Verification status recorded as pending next scheduled cycle (latest health snapshot predates code change).

Carryover:
- None

Next:
- Implement Phase 2 minimum price rule (10% ROI floor) in `scripts/H003_build_hos_guidelines_snapshot.py`.
---
[2026-02-10 13:33 UTC]
Layer: H Cycle / Head of Sales
Scope: Implement approved Phase 3 max price rule and sign off workbook

Change:
- Updated scripts/H003_build_hos_guidelines_snapshot.py to implement Phase 3 maximum price rule.
- Added max calculation max_price_gross = anchor_price * 1.15.
- Added fallback chain for anchor price: uy_box_price_used_gross -> buy_box_price_gross -> lowest_fba_price_gross -> our_price_gross.
- Added reason code uy_box_fallback_used when fallback source was used.
- Added investigate trigger missing_market_price when no anchor price exists.
- Updated output so uy_box_price_used_gross stores the actual anchor used for max calculations.
- Executed python scripts/H003_build_hos_guidelines_snapshot.py and captured proof output.

Files:
- scripts/H003_build_hos_guidelines_snapshot.py
- out/hos_guidelines_snapshot_2026-02-10.csv
- WORK_LOG.md

State:
- Validation run:
  - python -m py_compile scripts/H003_build_hos_guidelines_snapshot.py passed.
- Proof lines from run:
  - created_file=out/hos_guidelines_snapshot_2026-02-10.csv
  - row_count=10
- Reconciliation proof:
  - min_price_gross blank count=0
  - max_price_gross blank count=0
  - buy_box_fallback_used count=3
- Sample rows confirm fallback anchoring and max ceiling calculations.
- No Amazon price update endpoints called; flow is advisory output only.
- Verification status: pending next scheduled cycle check because latest health snapshot predates change.

Carryover:
- None

Next:
- Implement Phase 4 posture and review triggers in scripts/H003_build_hos_guidelines_snapshot.py.
---
[2026-02-10 13:34 UTC]
Layer: H Cycle / Head of Sales
Scope: Correction addendum for prior Phase 3 sign-off entry formatting

Change:
- Added this correction entry because the previous entry in this file contains formatting artifacts from shell escaping.
- Correct field names in the previous entry should read:
  - buy_box_price_used_gross
  - buy_box_fallback_used
- No code behavior changed by this addendum.

Files:
- WORK_LOG.md

State:
- Append-only correction recorded; prior entry remains unchanged as required.

Carryover:
- None

Next:
- Implement Phase 4 posture and review triggers in scripts/H003_build_hos_guidelines_snapshot.py.
---
[2026-02-10 13:38 UTC]
Layer: H Cycle / Head of Sales
Scope: Implement approved Phase 4 posture and review triggers, capture proof, and sign off workbook

Change:
- Updated `scripts/H003_build_hos_guidelines_snapshot.py` to implement Phase 4 posture rules:
  - investigate when `roi_at_buy_box_price_pct` is blank
  - step_back when `roi_at_buy_box_price_pct < 10`
  - compete otherwise
- Added Phase 4 review triggers:
  - `buy_box_below_floor` when `buy_box_price_used_gross < min_price_gross`
  - `buy_box_above_ceiling` when `buy_box_price_used_gross > max_price_gross`
  - `buy_box_missing` when buy box is missing
- Preserved advisory-only behavior (no price update endpoints, no sheet writes in this flow).
- Executed `python scripts/H003_build_hos_guidelines_snapshot.py` and captured proof output.

Files:
- scripts/H003_build_hos_guidelines_snapshot.py
- out/hos_guidelines_snapshot_2026-02-10.csv
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/H003_build_hos_guidelines_snapshot.py` passed.
- Required proof:
  - created_file=`out/hos_guidelines_snapshot_2026-02-10.csv`
  - listing_rows=10
  - hos_rows=10
  - row_match=True
  - posture_compete=5
  - posture_hold=0
  - posture_step_back=5
  - posture_investigate=0
  - buy_box_fallback_used_count=3
  - buy_box_missing_trigger_count=3
- Sample rows:
  - buy_box_present_sample sku=`6V-EEC1-2S9Z` posture=`compete`
  - fallback_sample sku=`AX-NKNU-29C1` reason_codes=`buy_box_fallback_used|buy_box_missing`
  - step_back_sample sku=`VF-3T0K-DR5O` posture=`step_back` review_triggers=`buy_box_below_floor`
- Active health alerts at latest snapshot:
  - `h_e_inputs_fresh` warn
  - `h_e_outputs_latest_asof` warn
  - `h_refund_adjustment_history_idempotent_today` warn
- Verification status: Pending next cycle check
- Changed at: 2026-02-10T13:37:06Z
- Latest health snapshot at: 2026-02-10T13:23:27Z
- Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-10 13:54 UTC]
Layer: H Cycle / Head of Sales
Scope: Execute Phase 5 test proof run (no code changes)

Change:
- Ran offer collection refresh via python scripts/H001_capture_offer_snapshot.py.
- Ran E cycle once and observed cadence skip; reran with E_ENFORCE_CADENCE=0 to complete Phase 5 proof refresh.
- Regenerated HOS snapshot via python scripts/H003_build_hos_guidelines_snapshot.py.
- Collected proof metrics from latest listing snapshot and HOS snapshot outputs.

Files:
- out/listing_offer_snapshot_2026-02-10.csv
- out/listing_offer_history.csv
- out/listing_offer_seller_snapshot_2026-02-10.csv
- out/listing_offer_seller_observation_history.csv
- out/phase1_seller_history.csv
- out/sku_sales_velocity.csv
- out/sku_roi_snapshot.csv
- out/sku_restock_signals.csv
- out/sku_performance_summary.csv
- out/e_study_report.csv
- out/hos_guidelines_snapshot_2026-02-10.csv
- out/api_call_log.jsonl
- out/system_health_checklist.csv
- WORK_LOG.md

State:
- Required Phase 5 proof:
  - created_file=out/hos_guidelines_snapshot_2026-02-10.csv
  - listing_rows=10
  - hos_rows=10
  - row_match=True
  - min_price_gross_filled_count=10
  - max_price_gross_filled_count=10
  - posture_filled_count=10
  - buy_box_fallback_used_count=3
  - posture_step_back_count=5
- Required sample rows captured:
  - buy_box_present sku=6V-EEC1-2S9Z posture=compete
  - fallback_used sku=AX-NKNU-29C1 reason_codes=buy_box_fallback_used|buy_box_missing
  - step_back sku=VF-3T0K-DR5O review_triggers=buy_box_below_floor
- Read-only flow proof:
  - api_call_log recent endpoints are GET-style reads only (listings_items_get_item, ba_inventory_get_summaries, products_pricing_get_item_offers, inances_get_financial_events)
  - update_like_endpoints=NONE
- Active health snapshot alerts at log time: fail_count=0, warn_count=4 (h_e_inputs_fresh, h_e_outputs_latest_asof, h_spapi_lock_present, h_refund_adjustment_history_idempotent_today).

Carryover:
- None

Next:
- If approved, sign off workbook for Phase 5 proof completion and open next ticket for WARN cleanup.
---
[2026-02-10 13:55 UTC]
Layer: H Cycle / Head of Sales
Scope: Ticket close - user approved Phase 5 proof and requested workbook sign-off

Change:
- Recorded user approval to sign off the workbook for Phase 5 proof completion.
- No code changes in this close step.

Files:
- WORK_LOG.md

State:
- Workbook sign-off: approved by user.
- Phase 5 proof artifacts remain in place for audit.
- Open alerts still present in latest health snapshot and require a separate cleanup ticket.

Carryover:
- None

Next:
- None
---
[2026-02-10 15:21 UTC]
Layer: H Cycle / Head of Sales
Scope: Phase 2 completion - Competition Data Capture daily market snapshot build

Change:
- Implemented Phase 2 builder script scripts/H004_build_daily_market_snapshot.py.
- Wired Phase 2 run into A cycle order in scripts/run_A_all.py after un_E_cycle.py.
- Executed python scripts/H004_build_daily_market_snapshot.py twice to prove idempotent append behavior.

Files:
- scripts/H004_build_daily_market_snapshot.py
- scripts/run_A_all.py
- out/hos_daily_market_snapshot_2026-02-10.csv
- out/hos_daily_market_history.csv
- WORK_LOG.md

State:
- Phase 2 proof metrics:
  - snapshot_rows=10
  - history_rows_after_run1=10
  - history_rows_after_run2=10
  - duplicate_key_rows=0
  - blank_buy_box_price_used_gross=0
  - buy_box_fallback_used_count=3
  - buy_box_missing_count=3
  - inferred_our_seller_id=AB5OM860MS57Z
- Health at completion:
  - latest_health_snapshot_utc=2026-02-10T15:17:16Z
  - fail_count=0
  - warn_count=0
- Workbook sign-off: approved by user.

Verification status: Pending next cycle check
Changed at: 2026-02-10T15:20:20Z
Latest health snapshot at: 2026-02-10T15:17:16Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
---
[2026-02-10 15:46 UTC]
Layer: H Cycle / Head of Sales
Scope: Phase 3 completion - daily market snapshot health checks

Change:
- Added Phase 3 health checks in scripts/A015_build_system_health_check.py for hos_daily_market_snapshot validation.
- Added checks for file existence, row count, required columns, null core fields, delivery parity binary values, and economics anchor completeness for training SKUs.
- No sheet writes and no pricing update logic added.

Files:
- scripts/A015_build_system_health_check.py
- WORK_LOG.md

State:
- Implementation proof:
  - py_compile_passed=True for scripts/A015_build_system_health_check.py
  - snapshot_path=out/hos_daily_market_snapshot_2026-02-10.csv
  - row_count=10
  - missing_required_cols=0
  - blank_buy_box_price_used_gross=0
  - blank_offer_count_fba=0
  - blank_offer_count_fbm=0
  - delivery_parity_invalid=0
  - training_rows_in_snapshot=10
  - training_blank_break_even_exvat_gbp=0
  - training_blank_break_even_gross_gbp=0
  - training_blank_token_cost_exvat_gbp=0
  - training_blank_min_price_gross_10pct=0
  - training_blank_max_price_gross_current=0
- Health at approval log time:
  - latest_health_snapshot_utc=2026-02-10T15:31:45Z
  - fail_count=0
  - warn_count=0
- Workbook sign-off: approved by user.

Verification status: Pending next cycle check
Changed at: 2026-02-10T15:32:17Z
Latest health snapshot at: 2026-02-10T15:31:45Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
[2026-02-10 15:57 UTC]
Layer: H Cycle / Head of Sales
Scope: Phase 4 completion - daily market reports (HTML + PDF + charts) and workbook sign-off

Change:
- Added `scripts/H005_build_daily_market_reports.py` to generate daily market reports from `hos_daily_market_snapshot` and `hos_daily_market_history`.
- Output now includes:
- `out/reports/hos_daily/hos_daily_report_YYYY-MM-DD.html`
- `out/reports/hos_daily/hos_daily_report_YYYY-MM-DD.pdf`
- `out/reports/hos_daily/hos_daily_report_index_YYYY-MM-DD.csv`
- per-SKU chart files in `out/reports/hos_daily/charts`
- Wired Phase 4 into A cycle run order in `scripts/run_A_all.py` after `H004_build_daily_market_snapshot.py`.
- Added Phase 4 health checks in `scripts/A015_build_system_health_check.py`:
- `h_market_report_html_exists`
- `h_market_report_pdf_exists`
- `h_market_report_price_charts_count`
- `h_market_report_seller_mix_charts_count`
- Workbook sign-off approved by user.

Files:
- scripts/H005_build_daily_market_reports.py
- scripts/run_A_all.py
- scripts/A015_build_system_health_check.py
- out/reports/hos_daily/hos_daily_report_2026-02-10.html
- out/reports/hos_daily/hos_daily_report_2026-02-10.pdf
- out/reports/hos_daily/hos_daily_report_index_2026-02-10.csv
- out/reports/hos_daily/charts/2026-02-10_*.png
- out/system_health_checklist.csv
- WORK_LOG.md

State:
- Validation run:
- `python -m py_compile scripts/H005_build_daily_market_reports.py` passed
- `python -m py_compile scripts/run_A_all.py` passed
- `python -m py_compile scripts/A015_build_system_health_check.py` passed
- Report generation proof:
- `python scripts/H005_build_daily_market_reports.py` completed
- snapshot_rows=10
- unique_skus=10
- price_chart_count=10
- seller_mix_chart_count=10
- Artifact proof:
- html exists: `out/reports/hos_daily/hos_daily_report_2026-02-10.html`
- pdf exists: `out/reports/hos_daily/hos_daily_report_2026-02-10.pdf`
- index exists: `out/reports/hos_daily/hos_daily_report_index_2026-02-10.csv`
- chart_file_count=20
- Health verification:
- latest_health_snapshot_utc=2026-02-10T15:56:49Z
- fail_count=0
- warn_count=0
- new Phase 4 checks present and all `ok`

Verification status: Verified by latest cycle check
Changed at: 2026-02-10T15:51:36Z
Latest health snapshot at: 2026-02-10T15:56:49Z
Next verifier: not required (already verified)

Carryover:
- None

Next:
- None
---
[2026-02-11 09:37 UTC]
Layer: B Cycle Reliability
Scope: Restore B ownership to Task Scheduler and add post-A self-heal for stale B lock/process

Change:
- Updated scripts/run_A_all.py to self-heal B after A completes:
- new env switch A_ENSURE_B_AFTER_A (default 1)
- if B is not running, clear stale out/B_cycle.lock and start scripts/run_B_cycle.py
- Updated out/process_guides/b_cycle_runbook.md with the self-heal behavior.
- Switched active B process back to Task Scheduler control:
- stopped manual un_B_cycle.py pid 21684
- started scheduled task \AMZ Orders

Files:
- scripts/run_A_all.py
- out/process_guides/b_cycle_runbook.md
- WORK_LOG.md

State:
- Validation run:
- python -m py_compile scripts/run_A_all.py passed
- Task Scheduler handoff proof:
- \AMZ Orders status: Running
- new lock owner: B|pid=6840|start=2026-02-11T09:36:25Z
- out/B_cycle.log advanced with new cycle start at 2026-02-11T09:36:25Z
- alert snapshot remains WARN (latest known): h_e_outputs_latest_asof

Verification status: Pending next cycle check
Changed at: 2026-02-11T09:32:38Z
Latest health snapshot at: 2026-02-11T06:24:09Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 11:54 UTC]
Layer: Agent Policy
Scope: Add automatic repeated-alert snooze protocol to AGENTS instructions

Change:
- Updated AGENTS.md Alerts and proactive fixes to require proactive snooze handling for known repeated alerts while waiting for later cycle/time window.
- Added requirement to include concrete snooze command using scripts/one_off/H001_set_health_alert_snooze.py with absolute UTC time and reason.
- Added requirement to keep underlying FAIL/WARN reporting visible and confirm snooze status when user asks to apply snooze.

Files:
- AGENTS.md

State:
- Policy update only; no pipeline script execution required.

Verification status: Pending next cycle check
Changed at: 2026-02-11T11:54:47Z
Latest health snapshot at: 2026-02-11T11:42:33Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 11:55 UTC]
Layer: Agent Policy
Scope: Require explicit user sign-off before applying alert snooze

Change:
- Updated AGENTS.md repeated-alert snooze protocol.
- Added rule: Codex must never apply snooze automatically; explicit user sign-off is required before running snooze set or clear commands.

Files:
- AGENTS.md

State:
- Policy update only; no pipeline script execution required.

Verification status: Pending next cycle check
Changed at: 2026-02-11T11:55:27Z
Latest health snapshot at: 2026-02-11T11:42:33Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 15:21 UTC]
Layer: E Cycle Reliability
Scope: Fix stale E output freshness cadence gate (h_e_outputs_latest_asof) and verify clear

Change:
- Updated scripts/run_E_cycle.py cadence logic to allow one successful E run per new UTC date, even when strict elapsed 24h has not fully passed.
- Preserved cadence protection for repeated same-date runs.
- Regenerated E outputs through python scripts/run_E_cycle.py.

Files:
- scripts/run_E_cycle.py
- out/sku_sales_velocity.csv
- out/sku_roi_snapshot.csv
- out/sku_restock_signals.csv
- out/sku_performance_summary.csv
- out/e_study_report.csv
- out/e_run_log.jsonl
- out/system_health_checklist.csv
- out/B_cycle.log
- WORK_LOG.md

State:
- Root cause confirmed: elapsed-24h cadence gate blocked next-day morning E run when previous success was later in prior day.
- Validation run: python -m py_compile scripts/run_E_cycle.py passed.
- Execution run: python scripts/run_E_cycle.py completed successfully and wrote fresh outputs.
- Before/after proof:
  - before: E outputs asof_date=2026-02-10 and health check h_e_outputs_latest_asof=warn.
  - after: all E outputs asof_date=2026-02-11 (sku_sales_velocity=405 rows, sku_roi_snapshot=64 rows, sku_restock_signals=135 rows, sku_performance_summary=135 rows, e_study_report=135 rows).
- Health reconciliation:
  - scheduled B-cycle A015 snapshot at 2026-02-11T15:19:49Z recorded ail=0, warn=0.
  - h_e_outputs_latest_asof is now ok with alue=0.

Verification status: Verified by latest cycle check
Changed at: 2026-02-11T15:17:31Z
Latest health snapshot at: 2026-02-11T15:19:49Z
Next verifier: not required (already verified)

Carryover:
- None

Next:
- None
---
[2026-02-11 15:51 UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 lab cohort lock-in (official pilot SKU) and health guard

Change:
- Added canonical lab cohort config `config/h_lab_cohort.csv` with the official Phase 0 pilot SKU `JB-RGB6-LZOJ` as active.
- Added loader helper `scripts/h_lab_cohort.py` with:
  - `load_lab_cohort()` for schema-safe reads
  - `load_active_lab_skus()` for enabled SKU list
- Updated `scripts/A015_build_system_health_check.py` to enforce:
  - `h_schema_lab_cohort` (required file + required columns)
  - `h_lab_cohort_active_rows` (at least one enabled SKU)

Files:
- config/h_lab_cohort.csv
- scripts/h_lab_cohort.py
- scripts/A015_build_system_health_check.py
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/h_lab_cohort.py scripts/A015_build_system_health_check.py` passed.
- Proof:
  - lab_cohort_rows=1
  - active_rows=1
  - unique_skus=1
  - active_lab_skus=JB-RGB6-LZOJ
- Health proof from latest completed cycle artifacts:
  - `out/system_health_checklist.csv` contains:
    - `h_schema_lab_cohort,ok,ok`
    - `h_lab_cohort_active_rows,ok,1`
  - latest `out/B_cycle.log` health snapshot at `2026-02-11T15:50:59Z` shows `fail=0`, `warn=0`.

Verification status: Verified by latest cycle check
Changed at: 2026-02-11T15:43:13Z
Latest health snapshot at: 2026-02-11T15:50:59Z
Next verifier: not required (already verified)

Carryover:
- None

Next:
- None
---

[2026-02-11 16:01 UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 next step - Head boundary template fields for official pilot SKU

Change:
- Added canonical Head boundary config file `config/h_head_boundaries.csv`.
- Added loader helper `scripts/h_head_boundaries.py` with:
  - `load_head_boundaries()` for schema-safe reads
  - `load_active_head_boundary_skus()` for enabled SKU list
- Updated `scripts/A015_build_system_health_check.py` to enforce:
  - `h_schema_head_boundaries` (required file + required columns)
  - `h_head_boundaries_active_rows` (at least one enabled boundary row)
  - `h_head_boundary_pilot_present` (official pilot SKU present and enabled)
  - `h_head_boundaries_numeric_valid` (ceiling/floor and guardrail numeric logic)

Files:
- config/h_head_boundaries.csv
- scripts/h_head_boundaries.py
- scripts/A015_build_system_health_check.py
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/h_head_boundaries.py scripts/A015_build_system_health_check.py` passed.
- Proof:
  - boundary_rows=1
  - active_rows=1
  - unique_skus=1
  - pilot_present=1
  - missing_required_cols=0
  - active_numeric_invalid_count=0
  - active_lab_sku=JB-RGB6-LZOJ
- Health evidence from latest completed artifacts:
  - `out/system_health_checklist.csv` fail_count=0, warn_count=0
  - `out/health_status.csv` latest status=OK at `2026-02-11T15:50:58.490754+00:00`

Verification status: Pending next cycle check
Changed at: 2026-02-11T16:00:29Z
Latest health snapshot at: 2026-02-11T15:50:58.490754+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 16:08 UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 next step completion - Supervisor tactical decision table for official pilot SKU

Change:
- Added canonical Supervisor tactical rule config `config/h_supervisor_tactical_rules.csv` for pilot SKU `JB-RGB6-LZOJ`.
- Added loader helper `scripts/h_supervisor_tactical_rules.py` with:
  - `load_supervisor_tactical_rules()` for schema-safe reads
  - `load_active_supervisor_tactical_rules()` for enabled rule subset
- Updated `scripts/A015_build_system_health_check.py` to enforce:
  - `h_schema_supervisor_tactical_rules` (required file + required columns)
  - `h_supervisor_tactical_active_rows` (at least one enabled tactical rule)
  - `h_supervisor_tactical_pilot_coverage` (official pilot SKU has active tactical coverage)
  - `h_supervisor_tactical_rules_valid` (state/probe enums and numeric guardrails valid)

Files:
- config/h_supervisor_tactical_rules.csv
- scripts/h_supervisor_tactical_rules.py
- scripts/A015_build_system_health_check.py
- WORK_LOG.md

State:
- Validation run:
  - `python -m py_compile scripts/h_supervisor_tactical_rules.py scripts/A015_build_system_health_check.py` passed.
- Proof:
  - rule_rows=4
  - active_rows=4
  - unique_skus=1
  - pilot_rows=4
  - states=aggressor_candidate|follower|stable|unknown
  - probe_types=hold|lower|match|raise
  - missing_required_cols=0
  - active_invalid_rule_rows=0
- Health evidence source used:
  - latest health snapshot timestamp from artifacts=`2026-02-11T15:50:58.490754+00:00`

Verification status: Pending next cycle check
Changed at: 2026-02-11T16:08:03Z
Latest health snapshot at: 2026-02-11T15:50:58.490754+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 16:17 UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 next step completion - Worker probe event/response schema and health guard

Change:
- Added canonical worker probe log module `scripts/h_probe_logs.py`.
- Defined required schema and idempotent append behavior for:
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- Added seed script `scripts/H006_seed_worker_probe_logs.py` to generate one pilot probe event and response windows for official SKU `JB-RGB6-LZOJ`.
- Updated `scripts/A015_build_system_health_check.py` to enforce:
- `h_schema_worker_probe_event_log`
- `h_schema_worker_probe_response_log`
- `h_worker_probe_event_idempotent`
- `h_worker_probe_event_numeric_valid`
- `h_worker_probe_response_idempotent`
- `h_worker_probe_response_types_valid`

Files:
- scripts/h_probe_logs.py
- scripts/H006_seed_worker_probe_logs.py
- scripts/A015_build_system_health_check.py
- out/h_worker_probe_event_log.csv
- out/h_worker_probe_response_log.csv
- WORK_LOG.md

State:
- Validation run:
- `python -m py_compile scripts/h_probe_logs.py scripts/H006_seed_worker_probe_logs.py scripts/A015_build_system_health_check.py` passed.
- Seed run:
- `python scripts/H006_seed_worker_probe_logs.py` completed.
- Proof:
- event_rows_total=1
- response_rows_total=4
- response_windows_for_seed_event=5|15|60|240
- event_duplicate_probe_event_id=0
- response_duplicate_keys=0
- event_missing_required_cols=0
- response_missing_required_cols=0
- event_guardrail_invalid_rows=0
- response_flag_direction_conflicts=0
- idempotent_reappend_proof: event_rows_before_after=1_to_1, response_rows_before_after=4_to_4
- Health evidence from latest completed cycle artifacts:
- latest_health_snapshot_utc=2026-02-11T16:15:45Z
- fail_count=0
- warn_count=0
- new probe checks all `ok` in `out/system_health_checklist.csv`

Verification status: Verified by latest cycle check
Changed at: 2026-02-11T16:14:23Z
Latest health snapshot at: 2026-02-11T16:15:45Z
Next verifier: not required (already verified)

Carryover:
- None

Next:
- None
---
[ UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 next step completion - start Safe Mode on official pilot SKU only

Change:
- Added scripts/H007_run_safe_mode_pilot.py to execute Phase 0 Safe Mode for the active pilot SKU only (JB-RGB6-LZOJ).
- Enforced Safe Mode guardrails at decision stage: pilot-only scope, allowed actions (hold/match), cooldown, hard floor, ceiling, max move, and max daily down protection.
- Wired Safe Mode run into A cycle order in scripts/run_A_all.py after H004_build_daily_market_snapshot.py.
- Added Safe Mode health checks in scripts/A015_build_system_health_check.py:
- h_safe_mode_pilot_event_present
- h_safe_mode_pilot_scope_pilot_only
- h_safe_mode_pilot_actions_allowed

Files:
- scripts/H007_run_safe_mode_pilot.py
- scripts/run_A_all.py
- scripts/A015_build_system_health_check.py
- out/h_worker_probe_event_log.csv
- out/h_worker_probe_response_log.csv
- WORK_LOG.md

State:
- Validation run:
- python -m py_compile scripts/H007_run_safe_mode_pilot.py scripts/run_A_all.py scripts/A015_build_system_health_check.py passed.
- Execution proof:
- python scripts/H007_run_safe_mode_pilot.py run twice.
- Safe Mode event created:
- probe_event_id=safe_mode_JB-RGB6-LZOJ_20260211
- sku=JB-RGB6-LZOJ
- probe_type=hold
- ction_price_before_gbp=9.99
- ction_price_target_gbp=9.99
- Reconciliation and idempotency:
- event_rows_total before/after runs=1 -> 2 -> 2
- response_rows_total before/after runs=4 -> 8 -> 8
- safe_mode_event_rows_pilot=1
- safe_mode_event_rows_non_pilot= 
- safe_mode_bad_probe_rows= 
- duplicate_probe_event_id_rows= 
- duplicate_probe_response_keys= 
- Boundary proof:
- boundary_breach_floor= 
- boundary_breach_ceiling= 
- boundary_breach_max_move= 
- safe_mode_total_down_move_gbp= 
- Health evidence source:
- latest completed cycle snapshot in out/B_cycle.log at 2026-02-11T16:22:20Z shows ail=0, warn=0.

Verification status: Pending next cycle check
Changed at: 
Latest health snapshot at: 2026-02-11T16:22:20Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 16:27 UTC]
Layer: H Cycle / Repricing Manager Stack
Scope: Phase 0 next step completion - start Safe Mode on official pilot SKU only

Change:
- Added scripts/H007_run_safe_mode_pilot.py to execute Phase 0 Safe Mode for the active pilot SKU only (JB-RGB6-LZOJ).
- Enforced Safe Mode guardrails at decision stage: pilot-only scope, allowed actions (hold/match), cooldown, hard floor, ceiling, max move, and max daily down protection.
- Wired Safe Mode run into A cycle order in scripts/run_A_all.py after H004_build_daily_market_snapshot.py.
- Added Safe Mode health checks in scripts/A015_build_system_health_check.py:
- h_safe_mode_pilot_event_present
- h_safe_mode_pilot_scope_pilot_only
- h_safe_mode_pilot_actions_allowed

Files:
- scripts/H007_run_safe_mode_pilot.py
- scripts/run_A_all.py
- scripts/A015_build_system_health_check.py
- out/h_worker_probe_event_log.csv
- out/h_worker_probe_response_log.csv
- WORK_LOG.md

State:
- Validation run:
- python -m py_compile scripts/H007_run_safe_mode_pilot.py scripts/run_A_all.py scripts/A015_build_system_health_check.py passed.
- Execution proof:
- python scripts/H007_run_safe_mode_pilot.py run twice.
- Safe Mode event created:
- probe_event_id=safe_mode_JB-RGB6-LZOJ_20260211
- sku=JB-RGB6-LZOJ
- probe_type=hold
- ction_price_before_gbp=9.99
- ction_price_target_gbp=9.99
- Reconciliation and idempotency:
- event_rows_total before/after runs=1 -> 2 -> 2
- response_rows_total before/after runs=4 -> 8 -> 8
- safe_mode_event_rows_pilot=1
- safe_mode_event_rows_non_pilot= 
- safe_mode_bad_probe_rows= 
- duplicate_probe_event_id_rows= 
- duplicate_probe_response_keys= 
- Boundary proof:
- boundary_breach_floor= 
- boundary_breach_ceiling= 
- boundary_breach_max_move= 
- safe_mode_total_down_move_gbp= 
- Health evidence source:
- latest completed cycle snapshot in out/B_cycle.log at 2026-02-11T16:22:20Z shows ail=0, warn=0.

Verification status: Pending next cycle check
Changed at: 2026-02-11T16:27:03Z
Latest health snapshot at: 2026-02-11T16:22:20Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-11 16:27 UTC] Correction: The immediately prior malformed partial sign-off block (blank Changed at and encoding artifacts) is superseded by the full timestamped sign-off entry above this correction. No historical entries were edited or removed.
---
[2026-02-12 15:05 UTC] Ticket: Masterplan v3.1 documentation audit cleanup

Scope:
- Validate whether v3.1 improved on v2 and v3 without losing logic.
- Apply approved documentation cleanup only.

Changes made:
- Updated out/process_guides/repricing_tool/master plans/masterplan v3.1.md.
- Fixed subsection numbering in Learning Integrity:
- 11.1 -> 13.1
- 11.2 -> 13.2
- Added "Quick logic mapping (v2/v3 -> v3.1)" table for audit traceability.

Validation:
- Verified mapping table and numbering with g.
- No runtime scripts executed (documentation-only change).

Carryover:
- None

Next:
- None
---
[2026-02-12 15:05 UTC] Correction: In the immediately prior entry, validation line text wrapped incorrectly; intended command reference is rg.
---
[2026-02-12 16:13 UTC] Ticket: Masterplan v5.1 DVE observability restoration

Scope:
- Restore missing DVE observability fields identified in v5.1 vs v4.
- Keep strategy and pressure-state logic unchanged.

Changes made:
- Updated out/process_guides/repricing_tool/master plans/masterplan v5.1.md.
- Added section 7.5 DVE outputs (must be logged per cycle).
- Restored explicit fields:
- max_delivery_days
- delivery_penalty_unknown_flag

Validation:
- Confirmed section exists via g at line 365.
- Confirmed max_delivery_days exists at line 368.
- Confirmed delivery_penalty_unknown_flag exists at line 377.
- No runtime scripts executed (documentation-only change).

Verification status: Not applicable (documentation-only change)

Carryover:
- None

Next:
- None
---
[2026-02-13 09:48 UTC] Ticket: v9 patch parity sync into masterplan v9

Scope:
- Bring missing v9 patch framing text from ideas file into canonical masterplan v9.
- Keep all technical sections (19-23) unchanged.

Changes made:
- Updated out/process_guides/repricing_tool/master plans/masterplan v9.md.
- Added preface block before section 19:
- "Below is a v9 Patch..."
- structural gaps list (single writer, share/units, variant fallback, OAS hash tightening)
- Added closing optional next-step lines after final assessment.

Validation:
- Re-ran line comparison of:
- out/process_guides/repricing_tool/Ideas to be incorperated/v9 patches.md
- out/process_guides/repricing_tool/master plans/masterplan v9.md
- Remaining differences are only intentional version labels (v8.1 in source patch phrasing vs v9 in canonical masterplan).
- No runtime scripts executed (documentation-only change).

Verification status: Not applicable (documentation-only change)

Carryover:
- None

Next:
- None
---
[2026-02-13 11:27 UTC] Ticket: Phase 1 Task 1 storage adapter + unit tests

Scope:
- Implement Task 1 for Phase 1 storage adapter in scripts only.
- Include CSV atomic writes, append-only tables, upserts for memory/dimensions, and read helpers.
- Exclude pricing logic.

Changes made:
- Updated scripts/phase1_storage.py.
- Added explicit table behavior configuration:
- APPEND_ONLY_TABLES
- UPSERT_TABLE_KEYS
- Added adapter write entrypoint:
- write_table(table, rows)
- Added read helpers:
- read_where(table, where)
- read_by_keys(table, key_values)
- Enforced append-only gate in append(table, rows) so non-append-only tables are rejected.
- Added tests/test_phase1_storage.py with focused unit tests for Task 1 behavior.

Validation:
- Ran: python -m unittest tests.test_phase1_storage -v
- Result: Ran 6 tests in 0.086s
- Result: OK
- Test coverage in this run includes:
- atomic write replacement behavior and temp-file cleanup
- append-only behavior
- upsert behavior for offer_variants and variant_delta_memory
- read helper behavior (read_latest/read_where/read_by_keys)
- rejection path for invalid append target

Alert observed from latest saved health artifacts:
- FAIL: l1_keys_missing_in_master=2
- WARN: b_cycle_recent_fail_lines=8
- Snapshot timestamp: 2026-02-13T11:00:14.995473+00:00

Verification status: Pending next cycle check
Changed at: 2026-02-13T11:27:25Z
Latest health snapshot at: 2026-02-13T11:00:14.995473+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-13 11:35 UTC] Ticket: Phase 1 Task 2 market snapshot processor

Scope:
- Implement Task 2 in phased execution plan: market snapshot processor.
- Deliver adapter for getCompetitiveSummary, normalized offer rows, and variant mapping consistency.

Changes made:
- Added scripts/phase1_market_snapshot_processor.py.
- Added tests/test_phase1_market_snapshot_processor.py.
- Marked Task 2 as DONE in out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md with completion proof.

Validation:
- Ran: python -m unittest tests.test_phase1_market_snapshot_processor -v
- Result: Ran 3 tests in 0.001s
- Result: OK
- Regression check: python -m unittest tests.test_phase1_storage -v
- Result: Ran 6 tests in 0.080s
- Result: OK
- Runtime proof:
- rows=2
- winner=sellera, featured_offer_price_gbp=11.00, unknown_featured_outcome=False
- unique_snapshot_ids=True
- deterministic variant IDs generated per structural key

Alert observed from latest saved health artifacts:
- FAIL: l1_keys_missing_in_master=2
- WARN: b_cycle_recent_fail_lines=8
- WARN: h_e_outputs_latest_asof=5
- Snapshot timestamp: 2026-02-13T11:33:10.801202+00:00

Verification status: Pending next cycle check
Changed at: 2026-02-13T11:31:27Z
Latest health snapshot at: 2026-02-13T11:33:10.801202+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-13 12:26 UTC] Ticket: Phase 1 Task 3 DVE layer

Scope:
- Complete Task 3 in phased execution plan: effective price calc, delivery penalty, penalty curve v0.
- Mark task as DONE and record completion proof after explicit user approval.

Changes made:
- Added scripts/phase1_dve.py.
- Added tests/test_phase1_dve.py.
- Marked Task 3 as DONE in out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md with completion proof.

Validation:
- Ran: python -m unittest tests.test_phase1_dve -v
- Result: Ran 3 tests in 0.001s
- Result: OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve -v
- Result: Ran 12 tests in 0.073s
- Result: OK
- Expected-value proof:
- gap 0 -> penalty 0.00
- gap 1 -> penalty 0.15
- gap 2 -> penalty 0.30
- gap 3 -> penalty 0.45
- gap 4+ -> penalty 0.60

Alert observed from latest saved health artifacts:
- FAIL: l1_keys_missing_in_master
- WARN: b_cycle_recent_fail_lines
- WARN: h_e_outputs_latest_asof
- Snapshot timestamp: 2026-02-13T12:01:36Z

Verification status: Pending next cycle check
Changed at: 2026-02-13T12:07:10Z
Latest health snapshot at: 2026-02-13T12:01:36Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-13 12:59 UTC]
Ticket: Phase 1 Task 5 probe engine completion and execution-plan sign-off

Scope:
- Complete Task 5 in phased execution plan: state machine transitions, best rival definition, bracket logic, and delta memory.
- Mark Task 5 as DONE after explicit user approval.

Changes made:
- Added scripts/phase1_probe_engine.py.
- Added tests/test_phase1_probe_engine.py.
- Marked Task 5 as DONE in out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md with completion proof.

Validation:
- Ran: python -m unittest tests.test_phase1_probe_engine -v
- Result: Ran 4 tests in 0.001s
- Result: OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine -v
- Result: Ran 23 tests in 0.080s
- Result: OK
- Expected-value proof:
- best rival selection excludes our offer and selects minimum rival effective price
- transition outcomes verified: REGAIN, RAISE_FIND_LOSS, BRACKET_NARROW, STABLE_WIN, HOLD_OBSERVE
- bracket midpoint verified: best_rival=10.10 with bounds -0.04 to 0.10 gives target=10.13
- delta memory verified: WIN -0.05 then LOSS 0.08 gives learned_delta=0.02 and valid_test_count=2

Alert observed from latest saved health artifacts:
- FAIL seen in recent cycle: l1_keys_missing_in_master
- WARN active: b_cycle_recent_fail_lines
- WARN active: h_e_outputs_latest_asof
- Latest health snapshot timestamp: 2026-02-13T12:58:15Z

Verification status: Pending next cycle check
Changed at: 2026-02-13T12:59:47Z
Latest health snapshot at: 2026-02-13T12:58:15Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-13 13:19 UTC]
Ticket: Phase 1 Task 8 main loop wiring completion and execution-plan sign-off

Scope:
- Complete Task 8 in phased execution plan: tie A-cycle + H-cycle + logging with a running script and clear input/output contracts.
- Mark Task 8 as DONE after explicit user approval.

Changes made:
- Added scripts/phase1_main_loop.py.
- Added tests/test_phase1_main_loop.py.
- Marked Task 8 as DONE in out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md with completion proof.

Validation:
- Ran: python -m unittest tests.test_phase1_main_loop -v
- Result: Ran 4 tests in 0.165s
- Result: OK
- Ran: python scripts/phase1_main_loop.py --demo
- Result: JSON output returned for A-cycle and H-cycle with state/write/ceiling/reason_codes fields.
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine tests.test_phase1_write_verify tests.test_phase1_oas tests.test_phase1_main_loop -v
- Result: Ran 38 tests in 0.233s
- Result: OK
- Contract proof:
- A-cycle persists sku_daily_intel with non-empty eligibility_source.
- H-cycle enforces writer lock and logs WRITER_LOCK_BLOCK.
- H-cycle writes snapshot rows, variant upserts, ceiling events, and execution log entries.
- Probe close writes oas_log and updates variant_delta_memory.

Alert observed from latest saved health artifacts:
- WARN: b_cycle_recent_fail_lines=4
- WARN: h_e_outputs_latest_asof=5
- Latest health snapshot timestamp: 2026-02-13T13:03:56Z

Verification status: Pending next cycle check
Changed at: 2026-02-13T13:19:00Z
Latest health snapshot at: 2026-02-13T13:03:56Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-14 13:22 UTC]
Ticket: H-cycle suppression blocker gate MVP (buy box/outcome/we-present hold)

Scope:
- Implement minimum viable suppression blocker in H executioner path so suppression/unknown outcome states are harmless.
- Enforce HOLD behavior: no price writes, no seller-delta learning updates, one suppression log line.

Changes made:
- Updated `scripts/run_H_pricing_cycle.py` snapshot build in `_refresh_listing_snapshot(...)` to write blocker fields:
- `buy_box_present_flag` = 1 when `buy_box_price` exists else 0
- `outcome_known_flag` = 1 when buy box exists else 0 (MVP placeholder)
- `we_present_flag` = 1 when `our_price` exists else 0
- Updated `_run_executioner(...)` to compute HOLD blocker after reading prices:
- HOLD when buy box missing/present flag false
- HOLD when outcome_known_flag != 1
- HOLD when we_present_flag != 1
- On HOLD, force `probe_type=hold`, `target_price=before_price`, `should_write=False`, and add `SUPPRESSION_OR_UNKNOWN_OUTCOME` reason code.
- Added dedicated suppression log line with required key fields:
- `reason=SUPPRESSION_OR_UNKNOWN_OUTCOME`, `sku`, `asin`, `buy_box_present`, `buy_box_price`, `outcome_known`, `we_present`, `event_utc`
- Blocked seller delta learning update by wrapping update block with `if not hold_blocker:`.

Validation:
- Ran forced HOLD verification with stubbed local executioner call and snapshot row with missing buy box.
- Evidence:
- `executioner_live_write_attempted=0`
- `action_log_live_write_attempted=0`
- `learning_updates_count=0` (no seller delta upsert)
- `blocker_log_count=1`
- blocker log text contains `reason=SUPPRESSION_OR_UNKNOWN_OUTCOME` and required key fields.

Alert observed from latest saved health artifacts:
- FAIL active: `h_spapi_lock_present`
- WARN active: `h_listing_offer_history_idempotent_today`, `h_listing_offer_seller_history_idempotent_today` (plus additional WARN in latest status)
- Health alert snooze set active until `2026-02-14T23:59:00Z`

Verification status: Pending next cycle check
Changed at: 2026-02-14T13:22:03Z
Latest health snapshot at: 2026-02-14T13:21:15.792478+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-14 13:26 UTC]
Ticket: Add pricing_writer_mode dry_run/live switch for H-cycle validation under suppression

Scope:
- Add writer mode switch so engine can compute and log intended actions without writing in dry-run mode.
- Keep invalid mode lock behavior explicit.

Changes made:
- Updated `scripts/phase1_main_loop.py`:
- `pricing_writer_mode` normalized to `dry_run` or `live` (legacy `CODEX_H` mapped to `live` for compatibility).
- Invalid mode returns `WRITER_LOCK_BLOCK` with message `writer mode must be dry_run or live`.
- Added dry-run branch: when action is required, set `write_status=DRY_RUN_NO_WRITE`, log intended action in `write_error`, and never submit write.
- Added dry-run reason codes: `DRY_RUN_MODE`, `DRY_RUN_MODE_NO_WRITE`.
- Updated `scripts/H110_run_phase1_h_pilot.py`:
- Config default for `pricing_writer_mode` set to `dry_run`.
- Accept only `dry_run` or `live` (legacy `codex_h` mapped to `live`).
- Effective live writes now require mode `live` plus existing live gates.
- Updated `tests/test_phase1_main_loop.py`:
- Migrated existing `CODEX_H` mode tests to `live`.
- Added `test_h_cycle_dry_run_logs_intended_action_without_write` to prove dry-run computes/logs action and submits no write.

Validation:
- Ran: `python -m unittest tests.test_phase1_main_loop -v`
- Result: Ran 7 tests in 0.255s
- Result: OK
- Dry-run proof from test:
- write submitter call count = 0
- `write_status=DRY_RUN_NO_WRITE`
- execution log contains intended action text in `write_error`

Alert observed from latest saved health artifacts:
- Active FAIL/WARN remain in latest health status.
- Health alert snooze remains active until `2026-02-14T23:59:00Z` (suppresses repeated toast interruption only).

Verification status: Pending next cycle check
Changed at: 2026-02-14T13:26:15Z
Latest health snapshot at: 2026-02-14T13:24:32.845608+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-14 14:30 UTC]
Ticket: Phase1 multi-SKU safety completion (hard observability gate + decision log contract + live allowlist)

Scope:
- Enforce hard observability gate in Phase1 loop for multi-SKU mode.
- Extend decision log schema to explicit hold reasons and writer mode.
- Add config-driven per-SKU live override while global dry-run stays default.

Changes made:
- Updated `scripts/phase1_main_loop.py`:
- Added `we_present` detection per SKU.
- Added strict observable gate: if not observable then `write_status=OBSERVABILITY_BLOCK_NO_WRITE`, `SUPPRESSION_OR_UNKNOWN_OUTCOME`, no write call.
- Added NO_LEARN behavior on unobservable cycles by skipping `variant_delta_memory` update.
- Extended decision log payload with `ts_utc`, `sku_or_asin`, `we_present`, `hold_reason`, `writer_mode`.
- Updated `scripts/phase1_storage.py`:
- Extended `decision_log` schema with new contract columns.
- Updated `scripts/H110_run_phase1_h_pilot.py`:
- Added `live_sku_allowlist` support in multi-SKU loop.
- Global mode can remain `dry_run`; SKUs in `live_sku_allowlist` are promoted to live mode per SKU.
- Effective live write now allows per-SKU override (`cfg enabled_live_writes` OR allowlist).
- Updated `config/pilot_sku.yaml`:
- Added `live_sku_allowlist` key (empty default).
- Updated tests in `tests/test_phase1_main_loop.py`:
- Added assertions for new decision log fields.
- Added `test_h_cycle_unobservable_blocks_live_write`.

Validation:
- Ran: `python -m unittest tests.test_phase1_main_loop -v`
- Result: Ran 9 tests in 0.398s
- Result: OK
- Ran: `python scripts/H110_run_phase1_h_pilot.py --phase1-config config/pilot_sku.yaml --read-only --now-utc 2026-02-14T14:45:00Z`
- Result: processed 10 SKUs, dry-run actioning logged.
- Decision log proof (latest rows): includes `ts_utc`, `buy_box_present`, `outcome_known`, `we_present`, `action`, `hold_reason`, `writer_mode`.

Alert observed from latest saved health artifacts:
- WARN active (fail=0 warn=2).

Verification status: Pending next cycle check
Changed at: 2026-02-14T14:30:00Z
Latest health snapshot at: 2026-02-14T14:30:12.287141+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 14:39 UTC]
Ticket: Force H pilot to single-SKU mode for L1-54EX-56YC

Scope:
- Stop expanding H pilot targets to all active merchant SKUs.
- Run exactly one SKU per H cycle pass for pilot control.

Changes made:
- Updated config/pilot_sku.yaml:
- use_active_merchant_skus: false
- max_skus_per_run: 1
- Kept pilot identifiers and live gates unchanged (sku, pilot_whitelist_sku, pricing_writer_mode, enabled_live_writes, live_sku_allowlist).

Validation:
- Verified config values in file:
- use_active_merchant_skus: false
- max_skus_per_run: 1

Alert observed from latest saved health artifacts:
- WARN active (fail=0 warn=2): _cycle_recent_fail_lines, _fees_failed_rows_today.

Verification status: Pending next cycle check
Changed at: 2026-02-17T14:39:00Z
Latest health snapshot at: 2026-02-17T14:35:52Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 14:39 UTC]
Ticket: WORK_LOG correction - warning names text encoding

Scope:
- Correct warning check names from previous entry where shell escaping inserted control characters.

Correction:
- Intended warning names are:
- b_cycle_recent_fail_lines
- a_fees_failed_rows_today

Notes:
- Previous entry retained unchanged to preserve append-only policy.
---
['+ $hdr +']
Ticket: H110 pilot target resolution fix (single-SKU mode)

Scope:
- Fix root-cause target selection so single-SKU pilot mode does not get overridden by scope expansion.

Changes made:
- Updated scripts/H110_run_phase1_h_pilot.py:
- Added helper _scope_non_parked_skus().
- Updated _resolve_target_skus(cfg):
- When use_active_merchant_skus is false, target resolution now prioritizes pilot_whitelist_skus / pilot_whitelist_sku / sku from config.
- Scope-based non-parked expansion remains for use_active_merchant_skus true.

Validation:
- Ran python -m py_compile scripts/H110_run_phase1_h_pilot.py (pass).
- Ran direct resolver check with current config:
- use_active_merchant_skus=False
- resolved_targets=[''L1-54EX-56YC'']
- Ran safe dry-run proof:
- python scripts/H110_run_phase1_h_pilot.py --phase1-config config/pilot_sku.yaml --read-only
- Output processed_count=1 and phase1_sku=L1-54EX-56YC.

Alert observed from latest saved health artifacts:
- WARN active (fail=0 warn=1): a_fees_failed_rows_today.

Verification status: Pending next cycle check
Changed at: '+$changed+'
Latest health snapshot at: '+$health+'
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 14:48 UTC]
Ticket: WORK_LOG correction - previous H110 entry variable rendering

Scope:
- Correct prior append where shell variables rendered as literal text.

Correction:
- Ticket: H110 pilot target resolution fix (single-SKU mode)
- Changed at: 2026-02-17T14:47:27Z
- Latest health snapshot at: 2026-02-17T14:45:47Z
- Resolver proof: resolved_targets=['L1-54EX-56YC'] with use_active_merchant_skus=False
- Dry-run proof command: python scripts/H110_run_phase1_h_pilot.py --phase1-config config/pilot_sku.yaml --read-only
- Dry-run proof result: phase1_sku=L1-54EX-56YC, phase1_skus_processed_count=1

Notes:
- Previous malformed entry is retained unchanged to preserve append-only policy.
---
[]
Ticket: Remove H cooldown and long loop wait for pilot

Scope:
- Remove per-SKU wait in Phase1 pilot path.
- Remove 15-minute loop wait from H launcher.

Changes made:
- Updated config/pilot_sku.yaml:
- scan_cooldown_minutes: 0
- Updated scripts/H110_run_phase1_h_pilot.py:
- cooldown clamp changed from min 1 to min 0.
- Updated run_H_cycle.bat:
- --sleep-minutes changed from 15 to 0.

Validation:
- Ran: python -m py_compile scripts/H110_run_phase1_h_pilot.py scripts/run_H_pricing_cycle.py
- Result: pass
- Ran back-to-back dry runs with same timestamp:
- python scripts/H110_run_phase1_h_pilot.py --phase1-config config/pilot_sku.yaml --read-only --now-utc <same_time>
- Result: both runs processed L1-54EX-56YC with processed_count=1 and skipped_cooldown_count=0.

Alert observed from latest saved health artifacts:
- None (fail=0 warn=0).

Verification status: Pending next cycle check
Changed at: 2026-02-17T15:02:47Z
Latest health snapshot at: 2026-02-17T15:02:18Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 15:03 UTC]
Ticket: Remove H cooldown and long loop wait for pilot

Scope:
- Remove per-SKU wait in Phase1 pilot path.
- Remove 15-minute loop wait from H launcher.

Changes made:
- Updated config/pilot_sku.yaml:
- scan_cooldown_minutes: 0
- Updated scripts/H110_run_phase1_h_pilot.py:
- cooldown clamp changed from min 1 to min 0.
- Updated run_H_cycle.bat:
- --sleep-minutes changed from 15 to 0.

Validation:
- Ran: python -m py_compile scripts/H110_run_phase1_h_pilot.py scripts/run_H_pricing_cycle.py
- Result: pass
- Ran back-to-back dry runs with same timestamp:
- python scripts/H110_run_phase1_h_pilot.py --phase1-config config/pilot_sku.yaml --read-only --now-utc <same_time>
- Result: both runs processed L1-54EX-56YC with processed_count=1 and skipped_cooldown_count=0.

Alert observed from latest saved health artifacts:
- None (fail=0 warn=0).

Verification status: Pending next cycle check
Changed at: 2026-02-17T15:02:47Z
Latest health snapshot at: 2026-02-17T15:02:18Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 15:05 UTC]
Ticket: Dynamic Phase1 sleep until next SKU due

Scope:
- Replace fixed Phase1 loop sleep behavior with dynamic sleep based on next SKU cooldown due time.

Changes made:
- Updated scripts/H110_run_phase1_h_pilot.py:
- Added next-due telemetry in output payload:
- phase1_next_due_sleep_seconds
- phase1_next_due_sku
- Cooldown skip path now computes remaining seconds until each skipped SKU is due.
- Updated scripts/run_H_pricing_cycle.py:
- In Phase1 mode, cycle sleep now uses phase1_next_due_sleep_seconds when >0.
- Keeps fixed loop sleep as fallback when no next-due signal exists.
- Added cycle log fields: mode, next_due_seconds, next_due_sku.

Validation:
- Ran: python -m py_compile scripts/H110_run_phase1_h_pilot.py scripts/run_H_pricing_cycle.py
- Result: pass
- Simulated cooldown config run (15 min) with fixed now:
- Output included phase1_next_due_sleep_seconds=793 and phase1_next_due_sku=L1-54EX-56YC.

Alert observed from latest saved health artifacts:
- None (fail=0 warn=0).

Verification status: Pending next cycle check
Changed at: 2026-02-17T15:04:25Z
Latest health snapshot at: 2026-02-17T15:02:18Z
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 16:36 UTC]
Ticket: Single source of truth H floor calculation (ProductDB + tokens only)

Scope:
- Implement one shared H floor resolver and use it in both H engines.
- Remove order-based input usage from active H floor decision path.
- Add guardrail checks for no-order-input, referral-band integrity, referral-source coverage, and formula consistency.

Changes made:
- Added scripts/h_floor_truth.py:
- Shared contracts: HFloorInputs, HFloorResult.
- Strict same-band referral/FBA selection.
- No last_commission_pct usage in H decisions.
- Token COGS source: token_ledger_live next available, token_cogs_ledger median fallback.
- Blocking reason codes for missing required band/token inputs.
- Trace output: out/h_floor_truth_trace.csv with used_order_data_flag=0.
- Updated scripts/H110_run_phase1_h_pilot.py:
- Replaced local floor math with shared h_floor_truth resolver.
- _load_temp_floor_by_sku now returns (floor_by_sku, blocked_by_sku).
- Added FLOOR_INPUT_MISSING_HOLD path to enforce no-write when required floor inputs are missing.
- Updated scripts/run_H_pricing_cycle.py:
- Replaced local fee/referral floor estimation with shared h_floor_truth resolver.
- Added blocking hold behavior: FLOOR_INPUT_MISSING_HOLD.
- Removed active order-based floor trace injection from calc_trace.
- Added shared floor trace append on profit floor compute.
- Updated scripts/A015_build_system_health_check.py:
- Added H_FLOOR_TRUTH_TRACE_PATH.
- Added checks:
- h_floor_no_order_inputs
- h_floor_referral_band_integrity
- h_floor_referral_source_coverage
- h_floor_formula_consistency
- Updated tests:
- Added tests/test_h_floor_truth.py.
- Updated tests/test_h110_temp_floor_source.py for new tuple return and blocker assertion.
- Extended tests/test_a015_health_check_runtime.py with h_floor guardrail coverage test.
- Updated runbook note:
- out/process_guides/repricing_tool/master plans/Phased execution/phase_1_scheduler_notes.md
- Added explicit note: commission == referral fee alias and strict in-band fallback rules.

Validation:
- Ran: python -m py_compile scripts/h_floor_truth.py scripts/H110_run_phase1_h_pilot.py scripts/run_H_pricing_cycle.py scripts/A015_build_system_health_check.py
- Result: pass
- Ran: python -m py_compile tests/test_h_floor_truth.py tests/test_h110_temp_floor_source.py tests/test_a015_health_check_runtime.py
- Result: pass
- Ran: python -m unittest tests.test_h_floor_truth tests.test_h110_temp_floor_source tests.test_a015_health_check_runtime -v
- Result: pass (12 tests)
- Ran: python -m unittest tests.test_h_floor_policy -v
- Result: pass (4 tests)

Alert observed from latest saved health artifacts:
- FAIL present in latest snapshot: out/health_status.csv at 2026-02-17T15:45:42.134135+00:00 (fail=1 warn=0).

Verification status: Pending next cycle check
Changed at: 2026-02-17T16:35:28Z
Latest health snapshot at: 2026-02-17T15:45:42.134135+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 16:52 UTC]
Ticket: Lock H execution to daily head floor/ceiling with manual refresh override

Scope:
- Keep execution boundaries stable during the day.
- Allow manual intraday refresh only when explicitly requested.

Changes made:
- Updated scripts/run_H_pricing_cycle.py:
- Executioner now locks head boundary per UTC day in state:
- head_boundary_lock_date
- head_boundary_lock_payload
- head_boundary_lock_utc
- head_boundary_lock_reason
- Default behavior: reuse locked boundary for all intraday execution cycles.
- Manual override added:
- H_FORCE_HEAD_BOUNDARY_REFRESH=1 forces intraday boundary refresh from active head boundary.
- Added trace fields for boundary lock source/reason in calc trace.

Validation:
- Ran: python -m py_compile scripts/run_H_pricing_cycle.py
- Result: pass

Alert observed from latest saved health artifacts:
- FAIL present in latest snapshot: out/health_status.csv at 2026-02-17T15:45:42.134135+00:00 (fail=1 warn=0).

Verification status: Pending next cycle check
Changed at: 2026-02-17T16:52:00Z
Latest health snapshot at: 2026-02-17T15:45:42.134135+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 17:14 UTC]
Ticket: Phase 1 recovery - active-merchant scan with single-SKU write gate

Scope:
- Run full active-merchant read path while preserving single live writer SKU.
- Unify H and A universe selection.
- Add daily intel alignment hook and runtime floor truth snapshot.

Changes made:
- Added scripts/phase1_target_universe.py:
- Shared deterministic resolver for target_universe_mode: active_merchant, scope_non_parked, lab_cohort, single_sku.
- Active merchant mode requires merchant status=active plus latest in-stock listing row.
- Updated scripts/H110_run_phase1_h_pilot.py:
- Replaced local target selection with shared resolver.
- Preserved live write allowlist gate and processed all due SKUs when max_skus_per_run <= 0.
- Added target-universe diagnostics to state payload.
- Updated scripts/A016_refresh_phase1_daily_intel.py:
- Replaced diverging scope selection with shared resolver so A016 and H110 resolve same universe.
- Added target-universe diagnostics in A016 output.
- Updated scripts/run_H_pricing_cycle.py:
- Added once-per-UTC-day pre-H daily intel alignment subprocess call to A016 (full_db scope).
- Added runtime floor snapshot export: out/phase1_runtime_floor_snapshot_latest.csv.
- Fixed snapshot merge bug caused by duplicate sku labels during trace merge.
- Updated config/pilot_sku.yaml:
- target_universe_mode: active_merchant
- scan_cooldown_minutes: 15
- max_skus_per_run: 0
- live_sku_allowlist kept as L1-54EX-56YC
- Updated config/pilot_sku_live_test.yaml:
- explicit target_universe_mode: single_sku and single-SKU allowlist settings.
- Updated guidebook:
- out/process_guides/repricing_tool/master plans/Phased execution/phase_1_execution_plan.md
- Added operational truth vs historical diagnostics section and recovery plan update.
- Added tests/test_phase1_target_universe.py with four mode tests.

Validation:
- Ran: python -m py_compile scripts/phase1_target_universe.py scripts/H110_run_phase1_h_pilot.py scripts/A016_refresh_phase1_daily_intel.py scripts/run_H_pricing_cycle.py
- Result: pass
- Ran: python -m unittest tests.test_phase1_target_universe -v
- Result: pass (4 tests)
- Ran: python -m unittest tests.test_a016_daily_intel_scheduler tests.test_h110_temp_floor_source -v
- Result: pass (5 tests)
- Runtime evidence:
- resolve_target_universe(config/pilot_sku.yaml) -> mode=active_merchant, candidate_count=61, resolved_count=61.
- execution_log live-write rows remain allowlisted only: non_allowlist_live_write_rows=0.
- execution_log at 2026-02-17T17:06:36Z shows multi-SKU processing (40 unique SKUs) with read-only statuses for non-allowlisted SKUs.
- floor snapshot helper run produced: phase1_runtime_floor_snapshot_status=ok, rows=30.

Alert observed from latest saved health artifacts:
- FAIL present in out/health_status.csv at 2026-02-17T15:45:42.134135+00:00 (fail=1 warn=0, check h_floor_phase1_cogs_basis_drift).

Verification status: Pending next cycle check
Changed at: 2026-02-17T17:11:55Z
Latest health snapshot at: 2026-02-17T15:45:42.134135+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 17:25 UTC]
Ticket: Freeze Phase1 floor/ceiling inputs once per UTC day after daily A alignment

Scope:
- Stop intraday boundary drift in H.
- Keep full-scan read path and single-SKU live-write gate.

Changes made:
- Updated scripts/H110_run_phase1_h_pilot.py:
- Added per-SKU daily boundary lock stored in out/phase1_sku_scan_state.json under daily_boundary_lock.
- On first SKU run each UTC day: set lock values (hard_floor_gbp, manual_cap_gbp, final_ceiling_landed_gbp).
- On later runs same UTC day: reuse locked hard_floor_gbp/manual_cap_gbp instead of recalculating.
- Daily lock auto-resets when UTC date changes.
- Added output diagnostics:
- phase1_boundary_lock_mode
- phase1_boundary_lock_date
- phase1_boundary_lock_final_ceiling_gbp
- phase1_boundary_lock_sku_count
- Disabled H-triggered intraday A refresh by default; H now only auto-refreshes intel intraday if config allow_h_intraday_intel_refresh=true.
- Updated config/pilot_sku.yaml:
- allow_h_intraday_intel_refresh: false
- Updated config/pilot_sku_live_test.yaml:
- allow_h_intraday_intel_refresh: false

Validation:
- Ran: python -m py_compile scripts/H110_run_phase1_h_pilot.py scripts/run_H_pricing_cycle.py
- Result: pass
- Ran: python -m unittest tests.test_h110_temp_floor_source -v
- Result: pass (1 test)
- Symbol check:
- phase1_boundary_lock and allow_h_intraday_intel_refresh references present in H110/config files.

Alert observed from latest saved health artifacts:
- FAIL present in out/health_status.csv at 2026-02-17T15:45:42.134135+00:00 (fail=1 warn=0, h_floor_phase1_cogs_basis_drift).
- H log still reports daily_intel missing events in latest cycle window.

Verification status: Pending next cycle check
Changed at: 2026-02-17T17:25:24Z
Latest health snapshot at: 2026-02-17T15:45:42.134135+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
[2026-02-17 17:47 UTC]
Ticket: H cycle resilience hardening to match B-style runner safety

Scope:
- Prevent H from silently exiting to Task Scheduler Ready.
- Add crash recovery, retries, timeouts, and lock safety to H runner.

Changes made:
- Updated scripts/run_H_pricing_cycle.py:
- Added subprocess timeouts:
- H_PHASE1_PILOT_TIMEOUT_SECONDS (default 1800s)
- H_PHASE1_ALIGNMENT_TIMEOUT_SECONDS (default 2700s)
- Added step retry framework:
- _run_with_retries(name, fn)
- H_STEP_MAX_RETRIES (default 2)
- H_STEP_BACKOFF_BASE (default 2)
- Added loop crash recovery:
- wraps each cycle in try/except
- logs cycle_error and sleeps H_LOOP_ERROR_SLEEP_SECONDS (default 30s)
- Added lock self-healing and ownership safety:
- _write_lock() now writes pid/start/heartbeat
- _ensure_lock_ownership() recreates missing lock and recovers stale lock
- _release_lock() now only removes lock if owned by current pid
- Hooked retries into phase1 critical steps:
- snapshot refresh
- daily intel alignment subprocess
- seller profile build
- H110 pilot subprocess
- runtime floor snapshot writer
- Hooked retries into legacy path steps (head/supervisor/executioner refreshes)

Validation:
- Ran: python -m py_compile scripts/run_H_pricing_cycle.py
- Result: pass
- Symbol checks confirmed for new timeout/retry/lock functions.

Operational note:
- run_H_cycle.bat was already updated earlier to self-restart on python exit.
- This patch removes common causes of python exit and lock corruption inside H itself.

Alert observed from latest saved health artifacts:
- FAIL still present in out/health_status.csv (h_floor_phase1_cogs_basis_drift).
- WARN count now non-zero in latest rows.
- H logs still show daily_intel missing events.

Verification status: Pending next cycle check
Changed at: 2026-02-17T17:46:45Z
Latest health snapshot at: 2026-02-17T17:46:45.666625+00:00
Next verifier: next scheduled cycle A015

Carryover:
- None

Next:
- None
---
