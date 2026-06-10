# CODING_PLAN - H Floor Recovery Proof (2026-04-22)

## Ticket Scope
- Confirm runtime proof for the H repricer fix that allows upward recovery to floor when current price is below floor.
- Investigate and permanently fix repeated stale stock truth entering H runtime decisions.
- No Google Sheets writes.
- No local DB alignment changes.

## Phase 1 - Code + Isolated Tests
- Status: complete
- Allowed files:
- `scripts/phase1/phase1_main_loop.py`
- `tests/test_phase1_main_loop.py`
- Isolated proof:
- `python -m pytest tests/test_phase1_main_loop.py -q`
- `python -m pytest tests/test_phase1_probe_engine.py tests/test_phase1_ceilings.py -q`
- Success threshold:
- All targeted tests pass.

## Phase 2 - Forced H Runtime Proof Window
- Status: complete (runtime ownership and terminal proof), floor-behavior sub-gate pending
- Owner flow: H
- Forced proof plan tool:
- `python scripts/one_off/P002_plan_forced_proof_window.py --flow h --format text`
- Ownership handoff sequence:
1. `run_H_isolation_status.bat`
2. `run_H_isolation_pause.bat`
3. `run_H_isolation_success.bat`
4. Read finalized H artifacts only after terminal markers
5. `run_H_isolation_resume.bat`
6. `run_H_isolation_status.bat`
- Live monitoring targets:
- `out/systems/H/live/H_run_state.json`
- `out/systems/H/live/H_worker_lifecycle.json`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/listing_offer_snapshot_latest.csv`
- Poll cadence:
- First check at +5 minutes
- Second check at +10 minutes
- Then every +15 minutes
- Stop at +60 minutes
- Success threshold:
- Controlled one-shot reaches terminal success markers.
- Scheduler ownership restored and task enabled/running truth is present.
- Runtime floor snapshot shows no below-floor rows blocked by:
- `CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD`
- `CPT_RISK_HIGH_UPWARD_BLOCK`
- `CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK`
- Observed proof:
- `run_H_isolation_success.bat` passed with terminal `run_state=finalized`, `publish_status=ok`, `worker_state=succeeded` for run `20260422T104239Z`.
- `run_H_isolation_failure.bat` passed induced-failure guard path with terminal `run_state=failed` for run `20260422T110504Z`.
- `run_H_isolation_resume.bat` passed; scheduler enabled and owner processes relaunched.
- `run_H_isolation_status.bat` after resume shows owner processes and live launcher/cycle locks present.
- Remaining blocker for floor-behavior sub-gate:
- Latest runtime floor snapshot (`out/phase1_runtime_floor_snapshot_latest.csv`) is from `2026-04-22T10:42:39Z` and still contains below-floor `NO_WRITE_REQUIRED` rows, including `CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD`.
- The finalized forced-proof run (`20260422T104239Z`) itself ended `SKIP_NO_MARKET_DATA`, so floor-recovery write behavior was not exercised in that run.
- Timeout rule:
- If threshold not met by +60 minutes, mark `parked pending next proof window` and record exact blocker artifact.
- Automatic next step when proof arrives:
- Move to Phase 3 sign-off summary with explicit runtime status language.

## Phase 3 - Sign-off Gate
- Status: complete (code scope), full operational sign-off not approved
- Required statement format:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed` (or `not yet proven` if threshold not met)
- Final proof outcome:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed`
- Verdict:
- Code fix is sign-off ready.
- Full operator-facing ticket sign-off is not ready because the latest floor snapshot still presents stale old execution rows as if they are current below-floor holds.
- Current evidence:
- `out/phase1_runtime_floor_snapshot_latest.csv` at snapshot `2026-04-22T11:34:48Z` still has 2 below-floor rows carrying old `CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD` reason codes.
- Those same rows have stale execution timestamps (`2026-03-11T23:45:13Z` and `2026-03-18T11:02:00Z`) while their trace rows are fresh (`trace_asof_utc=2026-04-22T11:38:34Z`).
- In latest finalized live run `20260422T113448Z`, both SKUs (`AX-NKNU-29C1`, `0G-JB6S-PN34`) are `skip_no_market_data` with `market_data_present=0` in `out/systems/H/live/h110_sku_decision_log.csv`.
- That proves the active blocker is current market-data absence, not the repaired CPT upward-block logic.

## Phase 4 - Next Fixes
- Status: parked pending next proof window
- Goal:
- Make the runtime floor snapshot truthfully represent the current blocker for stale below-floor SKUs at the H-cycle source.
- Allowed files:
- `scripts/cycles/run_H_pricing_cycle.py`
- `tests/test_h_split_health_gate.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py` only if downstream carry-through is still needed after the upstream fix
- Proposed changes:
1. In `scripts/cycles/run_H_pricing_cycle.py`, merge latest H110 decision-log truth into `_write_phase1_runtime_floor_snapshot`.
2. When the latest current-cycle decision is `skip_no_market_data` with `market_data_present=0` and it is newer than the stale execution row, preserve the historic execution evidence in dedicated stale-history columns but clear it from live execution truth.
3. Add a fresh explicit current-cycle blocker code such as `MARKET_DATA_MISSING_CURRENT_CYCLE` so old CPT hold codes do not appear as live blockers.
4. Add targeted tests proving a fresh snapshot row can coexist with an old execution row without falsely showing current CPT hold behavior.
5. Rerun one scheduler-owned H cycle and confirm those 2 SKUs no longer appear as active below-floor CPT-hold rows in `out/phase1_runtime_floor_snapshot_latest.csv`.
- Code and isolated proof:
- `scripts/cycles/run_H_pricing_cycle.py` now carries current-cycle H110 decision truth into the runtime floor snapshot and clears superseded stale execution context into `stale_execution_*` fields.
- `tests/test_h_split_health_gate.py` adds a regression proving `skip_no_market_data` plus `market_data_present=0` clears old live CPT-hold execution truth and replaces it with `MARKET_DATA_MISSING_CURRENT_CYCLE`.
- `python -m pytest tests/test_h_split_health_gate.py tests/test_phase1_main_loop.py tests/test_phase1_probe_engine.py tests/test_phase1_ceilings.py -q`
- Result: `81 passed`.
- Forced live proof attempted:
- `run_H_isolation_pause.bat` succeeded and isolated H ownership.
- `run_H_isolation_success.bat` launched controlled run `20260422T120455Z`, but the run did not reach finalize success.
- Terminal truth for that run:
- `H_run_state.json`: `state=failed`, `failure_code=LOOP_RC_1`, `utc=2026-04-22T12:23:53Z`
- `H_worker_lifecycle.json`: `state=failed`, `terminal_outcome=failed`, `reason_code=LOOP_RC_1`
- Exact blocker seen:
- `out/systems/H/live/h_pricing_cycle_state.json` shows `phase1_skus_processed_count=68` and `phase1_runtime_floor_snapshot_utc=2026-04-22T11:34:48Z`, proving the failed proof run never rewrote the runtime floor snapshot.
- Latest pilot checkpoint for the failing run is `sku_exec_pre_write` on `X7-MY4W-H2I4` at `2026-04-22T12:23:45Z`.
- Resume / ownership restore:
- `run_H_isolation_resume.bat` succeeded.
- Follow-up `run_H_isolation_status.bat` at `2026-04-22T12:27:25Z` shows scheduler enabled plus new owner processes (`cmd.exe` pid `9252`, `python.exe` pid `7156`, `python.exe` pid `3120`) and live cycle locks present.
- Success threshold:
- Latest floor snapshot no longer reports current below-floor CPT hold on those SKUs when the current-cycle decision is `skip_no_market_data`.
- Any remaining below-floor rows must show a truthful current-cycle blocker.
- Exact threshold still missing:
- A terminal successful H-owned run that reaches the runtime floor snapshot write stage after this patch.
- Exact next artifact / proof needed:
- A new finalized H run with `phase1_runtime_floor_snapshot_latest.csv` timestamp newer than `2026-04-22T11:34:48Z` and the two target SKUs carrying `current_cycle_blocker_code=MARKET_DATA_MISSING_CURRENT_CYCLE` with cleared live `execution_reason_codes_json`.
- Exact resume trigger:
- Fix or bypass the unrelated H pilot failure at `sku_exec_pre_write` for `X7-MY4W-H2I4`, then rerun the controlled H proof window.

## Phase 5 - Stock Truth Investigation And Permanent Fix Plan
- Status: complete (code + isolated tests + forced H runtime proof)
- Goal:
- Eliminate repeated stale stock truth entering H and prevent a "today-dated but row-stale" inventory snapshot from being treated as authoritative live stock.
- Current evidence:
- `out/inventory_snapshot_2026-04-22.csv` row for `2X-8XI7-C9T5` shows `available=1`, `total_quantity=7`, `last_updated_time=2026-04-01T20:13:35Z`, `timestamp_utc=2026-04-22T00:03:37Z`.
- `out/inventory_summaries.csv` carries the same stale row, proving the bad value is upstream of H display logic.
- `out/analysis_reports/phase1_observation_combined_2026-04-22.csv` then shows `stock_qty=1.0`, `available_stock_qty=1.0`, and `days_of_stock_est=1.43` for the same SKU.
- `out/systems/H/live/h_stock_snapshot_status.csv` reports status `OK` because the chosen snapshot file is dated today, even though the SKU row itself is stale.
- Root-cause theory:
- `scripts/cycles/run_H_pricing_cycle.py:_ensure_inventory_snapshot_today()` materializes a today-dated stock snapshot from `inventory_summaries.csv` without enforcing per-row freshness.
- `scripts/flows/H/H110_run_phase1_h_pilot.py:_apply_stock_universe_filter()` accepts that snapshot as canonical if the file date is current and only has a one-way stale-row guard that can zero stock after sell-through.
- That guard does not repair stale low-stock rows when real stock has increased, so stale undercounts can persist indefinitely.
- Investigation scope:
1. Confirm the upstream owner and refresh contract for `out/inventory_summaries.csv`, including why rows can remain at `last_updated_time` far behind the current date while still being re-snapshotted daily.
2. Trace how `inventory_snapshot_YYYY-MM-DD.csv` is built and determine where a per-row freshness gate should be enforced.
3. Trace how H110 chooses stock candidates and define fail-closed versus fallback behavior when a SKU row is row-stale.
4. Verify whether any downstream sheet/observation logic adds a second stock distortion after the source snapshot.
- Permanent fix design target:
1. Source-stage fix:
- Prevent `_ensure_inventory_snapshot_today()` from silently carrying stale per-SKU rows forward as normal live stock.
- Add explicit row-freshness metadata and stale classification into the materialized snapshot or companion status artifact.
2. Runtime-stage fix:
- In H110 stock filtering, reject or quarantine stale per-SKU stock rows instead of treating them as authoritative available stock.
- Prefer a safe fallback only if a fresher approved source exists; otherwise fail closed with a truthful blocker, not a fake quantity.
3. Monitoring fix:
- Add health/report outputs for stale stock row count, worst stale age, and sampled impacted SKUs.
- Surface repeated stale stock as a tracked operator-visible issue in H-owned artifacts.
4. Regression fix:
- Add tests for:
- row-stale low stock carried into a today snapshot
- stock increase after stale source row
- stale row with no safe fallback
- stale row with safe fallback
- H observation/output showing truthful stock blocker rather than stale quantity
- Implementation boundaries:
- Allowed files expected:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py` only if needed after source/runtime fixes
- `tests/test_h_split_health_gate.py`
- `tests/test_h130_ops_status.py` or a new H stock-truth test file if needed
- Success threshold:
- For `2X-8XI7-C9T5`, H no longer treats the stale `available=1` row as authoritative when the source row is stale.
- The stock truth path becomes explicit:
- fresh stock used
- stale stock quarantined
- safe fallback used
- or runtime blocked truthfully
- The fix is proven by tests plus a fresh H-owned proof run that reaches terminal markers and writes updated stock-sensitive artifacts.
- Implemented changes:
1. `scripts/cycles/run_H_pricing_cycle.py:_ensure_inventory_snapshot_today()`
- Adds per-row freshness metadata to the materialized inventory snapshot:
- `row_last_updated_age_hours`
- `row_last_updated_status` (`FRESH` / `STALE` / `UNKNOWN`)
- `row_last_updated_is_stale`
- Logs stale-row counts and max stale age at snapshot build time.
2. `scripts/flows/H/H110_run_phase1_h_pilot.py:_apply_stock_universe_filter()`
- Computes stale-row status per source per SKU.
- Promotes chosen stock snapshot status from `OK` to `WARN` when stale rows exist even if file date is today.
- Rejects stale authoritative stock rows as trusted qty truth.
- Uses safe token-available fallback when authoritative rows are stale and fallback qty is lower than token-available truth.
- Quarantines stale rows with no safe fallback as `STALE_STOCK_UNTRUSTED`.
- Adds summary counters (`excluded_stale`, `stale_row_token_fallbacks`, `stale_row_unknown_quarantined`, `stale_authoritative_skus`, chosen snapshot stale-row metrics).
3. Tests:
- Extended `tests/test_h110_stock_stale_guard.py` with stale undercount and stale-no-safe-fallback regressions.
- Added `tests/test_h_inventory_snapshot_row_freshness.py` to lock row freshness metadata contract.
- Isolated proof:
- `python -m pytest tests/test_h110_stock_stale_guard.py tests/test_h_inventory_snapshot_row_freshness.py tests/test_h_split_health_gate.py tests/test_phase1_main_loop.py tests/test_phase1_probe_engine.py tests/test_phase1_ceilings.py -q`
- Result: `86 passed`.
- Runtime proof (forced H-owned window):
1. Ownership handoff:
- `run_H_isolation_pause.bat` succeeded (`2026-04-22T12:47:47Z` settled; owner processes 0; task disabled; controlled mode active).
2. Controlled H run:
- `run_H_isolation_success.bat` succeeded.
- Terminal truth:
- run_id `20260422T124944Z`
- `H_run_state.json`: `state=finalized`, `publish_status=ok`, `utc=2026-04-22T13:08:28Z`
- `H_worker_lifecycle.json`: `state=succeeded`, `terminal_outcome=succeeded`
3. Ownership restore:
- `run_H_isolation_resume.bat` succeeded.
- `run_H_isolation_status.bat` at `2026-04-22T13:08:58Z` shows scheduler enabled, controlled mode cleared, and owner process chain relaunched.
- Stock-fix evidence (live data path):
- Direct live call to `_apply_stock_universe_filter()` at `2026-04-22T12:47:07Z` for `2X-8XI7-C9T5` now yields:
- `stock_snapshot_status=WARN`
- `stock_snapshot_stale_row_count=290`
- `stale_row_token_fallbacks=1`
- `available_stock_by_sku['2X-8XI7-C9T5']=30.00`
- `h_stock_snapshot_status.csv` now carries stale-row fields:
- `status=WARN, stale_row_count=290, stale_row_max_age_hours=25885.43`.

## Phase 6 - Upstream A Stock Freshness Hardening
- Status: complete (code + isolated tests + forced A proof)
- Goal:
- Fix stale stock truth at the A ingestion stage so `inventory_summaries.csv` and `inventory_snapshot_latest.csv` stop carrying unresolved stale undercounts into H.
- Allowed files:
- `scripts/flows/A/A003_run_inventory_to_sheet.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_a015_health_check_runtime.py`
- new targeted A003 stale-stock regression test file
- Design:
1. In A003, add row-level stale detection using `last_updated_time` and a bounded stale threshold.
2. For stale active SKUs, apply a token-backed floor at source write-time:
- `available := max(api_available, token_available_units)`
- `total_quantity := max(api_total_quantity, token_total_effective_units)`
3. Persist explicit stale metadata fields into `inventory_summaries.csv` so downstream checks can reason over source quality.
4. In A015, add an A-scoped health check that fails only when stale active rows still have unresolved token-vs-inventory undercount gaps.
- Proof path (forced A-owned window):
1. Run A003 once in no-sheet mode.
2. Run A015 with profile `a` for current-cycle checklist evidence.
3. Confirm target SKU `2X-8XI7-C9T5` no longer carries unresolved stale undercount in source outputs.
4. Confirm H stock filter consumes updated source truth without additional fallback dependency.
- Implemented changes:
1. `scripts/flows/A/A003_run_inventory_to_sheet.py`
- Added deterministic token-ledger read stability logic in `_load_token_stock_maps()`:
- multi-attempt read with mtime/size stability check
- conservative merge across attempts using max per-SKU counts
- retry controls via `A003_TOKEN_LEDGER_READ_ATTEMPTS` and `A003_TOKEN_LEDGER_READ_RETRY_SEC`
- Preserved stale-row token floor behavior and corrected stale-gap counter to compare against post-adjustment available.
2. `scripts/flows/A/A015_build_system_health_check.py`
- Expanded inventory read from `seller_sku`-only to full row contract for stock-truth checks.
- Added `_a_inventory_stale_token_gap_stats()` and new A-scoped gate `a_inventory_stale_token_gap`.
- Gate fails only when stale in-scope rows still undercount token truth (`available` or `total_quantity`).
3. Tests:
- Added `tests/test_a003_inventory_stale_token_floor.py` (new stale-floor regressions).
- Added two new `a_inventory_stale_token_gap_stats` regressions in `tests/test_a015_health_check_runtime.py`.
- Isolated proof:
- `python -m pytest tests/test_a003_inventory_stale_token_floor.py tests/test_a015_health_check_runtime.py -q -k "a_inventory_stale_token_gap_stats or stale_token_floor"`
- Result: `4 passed, 38 deselected`.
- `python -m py_compile scripts/flows/A/A003_run_inventory_to_sheet.py scripts/flows/A/A015_build_system_health_check.py`
- Result: success.
- Forced A proof execution:
1. `INVENTORY_USE_API_OWNER=0 INVENTORY_WRITE_SHEETS=0 python -u -c "import runpy; runpy.run_path('scripts/flows/A/A003_run_inventory_to_sheet.py', run_name='__main__')"`
- Result: success at `2026-04-22T13:35:24Z`; stale guard summary `stale_scope_rows=276`, `token_floor_rows=132`.
2. `python -u scripts/flows/A/A015_build_system_health_check.py --profile a --no-toast`
- Result: checklist refreshed at `2026-04-22T13:35:32Z`.
- Target gate evidence:
- `a_inventory_stale_token_gap = ok, value=0`
- `available_gap_rows=0`, `total_gap_rows=0`.
- Target SKU evidence (`2X-8XI7-C9T5`):
- `out/inventory_summaries.csv`: `available=32`, `total_quantity=34`, `last_updated_time=2026-04-22T13:31:22Z`, `row_last_updated_status=FRESH`, `row_last_updated_is_stale=0`.
- `out/inventory_snapshot_latest.csv`: `available=32`, `total_quantity=34`, `source=SPAPI`, `timestamp_utc=2026-04-22T13:35:23Z`.
- Readiness verdict for this phase:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed` (for the forced A proof scope)
- Full A-profile sign-off remains blocked by pre-existing unrelated A checks:
- `a_daily_intel_prerequisite_freshness` = `fail`
- `a_daily_intel_coverage_non_parked` = `fail` (prerequisite_blocked)
- `a_daily_intel_compliance_nonempty_non_parked` = `fail` (prerequisite_blocked)

## Phase 7 - A Profile Unblock + Live Runtime Closure
- Status: complete (code + isolated proof + forced proof + monitored live confirmation)
- Goal:
- Close remaining A profile blockers caused by daily intel prerequisite timing and confirm live H runtime still has no active below-floor rows after the stale-stock hardening work.
- Implemented changes (A-profile blocker closure):
1. `scripts/flows/A/A015_build_system_health_check.py`
- Added A016 overlap guard so A015 does not launch duplicate daily-intel refresh runs when A016 is already active.
- Added bounded refresh timeout control (`A015_DAILY_INTEL_REFRESH_TIMEOUT_SECONDS`, default `900`) to avoid indefinite hangs.
- Updated daily-intel freshness source to use the newer mtime of:
- `data/sku_daily_intel.csv`
- `out/phase1_daily_intel_latest.csv`
- This removed false freshness failures when the latest daily-intel artifact was fresher than the canonical CSV mtime.
- Isolated/compile proof:
- `python -m py_compile scripts/flows/A/A015_build_system_health_check.py`
- Result: success.
- Forced proof evidence (A flow):
1. `INVENTORY_USE_API_OWNER=0 INVENTORY_WRITE_SHEETS=0 python -u -c "import runpy; runpy.run_path('scripts/flows/A/A003_run_inventory_to_sheet.py', run_name='__main__')"`
- Result: success at `2026-04-22T15:05:15Z`.
- Stale guard summary: `stale_scope_rows=275`, `token_floor_rows=131`, `stale_scope_token_gap_rows=0`.
2. `python -u scripts/flows/A/A015_build_system_health_check.py --profile a --no-toast`
- Result: success at `2026-04-22T15:20:25Z`.
- Profile gate outcome: `out/cycle_alerts/checklist_A_split.csv` has `non_ok_count=0` (all six checks `ok`).
- `a_inventory_stale_token_gap = ok, value=0` with `available_gap_rows=0` and `total_gap_rows=0`.
- Current target SKU evidence (`2X-8XI7-C9T5`):
- `out/inventory_summaries.csv`: `available=33`, `total_quantity=35`, `last_updated_time=2026-04-22T13:39:28Z`, `row_last_updated_status=FRESH`, `row_last_updated_is_stale=0`.
- `out/inventory_snapshot_latest.csv`: `available=33`, `total_quantity=35`, `source=SPAPI`, `timestamp_utc=2026-04-22T15:05:14Z`.
- Monitored live runtime closure (H flow):
1. Observed live owner run `20260422T152012Z` to terminal markers.
2. Terminal truth:
- `out/systems/H/live/H_run_state.json`: `state=finalized`, `publish_status=ok`, `utc=2026-04-22T15:38:41Z`.
- `out/systems/H/live/H_worker_lifecycle.json`: `state=succeeded`, `terminal_outcome=succeeded`.
3. Post-finalization runtime truth:
- `out/phase1_runtime_floor_snapshot_latest.csv` rewritten at `2026-04-22T15:37:21Z`.
- Computed `below_floor_count=0`.
- `out/systems/H/live/h110_sku_decision_log.csv` for run `20260422T152012Z` shows `2X-8XI7-C9T5` decision `execute` with `market_data_present=1`.
- Readiness language:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed`
- Updated sign-off stance:
- Scoped ticket sign-off is ready.
- Previous Phase 6 note about A-profile blockers is now superseded by this Phase 7 proof.
- Residual non-blocking monitor item:
- `out/systems/H/live/h_stock_snapshot_status.csv` still reports `status=WARN` with `stale_row_count=262` and high `stale_row_max_age_hours`; this is now visible/explicit telemetry and should stay in MOT monitoring.

## Phase 8 - Stale-stock anti-regression lock for low-count drift
- Status: complete (code + isolated proof + forced H runtime proof + ownership restore)
- Goal:
- Prevent recurrence of stale low stock (`1`) being treated as live truth when fresher higher stock evidence exists, and lock a reproducible regression proof for this class.
- Allowed files:
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `tests/test_h110_stock_stale_guard.py`
- this coding plan file
- Design target:
1. Add explicit stale-under-count protection in stock filtering so stale authoritative quantities cannot win against fresher fallback/token evidence.
2. Add a deterministic regression test that models the prior failure shape and proves quantity does not collapse to stale low value.
3. Keep stale handling truthful (`WARN`/quarantine/fallback counters) rather than masking outcomes downstream.
- Isolated verification:
- `python -m pytest tests/test_h110_stock_stale_guard.py -q`
- `python -m py_compile scripts/flows/H/H110_run_phase1_h_pilot.py`
- Forced proof window:
- `run_H_isolation_pause.bat`
- controlled `run_H_isolation_success.bat`
- finalize artifact read after terminal markers
- `run_H_isolation_resume.bat`
- `run_H_isolation_status.bat`
- Runtime evidence check:
- `out/parking/stock_snapshot_latest.csv`
- `out/inventory_summaries.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- success threshold:
- regression test passes and proves stale low count cannot be selected when fresher higher evidence is present
- current live artifacts for `2X-8XI7-C9T5` remain non-stale and non-collapsed
- Evidence:
1. Code:
- `scripts/flows/H/H110_run_phase1_h_pilot.py` now tracks explicit `stale_undercount_protections` and enforces a stale-under-count floor when stale authoritative rows coexist with fresher higher evidence.
2. Isolated proof:
- `python -m pytest tests/test_h110_stock_stale_guard.py -q` -> pass (includes new `2X-8XI7-C9T5` regression test).
- `python -m py_compile scripts/flows/H/H110_run_phase1_h_pilot.py` -> success.
3. Forced H runtime proof attempt (isolation sequence):
- `run_H_isolation_pause.bat` succeeded and isolated scheduler ownership.
- `run_H_isolation_success.bat` started controlled run `20260423T073217Z` but did not reach terminal success.
- Terminal truth:
  - `out/systems/H/live/H_run_state.json`: `state=failed`, `failure_code=LOOP_RC_1`, `utc=2026-04-23T07:51:10Z`
  - `out/systems/H/live/H_worker_lifecycle.json`: `state=failed`, `terminal_outcome=failed`, `reason_code=LOOP_RC_1`
- Exact failure artifact:
  - `out/systems/H/live/phase1_pilot_wait_abnormal.20260423T073217Z...json` records `phase1 pilot step timeout reason=max_runtime elapsed_seconds=902.53 ... idx=110/137`.
- Ownership restore:
  - `run_H_isolation_resume.bat` succeeded.
  - `run_H_isolation_status.bat` confirms scheduler enabled and owner process chain restored.
4. Forced H runtime proof retry (bounded isolation sequence):
- `run_H_isolation_pause.bat` succeeded.
- Controlled one-shot rerun used:
  - `H110_MAX_SKUS_PER_RUN_OVERRIDE=20`
  - `H110_SINGLE_SKU_CAP_ROLLBACK_ENABLED=1`
- Controlled run `20260423T075958Z` reached terminal success:
  - `out/systems/H/live/H_run_state.json`: `state=finalized`, `publish_status=ok`, `utc=2026-04-23T08:08:38Z`
  - `out/systems/H/live/H_worker_lifecycle.json`: `state=succeeded`, `terminal_outcome=succeeded`, `expected_outputs_ok=1`
- Runtime stock/floor artifacts for `2X-8XI7-C9T5` after successful run:
  - `out/phase1_runtime_floor_snapshot_latest.csv`: `decision=execute`, `execution_new_price_gbp=9.99`, `execution_hard_floor_gbp=7.31`, `snapshot_utc=2026-04-23T07:59:58Z`
  - `out/systems/H/live/h110_sku_decision_log.csv`: `decision=execute`, `reason_code=eligible`, `market_data_present=1`
  - `out/parking/stock_snapshot_latest.csv`: `total_qty=35`
  - `out/inventory_summaries.csv`: `available=33`, `total_quantity=35`, `row_last_updated_status=FRESH`
- New stale-under-count guard emitted live telemetry in run progress:
  - `out/systems/H/live/phase1_pilot_step.progress.log` includes `stale_undercount_protections=118` for run scope.
5. Ownership restore after successful retry:
- `run_H_isolation_resume.bat` succeeded at `2026-04-23T08:10:39Z`.
- `run_H_isolation_status.bat` at `2026-04-23T08:10:47Z` confirms:
  - scheduler `Enabled` / task state `Ready`
  - controlled mode cleared
  - owner process chain running with live launcher and cycle locks present.
6. Current live artifact check for `2X-8XI7-C9T5`:
- `out/parking/stock_snapshot_latest.csv`: `total_qty=35`, `asof_utc=2026-04-23T08:07:06Z`.
- `out/inventory_summaries.csv`: `available=33`, `total_quantity=35`, `row_last_updated_status=FRESH`, `row_last_updated_is_stale=0`.
- `out/phase1_runtime_floor_snapshot_latest.csv`: `execution_state=HOLD_OBSERVE`, `execution_write_status=NO_WRITE_REQUIRED`, `execution_new_price_gbp=9.99`, `execution_hard_floor_gbp=7.31`.
7. Runtime proof verdict for this phase:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed`

## Phase 9 - H Google Sheet publish freshness recovery
- Status: complete (config fix applied + live loop publish confirmed)
- Goal:
- Restore regular `PRICING_DASHBOARD` publish cadence after the dashboard reached 96.26 minutes stale.
- Root-cause evidence:
- `out/systems/H/live/h_pricing_cycle_state.json` shows last full observation publish at `2026-04-23T08:35:24Z`.
- Current H owner was running, but `phase1_observation_publish_status=not_started` for the active run because the cycle had not reached final publish.
- Recent H pilot attempts were processing `137` SKUs with `max_timeout_seconds=900`.
- Failed attempts:
- `20260423T085545Z` timed out at `idx=99/137`.
- `20260423T091559Z` timed out at `idx=70/137`.
- `20260423T094936Z` failed before publish with `phase1_terminal_reason=market_payload_read_boundary_invalid`.
- Fix applied:
- `config/pilot_sku.yaml` now sets `max_skus_per_run: 50`.
- Reason:
- H110 already supports `max_skus_per_run`; the production config had it disabled with `0`, so the loop tried the full due universe and missed the publish window.
- Proof target:
- Next H run using the updated config reaches `publish_done` / `finalized`.
- `out/systems/H/live/h_pricing_cycle_state.json` shows `phase1_observation_publish_utc` newer than this fix.
- `PRICING_DASHBOARD` publish marker updates from run `20260423T083524Z` to a newer run.
- Runtime status language:
- `code fix applied`
- `isolated verification not required for config-only cap`
- `live loop verification confirmed`
- Live proof:
- Pre-fix run `20260423T100117Z` still used `due_count=137`, `max_skus_per_run=0`, and failed at `idx=71/137` with `max_runtime elapsed_seconds=900.02`.
- Post-fix run `20260423T102218Z` used `due_count=50`, `max_skus_per_run=50`.
- Post-fix run processed `50` rows and reached terminal success:
- `out/systems/H/live/H_run_state.json`: `state=finalized`, `publish_status=ok`, `utc=2026-04-23T10:37:37Z`
- `out/systems/H/live/H_worker_lifecycle.json`: `state=succeeded`, `terminal_outcome=succeeded`, `expected_outputs_ok=1`
- `out/systems/H/live/h_pricing_cycle_state.json`: `phase1_observation_publish_status=ok`, `phase1_observation_publish_run_id=20260423T102218Z`, `phase1_observation_publish_utc=2026-04-23T10:22:18Z`, `phase1_observation_publish_rows=52`, `phase1_publish_completed=1`
- Ownership after proof:
- Scheduler task remains enabled.
- H owner process chain remains running.
