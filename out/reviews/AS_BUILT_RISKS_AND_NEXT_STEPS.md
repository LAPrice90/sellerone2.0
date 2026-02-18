# AS-BUILT RISKS AND NEXT STEPS

## A) High-risk coupling points (with evidence)
- Shared health gate coupling: `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_C_cycle.py`, `scripts/run_E_cycle.py`, and `scripts/run_H_pricing_cycle.py` all invoke `scripts/A015_build_system_health_check.py` (global or profile modes), so one checklist issue can affect multiple cycles.
- Cross-cycle shared mutable artifacts in `out/`: `run_api_collection.py` writes listing/inventory/refund snapshots that are consumed by `scripts/run_H_pricing_cycle.py` and validated by `scripts/A015_build_system_health_check.py`.
- Shared lock namespace risk: both A and C default to `out/run_cycle.lock` via `RUN_LOCK_PATH` in `scripts/run_A_all.py` and `scripts/run_C_cycle.py`, creating coupling if launched concurrently.
- B cycle both computes and publishes from the same loop in `scripts/run_B_cycle.py` (`RUN_ORDER` + quiet-mode publish calls), combining transformation and outbound side effects in one process.
- H pilot path bridges multiple modules and subprocess boundaries: `scripts/run_H_pricing_cycle.py` -> `scripts/H110_run_phase1_h_pilot.py` -> `scripts/phase1_main_loop.py` + `scripts/phase1_storage.py`, increasing failure surface across shared CSV state.
- Google Sheets write coupling exists across many scripts (`scripts/A001_run_listings_to_sheet.py`, `scripts/A003_run_inventory_to_sheet.py`, `scripts/B001_run_orders_to_sheet.py`, `scripts/B002_run_pending_orders_to_sheet.py`, `scripts/B003_run_financial_events_level3.py`, `scripts/E010_publish_e_outputs.py`) with shared credential/env behavior.
- Split-health shadow/cutover state is shared through `out/cycle_alerts/flow_selftest_state.json` across A/B/E (`scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_E_cycle.py`) and separate state for H (`scripts/run_H_pricing_cycle.py`), creating multi-file mode coupling.
- Repair side effect coupling: `scripts/run_A_all.py` and `scripts/run_B_cycle.py` can call `scripts/B004_build_order_master.py` inside health handling paths, blending remediation into gate evaluation.

## B) Failure modes observed in code
- File IO and schema drift failures: many reads assume CSV existence/columns (`scripts/A015_build_system_health_check.py`, `scripts/run_H_pricing_cycle.py`, `scripts/B004_build_order_master.py`), and missing/invalid files frequently branch to fail/warn paths.
- External API failures propagate as runtime errors: SP-API/LWA calls raise on non-200 in `scripts/api/get_financial_events.py` and `run_api_collection.py`; H pricing live API calls use `spapi_get`/`spapi_patch_json` in `scripts/run_H_pricing_cycle.py`.
- Subprocess boundary failures can stop cycles: orchestrators use `subprocess.run(...)` extensively in `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_C_cycle.py`, `scripts/run_E_cycle.py`, and `scripts/run_H_pricing_cycle.py`.
- Lock contention/stale lock edge cases: lock files are used in `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_C_cycle.py`, `scripts/run_H_pricing_cycle.py`, and `scripts/api/spapi_owner.py`; stale PID recovery exists but depends on OS process checks.
- Maintenance-handoff timeout: A cycle waits for B maintenance readiness and raises timeout via `_wait_for_b_maintenance_ready()` in `scripts/run_A_all.py`.
- Freshness promotion can escalate WARN to FAIL: health freshness logic in `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_E_cycle.py`, and `scripts/run_H_pricing_cycle.py` treats stale-warning outputs as blocking failures.
- GSpread/API quota or network failures can interrupt publish/report steps in sheet-writing scripts (`scripts/B001_run_orders_to_sheet.py`, `scripts/B002_run_pending_orders_to_sheet.py`, `scripts/B003_run_financial_events_level3.py`, `scripts/E010_publish_e_outputs.py`).
- Environment misconfiguration (missing secrets/IDs) throws explicit failures via `require_env(...)` in `scripts/api/get_financial_events.py` and dependent callers (`run_api_collection.py`, H/B/A API scripts).

## C) Minimal stabilization plan (Phase 0 only, no refactor)
- Add a single structured per-step manifest for A runs in `scripts/run_A_all.py` (step start/end UTC, input file mtimes, return code, gate decision, run_id) written to `out/trace/A_run_manifest.jsonl`.
- Add equivalent per-cycle manifest in `scripts/run_B_cycle.py` including publish decisions and health snapshot source checksum to `out/trace/B_run_manifest.jsonl`.
- Add equivalent manifest in `scripts/run_C_cycle.py` and `scripts/run_E_cycle.py` so all orchestrators emit aligned step telemetry under `out/trace/`.
- Add dataset-level trace rows in `run_api_collection.py` (dataset name, row counts written, snapshot file names, lock acquisition outcome, API call counts) to `out/trace/api_collection_manifest.jsonl`.
- Add explicit input snapshot fingerprint capture in `scripts/run_H_pricing_cycle.py` before pilot execution (latest listing snapshot path/mtime/rowcount, state file mtime) to `out/trace/H_run_manifest.jsonl`.
- Add write-guard prechecks in `scripts/E010_publish_e_outputs.py` and sheet-writing B scripts (`scripts/B001_run_orders_to_sheet.py`, `scripts/B002_run_pending_orders_to_sheet.py`, `scripts/B003_run_financial_events_level3.py`) to log planned tab writes before execution.
- Extend `scripts/A015_build_system_health_check.py` output with provenance columns (`source_file`, `source_mtime_utc`, `source_rowcount`) for each check row to make gate outcomes reproducible.
- Add lock telemetry file appenders in `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_H_pricing_cycle.py`, and `scripts/api/spapi_owner.py` (`out/trace/lock_events.jsonl`) for acquire/release/steal/recovery events.
- Add schema-validation trace output for API collection contracts in `run_api_collection.py` (record required columns and missing column counts per snapshot) without changing current write logic.
- Add one canonical cycle correlation ID propagation field across A/B/C/E/H orchestrators (`scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_C_cycle.py`, `scripts/run_E_cycle.py`, `scripts/run_H_pricing_cycle.py`) written only as observability metadata (no behavioral changes).
