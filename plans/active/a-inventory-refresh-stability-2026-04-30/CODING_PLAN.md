# A Inventory Refresh Stability - Coding Plan

## Current Phase
- Status: closed for A inventory refresh stability; A-owned live proof confirmed and downstream B stock propagation confirmed.
- Changed at UTC: 2026-04-30T13:19:00Z.

## Problem
- `A_SKIP_LEGACY_SHEET_OUTPUT_STEPS=1` skipped `A003_run_inventory_to_sheet.py`.
- That avoided legacy sheet output, but also skipped the local inventory refresh that writes `out/inventory_summaries.csv` and `out/inventory_snapshot_latest.csv`.
- B and downstream H/E/O artifacts then rebuilt fresh-looking outputs from stale stock.
- Second root cause found during cleanup: in SQL mode, A003 wrote the token-floor-corrected `out/inventory_summaries.csv`, but did not overwrite SQL table `a_inventory_summaries` after applying the correction.
- A015 reads `a_inventory_summaries` through SQL fallback, so health was judging the raw API-owner inventory instead of the corrected inventory summary.
- Same class found for inventory history: `out/inventory_history.csv` had today rows, but SQL fallback table `a_inventory_history` had not been refreshed by A003.

## Allowed Files
- `scripts/cycles/run_A_all.py`
- `scripts/flows/A/A003_run_inventory_to_sheet.py`
- `tests/test_a_split_health_modes.py`
- `tests/test_a003_inventory_stale_token_floor.py`
- `project_control/EXPECTATIONS/A_cycle_expectations.md`
- this plan file

## Tests
- Passed: `python -m pytest tests/test_a_split_health_modes.py tests/test_a003_inventory_stale_token_floor.py`.
- Passed: `python -m pytest tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_fails_on_unresolved_stale_undercount tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_ok_when_stale_row_matches_token_floor`.
- Passed after SQL persistence fix: `python -m pytest tests/test_a003_inventory_stale_token_floor.py tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_fails_on_unresolved_stale_undercount tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_ok_when_stale_row_matches_token_floor`.
- Passed after inventory history SQL fix: `python -m pytest tests/test_a003_inventory_stale_token_floor.py tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_fails_on_unresolved_stale_undercount tests/test_a015_health_check_runtime.py::A015HealthCheckRuntimeTests::test_a_inventory_stale_token_gap_stats_ok_when_stale_row_matches_token_floor`.

## Live Proof
- User approved live proof with "run it now".
- Forced proof plan: `python scripts/one_off/P002_plan_forced_proof_window.py --flow a`.
- Proof run: `cmd /c run_A_all.bat`.
- A run id: `20260430T124556Z`.
- A manifest: `out/manifests/A/2026-04-30/20260430T124556Z.json`.
- A003 launched and completed with rc 0.
- A003 notes: `elapsed=18.1s;fresh_outputs=2`.
- Fresh A003 outputs: `out/inventory_snapshot_latest.csv`, `out/inventory_history.csv`.
- Target SKU `6V-EEC1-2S9Z` in `out/inventory_summaries.csv` after proof:
- available: 183.
- total_quantity: 215.
- last_updated_time: `2026-04-30T12:43:31Z`.
- row_last_updated_status: `FRESH`.
- row_stock_truth_source: `SPAPI`.
- Target SKU in `out/inventory_snapshot_latest.csv` after proof:
- available: 183.
- total_quantity: 215.
- last_updated_time: `2026-04-30T12:43:31Z`.
- B downstream proof: cycle `B_20260430T125309Z` refreshed `out/parking/stock_snapshot_latest.csv`; target `total_qty` is 215 with reason_code `OK`.
- Repricer/observation proof: `out/analysis_reports/phase1_observation_view_2026-04-30.csv` shows target `Stock` 183.
- Superseded earlier evidence: first proof still failed `a_inventory_stale_token_gap`; this was traced to SQL/CSV mismatch and fixed.
- Second proof run after SQL persistence fix: `cmd /c run_A_all.bat`.
- Second A run id: `20260430T130957Z`.
- Second A manifest: `out/manifests/A/2026-04-30/20260430T130957Z.json`.
- Second A final_state: `completed`.
- Second A health summary: fail_count 0, warn_count 0, ok_count 6.
- `a_inventory_stale_token_gap` after second proof: status `ok`, value 0, available_gap_rows 0, total_gap_rows 0.
- SQL fallback read of `a_inventory_summaries` returned 339 rows and showed the token-floor-corrected rows, proving SQL and CSV are aligned after A003.
- B ownership restored after A: `out/systems/B/live/B_cycle.lock` present with pid 17208 and fresh heartbeat after A maintenance cleared.
- Third proof run after inventory history SQL fix: `cmd /c run_A_all.bat`.
- Third A run id: `20260430T132254Z`.
- Third A manifest: `out/manifests/A/2026-04-30/20260430T132254Z.json`.
- Third A final_state: `completed`.
- Third A health summary: fail_count 0, warn_count 0, ok_count 6.
- `a_inventory_stale_token_gap` after third proof: status `ok`, value 0, available_gap_rows 0, total_gap_rows 0.
- `a_inventory_history` SQL fallback read returned 23986 rows, including 339 rows for `2026-04-30`.
- Global `h_inventory_history_idempotent_today` cleared to OK after the third proof.
- Post-maintenance B proof: cycle `B_20260430T132944Z` finalized after A maintenance and cleared the temporary `l1_keys_missing_in_master` fail.
- B stock propagation proof: `out/parking/stock_snapshot_latest.csv` row for `6V-EEC1-2S9Z` has `total_qty` 215, `source_cycle_run_id` `B_20260430T132944Z`, reason_code `OK`, asof `2026-04-30T13:39:04Z`.
- Remaining non-A issue after B proof: `token_shortages_by_sku` fail value 5 and `order_master_placeholder_cogs_rows` warn value 5.

## Timeout Rule
- No timeout. Approved proof window was run.

## Automatic Next Step
- Continue with repricer delayed-SKU investigation if requested. No Google Sheet edits or DB-to-Sheet alignment were made.
