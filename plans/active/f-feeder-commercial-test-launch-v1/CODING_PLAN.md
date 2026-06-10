# Coding Plan

Date: 2026-04-22
Scope: F feeder commercial launch path from live price file through user-reviewed test orders and monitored learning

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Lock planning, operating rules, and start-to-finish control model | `plans/active/f-feeder-commercial-test-launch-v1/*`, `WORK_LOG.md` | docs review | no | completed |
| Phase 1 | Refresh the active supplier-wave baseline from current screening truth | `scripts/flows/F/F005_build_supplier_price_list_universal.py`, `scripts/flows/F/F060_build_legacy_sheet_review_pack.py`, `scripts/flows/F/F061_run_legacy_first_checks_local.py`, `scripts/flows/F/_schemas.py`, `tests/test_f005_build_supplier_price_list_universal.py`, `tests/test_f060_build_legacy_sheet_review_pack.py`, `tests/test_f061_run_legacy_first_checks_local.py`, new `scripts/one_off/F018_build_live_price_file_launch_pack.py`, new `tests/test_f018_build_live_price_file_launch_pack.py` | targeted F tests + one-off builder run | yes | completed |
| Phase 2 | Build fresh pass and near-miss review packs from the active supplier wave | `scripts/one_off/F018_build_live_price_file_launch_pack.py`, new `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`, related tests | targeted one-off tests | yes | completed |
| Phase 3 | Add operator decision capture and release-shortlist output | feeder decision/logging files, planned one-off shortlist builder, related tests | targeted F tests + shortlist builder run | yes | planned |
| Phase 4 | Move approved candidates into controlled PO handoff readiness | `scripts/flows/F/F050_build_feeder_po_handoff.py`, related F flow files and tests | targeted F050 tests + handoff proof | yes | planned |
| Phase 5 | Build post-launch monitoring and launch-cohort learning packs | planned one-off monitoring builders, F011/F013/F017 links, related tests | targeted one-off tests + runtime artifact proof | yes | planned |

## 2) Phase details

### Phase 0 - Planning lock
Goal:
- Create a fresh active plan folder for the commercial launch phase.
- Lock the operating rule that this is a conservative test-buy selector, not an exact predictor.
- Spell out the full controlled path from live supplier file to monitored test-buy learning.

Files allowed to change:
- `plans/active/f-feeder-commercial-test-launch-v1/PROJECT_BRIEF.md`
- `plans/active/f-feeder-commercial-test-launch-v1/PLAN.md`
- `plans/active/f-feeder-commercial-test-launch-v1/CODING_PLAN.md`
- `plans/active/f-feeder-commercial-test-launch-v1/PLAN_STATUS.md`
- `plans/active/f-feeder-commercial-test-launch-v1/RUNBOOK.md`
- `plans/active/f-feeder-commercial-test-launch-v1/EXECUTION_BATCH_001.md`
- `WORK_LOG.md`

Implementation tasks:
- Record the live supplier-wave evidence already on disk.
- Mark stale recommendation and approval surfaces as unsafe for launch truth.
- Define the execution phases so the process stays under control.

Isolated verification:
- command:
  - review the new plan folder contents and confirm the phase sequence matches the ticket scope
- expected result:
  - one active plan folder exists with planning, status, runbook, and first execution batch

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - planning package complete
- timeout rule:
  - none
- next automatic step after success:
  - wait for user approval to execute Batch 001
- notification mode:
  - milestone only
- user interruption threshold:
  - ask only if scope changes

Phase status:
- code fix applied:
  - yes, planning files written
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 1 - Active supplier-wave baseline refresh
Goal:
- Rebuild a trustworthy commercial launch baseline for `stocklist_supplier` from current F screening truth.
- Stop stale feeder recommendation and approval outputs from being treated as the current launch surface.

Files allowed to change:
- `scripts/flows/F/F005_build_supplier_price_list_universal.py`
- `scripts/flows/F/F060_build_legacy_sheet_review_pack.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
- `tests/test_f005_build_supplier_price_list_universal.py`
- `tests/test_f060_build_legacy_sheet_review_pack.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f018_build_live_price_file_launch_pack.py`

Implementation tasks:
- Freeze the active supplier-wave evidence before any refresh run.
- Refresh screening truth in controlled windows only.
- Build a launch-baseline file that states exactly:
  - active supplier id
  - run id
  - raw/canonical/pending/timeout/pass/rescan counts
  - stale-derived-surface status
  - whether enough finished rows exist for pass and near-miss review

Isolated verification:
- command:
  - targeted `pytest` for touched F flow files plus new `F018`
- expected result:
  - launch-baseline builder reads current row-state truth and flags stale derived launch surfaces correctly

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - `out/systems/F/inbox/supplier_price_list_queue_state.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
- poll cadence:
  - once after the controlled refresh completes
- success threshold:
  - current supplier-wave counts and freshness are explicit
  - stale approval surfaces are marked not launch-safe
- timeout rule:
  - park with the exact missing artifact or count mismatch
- next automatic step after success:
  - Phase 2
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if evidence contradicts the current supplier-wave theory

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed
- execution proof snapshot:
  - compile:
    - `python -m py_compile scripts/one_off/F018_build_live_price_file_launch_pack.py tests/test_f018_build_live_price_file_launch_pack.py` -> pass
  - tests:
    - `pytest tests/test_f018_build_live_price_file_launch_pack.py -q` -> `1 passed`
  - runtime:
    - `python scripts/one_off/F018_build_live_price_file_launch_pack.py` -> pass at `2026-04-22T14:32:38Z`
  - key outputs:
    - `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
    - `out/analysis_reports/f_live_price_file_launch_summary_latest.csv`
  - key runtime metrics:
    - `row_state_rows_active_supplier=42856`
    - `row_state_completed_rows=9987`
    - `row_state_pending_rows=32869`
    - `row_state_pass_rows=266`
    - `row_state_timeout_rows=9721`
    - `derived_launch_surface_safe_flag=false`
    - `launch_readiness_state=ready_for_pass_review_with_stale_derived_surfaces`

### Phase 2 - Pass and near-miss review packs
Goal:
- Build the review surfaces the user will actually use for launch decisions.

Files allowed to change:
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `tests/test_f018_build_live_price_file_launch_pack.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`

Implementation tasks:
- Create a pass review pack with:
  - pass reason summary
  - lower band
  - expected band
  - upper band
  - conservative starter qty
  - main commercial notes
- Create a near-miss pack with:
  - first blocker
  - blocker family
  - recovery hint
  - whether it is user-reviewable or hard reject

Isolated verification:
- command:
  - targeted `pytest` for `F018` and `F019`
- expected result:
  - pass rows and just-failed rows are separated cleanly and explainable without code knowledge

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- poll cadence:
  - once after builders run
- success threshold:
  - review packs exist and row counts reconcile to the active supplier-wave baseline
- timeout rule:
  - park with the exact unreconciled category
- next automatic step after success:
  - Phase 3
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if the pack is commercially contradictory

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - completed
- execution proof snapshot:
  - compile:
    - `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py` -> pass
  - tests:
    - `pytest tests/test_f019_build_live_price_file_near_miss_pack.py -q` -> `1 passed`
  - runtime:
    - `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py` -> pass at `2026-04-22T14:43:41Z`
  - key outputs:
    - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
  - key runtime metrics:
    - `pass_review_rows=266`
    - `near_miss_review_rows=3056`
    - `near_miss_evidence_gap_rows=2153`
    - `near_miss_commercial_rows=903`
    - `hard_reject_rows=6665`
    - `pass_review_batches=14`
    - `near_miss_review_batches=153`

### Phase 3 - Operator decision capture and release shortlist
Goal:
- Make the user veto step explicit and durable.

Files allowed to change:
- planned feeder approval and decision-log files
- planned shortlist builder files
- related tests

Implementation tasks:
- record user decisions against pass and near-miss rows
- build a release shortlist containing only user-approved test candidates
- keep watch and reject decisions explicit

Isolated verification:
- command:
  - targeted `pytest` for shortlist and decision-log behavior
- expected result:
  - user decisions produce a stable release shortlist and durable status history

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - decision log output
  - `out/analysis_reports/f_live_price_file_release_shortlist_latest.csv`
- poll cadence:
  - once after shortlist build
- success threshold:
  - release shortlist contains only approved rows
- timeout rule:
  - park with the exact decision-state inconsistency
- next automatic step after success:
  - Phase 4
- notification mode:
  - milestone only
- user interruption threshold:
  - explicit approval is required here by design

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 4 - Controlled PO handoff readiness
Goal:
- Convert the approved shortlist into a PO-ready feeder handoff without widening scope.

Files allowed to change:
- `scripts/flows/F/F050_build_feeder_po_handoff.py`
- related feeder handoff files and tests

Implementation tasks:
- map approved release rows into feeder PO handoff readiness
- preserve conservative starter quantities
- keep unapproved rows out of handoff

Isolated verification:
- command:
  - targeted `pytest` for F050 handoff logic
- expected result:
  - only approved launch rows become handoff-ready

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - `out/systems/F/live/feeder_po_handoff_ready_live.csv`
  - `out/systems/F/live/feeder_po_handoff_health.csv`
- poll cadence:
  - once after controlled handoff run
- success threshold:
  - approved rows appear, health is readable, and no unapproved rows leak through
- timeout rule:
  - park with the exact contract defect
- next automatic step after success:
  - Phase 5
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if approval or contract scope changes

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 5 - Launch monitoring and learning checkpoints
Goal:
- Learn from the test cohort without demanding perfect prediction.

Files allowed to change:
- planned launch monitoring builders
- related tests
- linked one-off review files as needed

Implementation tasks:
- produce 14-day, 30-day, and 60-day launch-cohort monitoring outputs
- compare actuals to lower and upper bands
- classify:
  - healthy conservative pass
  - acceptable but soft
  - false green
  - operationally poor outcome
- feed repeated patterns back into pass logic reviews

Isolated verification:
- command:
  - targeted `pytest` for launch-monitoring builders
- expected result:
  - monitoring pack explains outcome against the launch band logic clearly

Monitored validation:
- live proof needed:
  - yes
- artifacts to poll:
  - `out/analysis_reports/f_live_price_file_test_monitor_latest.csv`
- poll cadence:
  - milestone-based at 14d, 30d, 60d
- success threshold:
  - launch cohort outcomes are explicit and reusable for tuning
- timeout rule:
  - park until the next checkpoint window exists
- next automatic step after success:
  - close the first-wave launch ticket or promote it into the stable feeder operating model
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only for new contradiction or approval need

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started
