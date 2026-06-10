# Execution Batch 002 Reply

## Status
- Complete / Partial / Failed:
  - Partial
- Checked against:
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002.md`

## Summary of changes
- Files added:
  - `scripts/one_off/H165_build_h_signoff_proof_pack.py`
  - `tests/test_h165_build_h_signoff_proof_pack.py`
- Files changed:
  - `scripts/one_off/H165_build_h_signoff_proof_pack.py` (BOM-safe provenance parsing fix)
- Behavior changed:
  - Batch 002 now has machine-generated sign-off packs with explicit gates.
  - Forced H proof chain executed end-to-end with terminal proof and scheduler ownership restore.
  - Stale interrupted marker `H_run_in_progress.txt` for `run_id=20260417T140406Z` was archived to clear false fail-closed one-shot exits:
    - `out/locks/archive/H_run_in_progress.20260417T141850Z.stale.20260417T140406Z.txt`

## Tests run
- Command:
  - `pytest tests/test_h165_build_h_signoff_proof_pack.py -q -p no:cacheprovider`
  - `python -m py_compile scripts/one_off/H165_build_h_signoff_proof_pack.py`
- Result:
  - pass (`1 passed`)
  - compile pass

## Proof
- Row counts:
  - proof pack (`candidate_ts_utc=2026-04-17T11:13:01Z`) reports:
    - `rows_since_candidate=671`
    - `same_target_rows=659`
    - `same_target_applied=0` (gate pass)
    - `raw_legacy_multi_seller_population=604`
    - `effective_chaseable_multi_seller_population=0`
    - `suppression_reactivation rows=22 success=0 expired_share_pct=72.73`
    - `controlled_exit rows=0 success=0`
- Health rows:
  - fresh H health snapshot captured:
    - `out/health_status_H.csv` latest: `2026-04-17T14:32:51Z` (`WARN fail=0 warn=2`)
    - `h_ceiling_effective_floor_integrity=ok,value=0` (gate pass)
- Output paths:
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143546Z.json` (`effective_chaseable_population`)
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143546Z.csv`
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143633Z.json` (`raw_legacy_population`)
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143633Z.csv`
- Other evidence:
  - forced proof window sequence completed:
    - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
    - `.\run_H_isolation_pause.bat` (success)
    - `.\run_H_isolation_success.bat` (final terminal proof success after stale-marker archive)
    - terminal proof run: `run_id=20260417T142039Z`, `finalized/succeeded`
    - `python -m scripts.flows.A.A015_build_system_health_check --profile h --no-toast` wrote fresh H checklist/health (process rc `1` due warn policy)
    - `.\run_H_isolation_resume.bat` restored scheduler ownership and enabled scheduler task
  - run-chain proof in pack:
    - scheduler-owned runs after candidate: `13`
    - scheduler-owned succeeded: `12`
    - max consecutive succeeded streak: `12` (10-run gate pass)

## Monitoring outcome
- Monitored validation:
  - completed for Batch 002 window (forced proof + proof-pack scoring)
- Checks performed:
  - forced H isolation proof chain
  - H-scoped A015 refresh
  - scheduler resume and owner restoration check
  - proof-pack scoring on both denominator contracts
- Latest evidence:
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143546Z.json`
  - `out/analysis_reports/h_signoff_proof_pack_20260417T143633Z.json`
- Threshold met:
  - No
- If not met, exact blocker:
  - multi-seller threshold failed on both contracts:
    - effective contract: `denominator=0` (`effective_chaseable_multi_seller_population=0`)
    - raw contract: `denominator=604` but `success_per_100=0.0`
  - suppression threshold failed:
    - `rows=22` (<30), `success=0` (<2), `expired_share_pct=72.73` (>55)
  - controlled-exit threshold failed:
    - `rows=0` (<10), `success=0`
  - live seller-detail gate failed:
    - `amazon_missing_pressure=warn,current_value=3,threshold=3` (snapshot `2026-04-17T14:20:39Z`)
- Next automatic step or park rule:
  - Parked pending next H proof window.
  - Resume trigger:
    - rerun `H165` proof pack after next finalized H run where seller-detail alert snapshot refreshes and suppression pending window moves.
- User-facing interruption sent:
  - no (batch-level summary only)

## Issues found
- `run_H_isolation_success.bat` initially failed (`terminal_success_not_proven`) because:
  - stale interrupted run marker (`20260417T140406Z`) kept one-shot in fail-closed path
  - launcher auto-detach hid terminal progress
- resolved by:
  - archiving stale marker (path above)
  - rerunning isolated success with `H_LAUNCHER_AUTO_DETACH=0`
- A015 command exited non-zero (`rc=1`) under warn-exit policy while still writing fresh H profile artifacts

## Next batch notes
- Remaining work:
  - hold plan active until conversion gates and live-alert gate pass on fresh proof pack
  - decide and document WARN exception-list disposition (or clear WARNs) before archive
- Risks discovered:
  - conversion gates currently fail even with proven runtime integrity
  - one stale interrupted run can poison one-shot validation until marker reconciliation is done
