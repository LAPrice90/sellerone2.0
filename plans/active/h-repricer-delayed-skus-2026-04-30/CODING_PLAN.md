# H Repricer Delayed SKUs - Coding Plan

## Current Phase
- Status: code fix applied; isolated verification passed; live H proof confirmed.
- Started at UTC: 2026-04-30T14:27:00Z.
- Last updated UTC: 2026-04-30T14:56:30Z.

## SKU Set
- RB-1O77-8969
- RI-VSUS-0YTD
- TJ-6LOP-OPEU
- U1-M5BM-8F5W
- US-AK96-YFSB
- W3-8FN7-FSP0
- WE-1Z7L-SA2I
- WJ-YHKC-EES5
- XE-YPAI-HX9F
- OV-LVEL-DQL6
- R7-98IN-2PW8
- RB-82FL-T88J
- RZ-6ZL9-CZ7J
- SU-JM8R-2U82
- TK-E7QE-T40G
- VL-48KZ-J3F2
- XY-UM2X-TPS3

## Problem
- User reports these SKUs are always delayed on the repricer.
- Need identify the exact delay stage: scope eligibility, stock, daily intel, market data, seller-detail rotation, decision, write attempt, or publish.
- Root-cause fix must happen at the earliest responsible stage.

## Root Cause
- Delay stage is H selector/cooldown, not stock, scope, seller detail, market data, write gate, or publish.
- All listed SKUs are eligible: `repricing_enabled=1`, `observe_effective=1`, `write_effective=1`, `writer_mode=CODEX_H`, not parked, and not excluded by stock/scope files.
- Seller detail is recovered for all listed SKUs: `seller_detail_status=DETAIL_OK`, `seller_detail_resolution_status=RECOVERED`, `retry_next_run_flag=0`.
- Runtime floor snapshot marked all listed SKUs as `current_cycle_decision=skip_cooldown` with `reason_code=cooldown`.
- The active write-effective universe is larger than `max_skus_per_run=50`; the listed SKUs sit around ranks 55-82 in SKU sort order, so alphabetically earlier due SKUs can repeatedly consume the capped batch.
- Earliest responsible stage is the H due-SKU selector before the max-SKU cap.
- During proof, 5 of the 17 also hit a narrower seller-detail hold (`READ_ONLY_NO_WRITE`) after selector recovery. That was not the same root cause. The next normal live run used the existing one-cycle seller-detail retry path and recovered all 5.

## Fix Applied
- Updated `scripts/flows/H/H110_run_phase1_h_pilot.py` so due rows are ordered by:
- write-enabled rows first
- oldest `last_scan_utc` next
- SKU only as the tie-breaker
- This keeps write-enabled priority but prevents alphabetically early SKUs from permanently taking the 50-SKU capped batch.

## Allowed Files
- Write scope used for this phase:
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `tests/test_h110_scan_due_order.py`
- `plans/active/h-repricer-delayed-skus-2026-04-30/CODING_PLAN.md`
- No Google Sheet edits.
- No DB-to-Sheet or Sheet-to-DB alignment changes.

## Evidence Targets
- `out/phase1_sku_scope.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/listing_offer_snapshot_latest.csv`
- `out/listing_offer_seller_snapshot_latest.csv`
- `out/systems/H/live/h110_sku_lifecycle_log.csv`
- `out/systems/H/live/h_pricing_cycle_state.json`
- `out/analysis_reports/phase1_observation_view_2026-04-30.csv`
- `out/cycle_alerts/checklist_H_split.csv`

## Tests And Proof
- If code changes are made, run focused H tests first.
- H-owned live proof requires scheduler/owner-safe guarded proof, not an ad-hoc partial script.
- Separate statuses:
- code fix applied
- isolated verification passed
- live H proof confirmed
- Isolated tests passed at UTC 2026-04-30T14:20-14:25 range:
- `python -m pytest tests/test_h110_scan_due_order.py tests/test_h110_stock_stale_guard.py tests/test_h110_market_payload_snapshot_floor.py`
- Result: 9 passed.
- Forced proof plan command run:
- `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
- Required live proof sequence:
- `.\run_H_isolation_status.bat`
- `.\run_H_isolation_pause.bat`
- `.\run_H_isolation_success.bat`
- `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
- `.\run_H_isolation_resume.bat`
- Controlled proof run:
- run_id: `20260430T143429Z`
- terminal state: `finalized`
- publish status: `ok`
- worker outcome: `succeeded`
- last finalized marker: `20260430T143429Z`
- Target SKU selector proof:
- all 17 listed SKUs were selected and reached `decision=execute`
- 12 reached `write_status=NO_WRITE_REQUIRED`
- 5 reached `write_status=READ_ONLY_NO_WRITE` with seller-detail rotation pending, then recovered in the next live run
- H-scoped health after controlled proof:
- `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
- result: 104 OK, 3 WARN, 0 FAIL
- WARNs: `h_strategy_sample_size_multi_seller_ladder_cap`, `h_strategy_sample_size_single_rival_reset`, `h_floor_referral_source_coverage`
- Scheduler ownership restoration:
- `run_H_isolation_resume.bat` succeeded
- controlled mode cleared
- scheduled task enabled
- normal H owner process restarted
- new live run observed: `20260430T145155Z`

## Monitoring
- Current H owner is active under `out/systems/H/live/H_pricing_cycle.lock`.
- Poll cadence during investigation: read artifacts after current H run reaches terminal markers or when specific evidence files update.
- Success threshold: all listed SKUs have a clear non-delayed path reason, or the fix removes the repeated delay cause and live proof shows the affected stage advancing.
- Live proof success threshold:
- controlled H run reaches terminal markers (`finalized` / `succeeded` equivalent)
- H-scoped health is read after the controlled run finalizes
- target SKU evidence from the proof run shows the selector is no longer starving later-alphabet write SKUs behind the first 50 rows
- scheduler ownership is resumed and a new H owner process or run is observed
- Seller-detail follow-up:
- next normal live run `20260430T145155Z` raised item-offers budget from 15 to 65 because 50 ASINs were pending seller-detail retry
- the 5 held SKUs recovered seller detail:
- `W3-8FN7-FSP0`: `DETAIL_OK`, rows=4, `RECOVERED`
- `WE-1Z7L-SA2I`: `DETAIL_OK`, rows=3, `RECOVERED`
- `WJ-YHKC-EES5`: `DETAIL_OK`, rows=2, `RECOVERED`
- `XE-YPAI-HX9F`: `DETAIL_OK`, rows=4, `RECOVERED`
- `XY-UM2X-TPS3`: `DETAIL_OK`, rows=10, `RECOVERED`
- all five now have `retry_next_run_flag=0`

## Automatic Next Step
- Monitor normal H ownership through the routine H cycle artifacts. No further selector fix is needed now.

## Verification Status
- Verification status: Live H proof confirmed
- Changed at: 2026-04-30T14:20:00Z
- Latest H-scoped health snapshot at: 2026-04-30T14:50:05Z
- Next verifier: routine H cycle monitoring; success condition is no reappearance of selector starvation for later-alphabet due SKUs
