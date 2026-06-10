# Timeout Queue Integration Plan

Date: 2026-05-01
Scope: F price-list manager timeout memory and scan queue filtering.

## Goal
When the price-list manager loads a new supplier file, it should keep the full source file for audit and comparison, but it must not stage timed-out barcodes into F061.

Timed-out rows should disappear from the scanner queue, not from the supplier batch record.

## Core Decision
Use one shared scanner memory table, not separate supplier timeout lists.

Canonical memory:
- `out/systems/F/price_list_manager/test_mode/barcode_scan_memory.csv` for current manager-owned memory
- same schema should be used when promoted to live ownership

Keep two memory scopes:
- `global_barcode` for product facts that apply across suppliers
- `supplier_offer` for economics that depend on supplier, barcode, and cost

Do not maintain separate per-supplier timeout files as source of truth. Per-supplier views can be generated from the single memory table when needed.

## Why One Memory Table
One barcode can appear in many supplier files.

If the fail reason is product-level, rescanning it for another supplier wastes capacity:
- `NOASIN`
- `OVER50K`
- `HAZMATFAIL`
- `BRANDFAIL`
- `NODATE`
- `REVIEWFAIL`
- `SCRAPEFAIL`
- `LOWSALESFAIL`
- `SELLERHISTORYFAIL`
- `PRICEHISTORYFAIL`
- `RESCAN`
- `FAIL`

If the fail reason is economics or cost-level, a supplier change can make it worth trying again:
- `NOCOST`
- `ROIFAIL`
- `LOWROI`

Those should use `supplier_offer` memory and reset when the supplier cost changes.

## Timing Rules
### Current Active Scan
Do not rebuild or prune the currently active F061 run mid-scan.

For the current Entertainment Trading scan:
- let F061 finish the current active run
- import completed scan results into manager memory at chunk boundaries and at final drain
- create the next filtered scan list only at the next manager batch-selection boundary

This avoids rewriting `supplier_price_list_active_run.csv` while F061 is already working from it.

### Future Supplier Files
For every new supplier file:
1. Acquire or import the file.
2. Convert it into full `batch_rows.csv`.
3. Apply timeout memory before any F061 staging.
4. Write `batch_scan_eligibility.csv`.
5. Stage only rows where `scan_decision=scan`.

The manager may import the full file immediately. It should not wait for timeout expiry to store the file.

## What Disappears From Where
Full supplier batch:
- rows stay in `batch_rows.csv`
- used for audit, row hash comparison, and future changed-cost detection

Scanner queue:
- timed-out rows are excluded from `batch_scan_eligibility.csv`
- F061 handoff uses only eligible rows

Timeout memory:
- rows stay until replaced by newer scan evidence
- expired rows do not need deleting
- each manager cycle recomputes whether the timeout is still active

So a barcode "comes back" when either:
- `observed_utc >= cooldown_until_utc`
- supplier cost changed for cost-sensitive policies
- source identity/hash changed for future source-sensitive policies
- operator manually disables or edits the policy

## Required Flow Change
Current late filter:
- `FPM040_build_next_action.py` already evaluates timeout memory when building `batch_scan_eligibility.csv`.

Needed improvement:
- move that decision logic into a shared helper, then call it earlier after source import/conversion.

Recommended helper:
- `scripts/flows/F/price_list_manager/timeout_queue.py`

Responsibilities:
- read `barcode_scan_memory.csv`
- read `config/feeder/f_scanner_timeout_policy.csv`
- match each batch row to global or supplier-offer memory
- decide `scan_now`, `skip_cooldown`, `hold`, or `blocked_missing_data`
- write consistent reason codes
- update batch counts

## Row State Rules
For each row in a new price list:
- missing barcode or missing cost -> `hold`
- no memory -> `scan_now`
- global memory active -> `skip_cooldown`
- supplier-offer memory active and cost unchanged -> `skip_cooldown`
- supplier-offer memory active but cost changed -> `scan_now`
- timeout expired -> `scan_now`

Reason codes should be plain and stable:
- `new_barcode`
- `cost_changed_reset`
- `timeout_active`
- `timeout_expired`
- `missing_barcode`
- `missing_unit_cost`
- `manual_review_required`
- `policy_disabled`
- `unknown_fail_code_fallback_fail`

## Result Memory Timing
Manager memory should be updated only from finalized scanner evidence.

Safe update points:
- after each F061 child chunk finishes successfully
- after the supplier run drains to zero pending rows
- after a controlled test-mode placeholder scan finishes

Do not read half-written F061 outputs mid-chunk.

Recommended new live importer:
- `scripts/flows/F/price_list_manager/FPM126_update_memory_from_f061_results.py`

Input:
- `out/systems/F/live/f_screening_row_state_live.csv`
- current batch row map
- current timeout policy

Output:
- updated `barcode_scan_memory.csv`
- health rows proving row counts and unique memory keys

## Batch Count Updates
After timeout filtering, update `price_list_batches.csv`:
- `source_row_count`: full imported source rows
- `valid_row_count`: rows with usable barcode and cost
- `held_row_count`: missing required data
- `new_row_count`: no prior memory
- `changed_row_count`: prior supplier-offer memory exists but cost/source changed
- `eligible_row_count`: rows that can be scanned now
- `skipped_cooldown_row_count`: rows skipped by active timeout

Success equation:
- `valid_row_count = eligible_row_count + skipped_cooldown_row_count + other_valid_non_scan_rows`

## Implementation Phases
### Phase 1 - Shared Timeout Queue Helper
Build `timeout_queue.py` and tests using current CSV artifacts only.

Proof:
- same inputs produce same `batch_scan_eligibility.csv` as current FPM040 logic
- cost-change reset works
- expired timeout returns to scan queue
- global barcode timeout blocks same barcode for another supplier
- supplier-offer timeout does not block changed-cost row

### Phase 2 - Apply Filter Immediately After Import
Call the shared helper after:
- `FPM011_import_ready_sources.py`
- `FPM012_enrich_batch_rows_for_f061.py`

FPM040 should still rebuild eligibility as a safety pass, but it should use the same helper.

Proof:
- a new file with 100 rows and 80 active timeouts stages only 20 scanner rows
- batch counts reconcile
- F061 preview/handoff contains no active-timeout rows

### Phase 3 - Live F061 Result Memory Import
Add `FPM126_update_memory_from_f061_results.py`.

Run it:
- after each successful F061 child chunk in `FPM130_run_live_cycle.py`
- after final supplier drain

Proof:
- completed F061 rows become memory rows
- memory key count is unique
- policy health remains ok
- next manager queue build skips rows that just failed and timed out

### Phase 4 - Queue UI Evidence
Add operator-visible counts to the existing Price List Queue view:
- full rows
- eligible now
- skipped by timeout
- held missing data
- top skip reasons
- next timeout expiry date for the selected supplier

No new app. Use the existing Streamlit page.

### Phase 5 - Safe Live Cutover
Do not prune the current active scan.

Cutover point:
- when current Entertainment Trading active run reaches terminal drain or an explicit safe F manager batch-selection boundary

Proof:
- active F061 run is terminal or idle
- manager chooses a batch using filtered eligibility
- staged F061 active run row count equals eligible rows only
- no active-timeout rows appear in staged handoff

## Health Checks
Add health rows for:
- timeout memory file exists
- memory keys are unique
- policy rows are valid
- eligibility row count equals batch row count
- staged F061 row count equals eligible scan count
- active-timeout rows staged to F061 equals 0
- cost-change reset count is recorded
- expired-timeout re-entry count is recorded

Any active-timeout row staged to F061 should be a FAIL health condition.

## Recommended Build Order
1. Build shared timeout queue helper.
2. Prove it with isolated fixtures.
3. Wire helper into FPM040 first.
4. Wire helper into post-import/post-enrichment flow.
5. Add live F061 result memory importer.
6. Add health checks.
7. Add UI counts.
8. Wait for current active scan boundary.
9. Run a controlled manager batch-selection proof.

## Definition Of Done For This System
- The manager can load a full supplier file.
- The full file remains auditable.
- Timed-out rows are excluded before F061 staging.
- New barcodes are prioritized.
- Changed-cost rows can re-enter.
- Expired rows can re-enter automatically.
- Active-timeout rows staged to F061 equals 0.
- No Google Sheets writes are required.
