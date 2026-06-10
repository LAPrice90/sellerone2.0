# Coding Plan

## Execution memory
- Plan slug:
  - `h-f-data-cleanup-2026-04-18`
- Current phase:
  - `Complete - sign-off closed`
- Overall mode:
  - all planned phases are complete
  - Phase 1 and 2 live-loop proof is confirmed from owned runtime evidence
  - Phase 3 closed via explicit no-overlap proof path
  - Phase 4 rebuild and rescoring closed with `hf_fail=0` and `hf_warn=0`
- Automatic next step when execution begins:
  - none for this ticket
  - open follow-on overlap-growth ticket (separate scope)

## Allowed files by phase
- Phase 1:
  - `scripts/flows/A/A015_build_system_health_check.py`
  - H helper or storage files only if needed to expose live sample freshness truth
  - tests for A015 or H freshness helpers
- Phase 2:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - H scoped tests for ceiling and rollup integrity
- Phase 3:
  - `scripts/one_off/HF000_build_learning_foundation.py`
  - tests for HF foundation and identity bridging
- Phase 4:
  - `scripts/one_off/HF001_build_learning_baseline.py`
  - `scripts/one_off/HF002_build_learning_alignment.py`
  - `scripts/one_off/HF003_build_learning_health_checks.py`
  - `scripts/one_off/HF005_build_learning_operator_report.py`
  - related tests
- Phase 5:
  - `plans/archive/2026/h-f-data-cleanup-2026-04-18/PLAN_STATUS.md`
  - `plans/archive/2026/h-f-data-cleanup-2026-04-18/CODING_PLAN.md`
  - sign-off notes only

## Tests and proof by phase
- Phase 1 isolated proof:
  - targeted H split-gate tests pass
  - runtime state now carries live strategy sample-size values plus stale-vs-checklist flag
- Phase 1 live proof:
  - controlled isolation run finalized cleanly:
    - `H_run_state.json`: `run_id=20260418T081717Z`, `state=finalized`, `publish_status=ok`
    - `H_run_in_progress.txt` cleared after terminal success
    - state fields present:
      - `h_strategy_sample_live_status=ok`
      - `h_strategy_sample_live_stale_vs_checklist=1`
- Phase 2 isolated proof:
  - targeted H tests pass
  - local rebuild shows:
    - `effective ceiling below floor = 0`
    - no impossible daily rows
    - ceiling-event reason codes include explicit conflict/input buckets
- Phase 2 live proof:
  - latest H run slice includes bucketed reason codes and floor-safe outcomes:
    - latest run id: `20260418T102258Z`
    - `bad_floor_ceiling=0`
    - `CEILING_CONFLICT_BUCKET_*` and `CEILING_INPUT_BUCKET_*` present
- Phase 3 isolated proof:
  - HF foundation tests pass
  - repeat build is deterministic
  - unresolved rows are explicitly bucketed by cause
- Phase 4 isolated proof:
  - HF baseline, alignment, health, and operator-report tests pass
  - repeat builds stay deterministic
  - missing-rate output is rescored from rebuilt inputs
- Phase 5 live proof:
  - pass criteria are met and sign-off is recorded in `PLAN_STATUS.md`
  - runtime ownership remains healthy:
    - `out/H_pricing_cycle.lock` and `out/systems/B/live/B_cycle.lock` are fresh
    - latest terminal marker:
      - `out/H_cycle_last_terminal_info.txt` -> `state=finalized`, `publish_status=ok`

## Monitoring targets
- During execution, watch:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
  - `out/analysis_reports/hf_learning_health_checklist_latest.csv`
  - `out/reports/hf_learning_operator_report_latest.csv`

## Poll cadence
- Default monitored validation cadence:
  - first check at `+5 minutes`
  - second check at `+10 minutes`
  - then every `+15 minutes`
  - stop at `+60 minutes` unless a phase defines a tighter bound

## Success thresholds
- Phase 1:
  - stale H checklist counts can no longer be mistaken for current H live counts
- Phase 2:
  - `effective ceiling below floor = 0`
  - no impossible daily rollup rows
- Phase 3:
  - one of:
    - `identity_rows_resolved > 0`
    - explicit no-overlap proof path:
      - `identity_rows_with_asin > 0`
      - `identity_rows_asin_in_h_scope = 0`
      - `identity_rows_asin_not_in_h_scope = identity_rows_with_asin`
      - `identity_asin_h_scope_overlap_rate = 0.0000`
- Phase 4:
  - `hf_scrape_gap_missing_rate <= 0.80`
  - or explicit root-cause proof that the remainder is non-scraper scope
- Ticket sign-off:
  - all required pass criteria in `PLAN.md` satisfied

## Timeout rule
- If a phase cannot hit its threshold inside the bounded proof window:
  - record exact evidence seen
  - record exact threshold still missing
  - record the next artifact needed
  - mark status as `parked pending next proof window`

## Execution constraints
- Do not run any `A` script manually unless the user explicitly asks
- Do not overlap manual `B` work with the live B owner
- Keep one-off builders out of daily loops
- Fix earliest-stage truth, not downstream report cosmetics
