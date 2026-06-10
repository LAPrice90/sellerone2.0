# Execution Batch 002

## Purpose
- One-sentence outcome for this batch:
  - produce an undeniable H sign-off proof pack for the current candidate, or fail truthfully with exact missing proof

## Scope guardrails
- Only do:
  - proof-pack generation
  - fresh H-scoped health proof after the final candidate timestamp
  - live runtime proof capture
  - denominator-contract lock for final sign-off scoring
  - explicit WARN disposition for archive readiness
- Do not change:
  - Google Sheets
  - local DB
  - daily-loop repricer logic
  - scheduler ownership design
  - threshold values silently inside chat only
- Do not add:
  - new daily-loop steps
  - one-off logic inside runtime loops
  - metric-contract changes without writing them into plan files

## Files allowed to change
- `plans/active/h-repricer-ceiling-floor-conversion-v2/CODING_PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN_STATUS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002_REPLY.md`
- optional proof-only additions:
  - `scripts/one_off/H165_build_h_signoff_proof_pack.py`
  - `tests/test_h165_build_h_signoff_proof_pack.py`

## Inputs to read first
- `AGENTS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/CODING_PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN_STATUS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/SIGN_OFF_REVIEW_2026-04-17.md`
- supporting files:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/health_status_H.csv`
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/systems/H/live/H_run_state.json`
  - `out/systems/H/live/H_worker_lifecycle.json`
  - `out/systems/H/live/h_seller_detail_measurement_alerts_latest.csv`

## Candidate lock
- Final candidate timestamp:
  - `2026-04-17T11:13:01Z`
- Final candidate code surface:
  - `scripts/phase1/phase1_probe_engine.py`
  - `tests/test_phase1_probe_engine.py`
- Rules:
  - no stale artifact older than this timestamp may be used as final sign-off proof
  - if any further runtime-logic code change lands, reset the candidate timestamp and restart this batch

## Tasks
### Task 1
- Goal:
  - lock the metric contract that sign-off will use
- Required output:
  - written decision in plan docs stating whether `multi_seller_ladder_cap` is judged on:
    - raw legacy population
    - effective chaseable population
- Notes:
  - both populations must still be reported in the proof pack
  - no silent denominator switch is allowed

### Task 2
- Goal:
  - generate a proof pack that can be checked without manual CSV archaeology
- Required output:
  - machine-readable proof file under `out/analysis_reports/`
  - human-readable proof summary in the reply doc
- Minimum proof-pack contents:
  - candidate timestamp
  - latest H-scoped health snapshot timestamp
  - per-run terminal outcomes after candidate timestamp
  - 10-run success chain status
  - `same_target_applied`
  - raw multi-seller rows
  - reclassified non-action hold rows
  - effective chaseable multi-seller rows if derived
  - suppression rows, success count, expired share
  - controlled-exit rows and success state
  - current live seller-detail alert states

### Task 3
- Goal:
  - refresh H-scoped truth proof on artifacts newer than the candidate timestamp
- Required command sequence:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python -m scripts.flows.A.A015_build_system_health_check --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- Notes:
  - this batch must not claim sign-off using the older `2026-04-17T10:20:22.152493+00:00` H health snapshot

### Task 4
- Goal:
  - capture undeniable live runtime ownership proof
- Required proof:
  - 10 consecutive scheduler-owned H runs after the candidate timestamp finalize as `succeeded`
  - owner chain is restored after isolated proof
- Notes:
  - isolated proof alone is not enough for final sign-off

### Task 5
- Goal:
  - produce the sign-off decision
- Decision rule:
  - if every gate passes, archive
  - if any gate fails or remains unproven, park with exact missing proof and exact resume trigger

## Tests
- Command:
  - if a proof-builder script is added:
    - `pytest tests/test_h165_build_h_signoff_proof_pack.py -q -p no:cacheprovider`
    - `python -m py_compile scripts/one_off/H165_build_h_signoff_proof_pack.py tests/test_h165_build_h_signoff_proof_pack.py`
- Expected result:
  - proof-builder tests pass if the script exists
  - if no script is added, this batch has no new code-test surface

## Monitoring plan
- Live proof needed:
  - yes
- Forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python -m scripts.flows.A.A015_build_system_health_check --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- Artifacts to poll:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/health_status_H.csv`
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/systems/H/live/H_run_state.json`
  - `out/systems/H/live/H_worker_lifecycle.json`
  - `out/systems/H/live/h_seller_detail_measurement_alerts_latest.csv`
  - proof-pack outputs under `out/analysis_reports/`
- Poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+180 minutes` or until 10 scheduler-owned runs finalize
- Success threshold:
  - H health snapshot timestamp is later than `2026-04-17T11:13:01Z`
  - `h_ceiling_effective_floor_integrity=ok,value=0`
  - 10 consecutive scheduler-owned H runs after the candidate finalize as `succeeded`
  - `same_target_applied=0`
  - proof pack reports both raw and reclassified/effective multi-seller populations
  - chosen denominator contract is written explicitly before archive
  - chosen sign-off contract thresholds are met:
    - `multi_seller_ladder_cap` on the chosen basis
    - `suppression_reactivation` rows `>=30`, success `>=2`, expired share `<=55%`
    - `controlled_exit` rows `>=10` and success semantics proven
  - remaining WARNs are either cleared or explicitly exception-listed with reason, owner, and review checkpoint
- Timeout rule:
  - park as `pending next H proof window` with:
    - exact missing artifact
    - exact failing threshold
    - exact next proof boundary
- Fallback if forced proof is blocked:
  - record the exact ownership blocker, stale marker, or resume blocker before deferring
- Next phase after success:
  - archive this plan
- Notification mode:
  - passive
- User interruption threshold:
  - sign-off earned, contradiction, new/worse alert, timeout park, or approval-required scope change

## Proof required
- Fresh health rows:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/health_status_H.csv`
- Runtime proof:
  - 10 scheduler-owned finalized/succeeded runs after candidate timestamp
  - owner chain restored after isolated proof
- Behavior proof:
  - `same_target_applied=0`
  - raw multi-seller count
  - reclassified non-action hold count
  - effective chaseable count if used
  - suppression sample and success counts
  - controlled-exit sample and success counts
- Output files:
  - `out/analysis_reports/h_signoff_proof_pack_<timestamp>.json`
  - `out/analysis_reports/h_signoff_proof_pack_<timestamp>.csv`
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002_REPLY.md`
- Notes:
  - do not call the batch complete until the proof pack is built from artifacts newer than the candidate timestamp

## Completion checklist
- [ ] Scope held
- [ ] Files changed only in allowed set
- [ ] Fresh H-scoped health proof captured after candidate timestamp
- [ ] 10 scheduler-owned finalized/succeeded runs captured
- [ ] Proof pack generated
- [ ] Denominator contract written explicitly
- [ ] Reply file updated
