# Runbook

## Purpose
- What this plan or system does:
  - gives the working order for building the new H/F learning loop without mixing one-off evidence work into live daily owners too early

## Standard run order
```powershell
# 1) Read the active task documents first
Get-Content plans\active\h-f-feedback-learning-loop-v1\PROJECT_BRIEF.md
Get-Content plans\active\h-f-feedback-learning-loop-v1\RESEARCH_REPORT_2026-04-17.md
Get-Content plans\active\h-f-feedback-learning-loop-v1\CODING_PLAN.md
Get-Content plans\active\h-f-feedback-learning-loop-v1\FROZEN_INPUT_MANIFEST.md
Get-Content plans\active\h-f-feedback-learning-loop-v1\PHASE_SCORECARD.md

# 2) Read the current evidence sources
Get-Content out\cycle_alerts\checklist_H.csv -TotalCount 40
Get-Content out\analysis_reports\f_backtest_calibration_set_latest.md -TotalCount 80
Get-Content out\analysis_reports\f_sales_history_validation_latest.csv -TotalCount 5
Get-Content out\h_strategy_outcome_daily.csv -TotalCount 20
Get-Content out\hos_daily_market_snapshot_latest.csv -TotalCount 5
Get-Content out\systems\F\live\f_screening_row_state_live.csv -TotalCount 5
Get-Content out\systems\F\history\feeder_approval_decisions_log.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_approval_queue_live.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_legacy_scrape_evidence_live.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_legacy_chart_daily_raw_live.csv -TotalCount 5

# 3) After prep-gate code exists, freeze the input set first
pytest tests\test_hf_learning_prep_freeze.py -q
python -m py_compile scripts\one_off\HF000_prep_freeze_learning_inputs.py tests\test_hf_learning_prep_freeze.py
python scripts\one_off\HF000_prep_freeze_learning_inputs.py

# 4) After Batch 000 code exists, run the foundation builder and its tests
pytest tests\test_hf_learning_foundation.py -q
python -m py_compile scripts\one_off\HF000_build_learning_foundation.py tests\test_hf_learning_foundation.py
python scripts\one_off\HF000_build_learning_foundation.py

# 5) After Batch 001 code exists, run the joined-baseline builder and its tests
pytest tests\test_hf_learning_baseline.py -q
python -m py_compile scripts\one_off\HF001_build_learning_baseline.py tests\test_hf_learning_baseline.py
python scripts\one_off\HF001_build_learning_baseline.py

# 6) If scrape coverage is weak, do not refresh it inside this ticket unless the freeze is intentionally reset
python scripts\one_off\F007_prepare_targeted_rescrape_subset.py --supplier-id <supplier_id> --max-rows 25
python scripts\one_off\F007_prepare_targeted_rescrape_subset.py --supplier-id <supplier_id> --max-rows 25 --apply-changes
$env:F061_MODE='data_collection'
python scripts\flows\F\F061_run_legacy_first_checks_local.py --supplier-id <supplier_id> --max-rows 25 --scrape-mode legacy_module

# 7) For sampled deep validation only
python scripts\one_off\F008_capture_full_bbp_evidence_pack.py --asin-pack-path <asin_pack_csv> --max-asins 10 --passes 3

# 8) After Batch 002 code exists, build alignment outputs
pytest tests\test_hf_learning_alignment.py -q
python -m py_compile scripts\one_off\HF002_build_learning_alignment.py tests\test_hf_learning_alignment.py
python scripts\one_off\HF002_build_learning_alignment.py

# 9) After Phase 3 health code exists, build health checklist
pytest tests\test_hf_learning_health_checks.py -q
python -m py_compile scripts\one_off\HF003_build_learning_health_checks.py tests\test_hf_learning_health_checks.py
python scripts\one_off\HF003_build_learning_health_checks.py

# 10) After Phase 4 code exists, build F shadow calibration (shadow-only)
pytest tests\test_f080_build_feedback_calibration_shadow.py -q
python -m py_compile scripts\flows\F\F080_build_feedback_calibration_shadow.py tests\test_f080_build_feedback_calibration_shadow.py
python scripts\flows\F\F080_build_feedback_calibration_shadow.py

# 11) After Phase 5 code exists, build operator report
pytest tests\test_hf_learning_operator_report.py -q
python -m py_compile scripts\one_off\HF005_build_learning_operator_report.py tests\test_hf_learning_operator_report.py
python scripts\one_off\HF005_build_learning_operator_report.py

# 12) If a phase edits H runtime-owned code, drain H owner before editing
$requestId = "HF_PHASE5_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$marker = "requested_by=controlled_restart_gate|pid=$PID|ts=" + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + "|reason=overnight_restart_eval|request_id=$requestId"
Set-Content -Path out\locks\maintenance.requested -Value $marker -NoNewline -Encoding ascii
while (-not (Test-Path out\systems\H\live\H_restart_drain.ready)) { Start-Sleep -Seconds 5 }
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_H_pricing_cycle|run_H_pricing_cycle_guarded|run_H_cycle\\.bat' }

# 13) After isolated proof, restore H ownership
Remove-Item out\locks\maintenance.requested -ErrorAction SilentlyContinue
Remove-Item out\systems\H\live\H_restart_drain.ready -ErrorAction SilentlyContinue
cmd /c run_H_cycle.bat
Get-Content out\systems\H\live\H_launcher.heartbeat -TotalCount 1
Get-Content out\systems\H\live\H_runtime_status.json -TotalCount 20
```

## Validation steps
- Step 1:
  - confirm the active phase and allowed files in `CODING_PLAN.md`
- Step 2:
  - confirm `FROZEN_INPUT_MANIFEST.md` is locked before any coding phase runs
- Step 3:
  - run only the narrow tests for the current batch
- Step 4:
  - confirm the identity bridge and frozen assumption snapshots exist before any joined marts are built
- Step 5:
  - confirm new outputs have nonzero rows and reconciled keys
- Step 6:
  - rerun the same builder or check against the same frozen inputs and confirm the result shape is unchanged
- Step 7:
  - update `PHASE_SCORECARD.md` before moving to the next phase
- Step 8:
  - confirm health checks exist before any promotion into live owner paths
- Step 9:
  - if a fresh scrape is needed, route it through `F007` plus `F061`, not by adding a duplicate scrape path
- Step 10:
  - for H-runtime edits, use the controlled restart-drain marker and wait for `H_restart_drain.ready` before touching H-owned runtime files

## Expected outputs
- Output:
  - `hf_learning_identity_bridge_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
- What good looks like:
  - candidate, supplier, ASIN, and SKU links are explicit and unresolved rows remain visible

- Output:
  - `hf_learning_assumption_snapshots_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_assumption_snapshots_latest.csv`
- What good looks like:
  - approval or handoff assumptions are frozen with stage and source timestamps

- Output:
  - `hf_learning_foundation_metrics_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
- What good looks like:
  - bridge coverage and stage coverage metrics are explicit and repeatable across reruns

- Output:
  - `hf_learning_market_facts_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_market_facts_latest.csv`
- What good looks like:
  - one reconciled row per observation key with market and economics anchors

- Output:
  - `hf_learning_action_outcomes_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_action_outcomes_latest.csv`
- What good looks like:
  - each row clearly shows whether H was eligible, decided, attempted, and applied

- Output:
  - `hf_learning_alignment_30d_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
- What good looks like:
  - expected vs actual differences are visible with a reason bucket

- Output:
  - `hf_learning_factor_impacts_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_factor_impacts_latest.csv`
- What good looks like:
  - discrepancy buckets, sample size, and rescrape trigger decisions are explicit

- Output:
  - `hf_learning_health_checklist_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_health_checklist_latest.csv`
- What good looks like:
  - schema, row guards, freshness, and trigger-consistency checks are visible in one checklist

- Output:
  - `feeder_feedback_calibration_live.csv`
- Path:
  - `out/systems/F/live/feeder_feedback_calibration_live.csv`
- What good looks like:
  - factor outputs are populated, sample-sized, and clearly shadow-only

- Output:
  - `hf_learning_operator_report_latest.csv`
- Path:
  - `out/reports/hf_learning_operator_report_latest.csv`
- What good looks like:
  - H behavior, scrape coverage, alignment drift, and health status are visible in one operator-facing file

- Output:
  - `hf_learning_scrape_gap_report_latest.csv`
- Path:
  - `out/analysis_reports/hf_learning_scrape_gap_report_latest.csv`
- What good looks like:
  - every rescrape recommendation tells us exactly why it is needed and which existing owner path should run it

## Health checks
- Check:
  - identity bridge truth
- Pass condition:
  - required key columns present, bridge coverage reported, unresolved rows explicit
- Warning condition:
  - some rows unresolved but visible and quantified
- Fail condition:
  - silent drops, ambiguous bridges with no flag, or missing key columns

- Check:
  - frozen assumption snapshot truth
- Pass condition:
  - snapshot rows carry source stage and source timestamp for expected assumptions
- Warning condition:
  - partial stage coverage but gaps are explicit
- Fail condition:
  - alignment would compare actuals against rewritten or current assumptions

- Check:
  - joined market facts schema
- Pass condition:
  - required columns present, keys unique, nonzero rows
- Warning condition:
  - thin sample or partial source coverage
- Fail condition:
  - zero-row build, broken key contract, or missing required columns

- Check:
  - action outcome state integrity
- Pass condition:
  - eligible / decision / attempted / applied flags are logically consistent
- Warning condition:
  - some source fields missing but rows still traceable
- Fail condition:
  - impossible state combinations or broken joins

- Check:
  - monthly alignment freshness
- Pass condition:
  - latest alignment is within the intended review window
- Warning condition:
  - nearing stale threshold
- Fail condition:
  - operator review relies on stale alignment

- Check:
  - scrape coverage and rescrape trigger truth
- Pass condition:
  - scrape gap report explains missing or stale coverage and points to the correct existing owner path
- Warning condition:
  - thin coverage or growing stale share
- Fail condition:
  - learning outputs rely on stale or missing scrape evidence with no explicit rescrape route

## Failure recovery
- If the frozen-input rule is broken:
  - stop the active phase
  - refresh the freeze manifest
  - restart scoring from Prep
- If H scoped evidence and aggregate evidence disagree:
  - use the newer scoped file for this ticket and record the aggregate file as stale context
- If F live backtest files are empty:
  - use the current analysis reports as the evidence baseline and record the owner-path gap honestly
- If fresh scrape is needed:
  - first prepare a controlled subset with `F007`
  - prefer `F061_MODE=data_collection` for learning-driven refreshes
  - then let `F061` own the scrape and contract writes
  - do not run `Webscrape.py` directly as the primary owner path for this task
- If bridge coverage is weak:
  - stop before alignment and fix the identity rules first
- If a phase touches H runtime-owned files:
  - use the controlled restart-drain marker payload that H launcher and worker recognize
  - wait for `out/systems/H/live/H_restart_drain.ready` before editing
  - restart only through `run_H_cycle.bat` after isolated proof passes
- If tests fail:
  - fix the earliest failing builder or contract first
- If row counts do not reconcile:
  - stop before adding reports or calibration outputs

## Archive note
- What to preserve when this plan is finished:
  - final identity bridge and frozen assumption snapshot schemas
  - final joined output schemas
  - reconciliation proof
  - monthly alignment method
  - promotion decision for each output
