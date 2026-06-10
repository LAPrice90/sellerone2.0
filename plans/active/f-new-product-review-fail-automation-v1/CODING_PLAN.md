# Coding Plan

Date: 2026-04-23
Scope: New Product Review fail automation with 3 fail types and targeted pass-scope rescan routing

## Current implementation addendum - 2026-05-20 F032 review intelligence Phase 1/2 and blind seed proof

Active phase:
- F032 Review Intelligence Cycle Phase 1, Phase 2, Phase 3, and Phase 6 are built as read-only analysis outputs.
- Blind validation plumbing is built and improved, but final acceptance is not passed yet because the seed set is too small.

Allowed files for this phase:
- `scripts/one_off/F032_build_review_intelligence_cycle.py`
- `scripts/one_off/F033_build_f032_blind_validation_pack.py`
- `scripts/one_off/F034_score_f032_blind_agent_runs.py`
- `tests/test_f032_build_review_intelligence_cycle.py`
- `tests/test_f033_build_f032_blind_validation_pack.py`
- `tests/test_f034_score_f032_blind_agent_runs.py`
- `plans/active/f-new-product-review-fail-automation-v1/F032_IMPLEMENTATION_AND_BLIND_VALIDATION_PLAN.md`
- `plans/active/f-new-product-review-fail-automation-v1/F032_REVIEW_INTELLIGENCE_CYCLE.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`
- `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_inputs.csv`
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_expected.csv`
- `out/analysis_reports/f032_review_intelligence_*`
- `out/analysis_reports/f032_blind_validation_*`
- `out/analysis_reports/f032_blind_agent_run_*_latest.csv`

Implementation:
- F032 combines the current Pass and Near Miss review packs with the title-match decisions and supplier canonical titles.
- F032 writes one evidence row and one decision row per candidate.
- F032 can remove clear fails from clean Pass, send uncertain rows to manual review, send incomplete evidence to rescan, or allow rows only if other checks also pass.
- F033 creates an input-only blind validation file and a separate hidden expected-answer file.
- F033 now includes visible supplier-brand guess, Amazon brand, title-rule result, quantity alignment, and pack-size guidance so blind reviewers do not invent risk outside the available evidence.
- F034 scores three blind-agent outputs for hidden-answer agreement and cross-run consistency.
- F032 writes a checklist output and a rule-tightening suggestion output.

Important root-cause correction during proof:
- Evidence-gap rows now route to `rescan_needed` before `manual_review`.
- Plain English: if the system does not have enough facts, it should fetch the missing facts before asking the user to judge the row.
- Equivalent pack wording such as `100 pc` and `100 pieces` is now recorded as matching quantity wording.
- Plain English: the system should not treat two ways of saying the same count as a pack-size problem.

Tests and isolated proof:
- `python -m py_compile scripts\one_off\F032_build_review_intelligence_cycle.py tests\test_f032_build_review_intelligence_cycle.py` -> pass
- `pytest tests\test_f032_build_review_intelligence_cycle.py -q` -> `3 passed`
- `pytest tests\test_f033_build_f032_blind_validation_pack.py tests\test_f031_build_title_match_agent_backlog.py -q` -> `7 passed`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f031_build_title_match_agent_backlog.py tests\test_f032_build_review_intelligence_cycle.py tests\test_f033_build_f032_blind_validation_pack.py tests\test_f034_score_f032_blind_agent_runs.py -q` -> `58 passed`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `20 passed`
- `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `17 passed, 53 deselected`
- `python -m py_compile scripts\one_off\F033_build_f032_blind_validation_pack.py tests\test_f033_build_f032_blind_validation_pack.py` -> pass
- `pytest tests\test_f033_build_f032_blind_validation_pack.py -q` -> `2 passed`
- `python -m py_compile scripts\one_off\F034_score_f032_blind_agent_runs.py tests\test_f034_score_f032_blind_agent_runs.py` -> pass
- `pytest tests\test_f034_score_f032_blind_agent_runs.py -q` -> `2 passed`

Live artifact proof:
- F032 command: `python scripts\one_off\F032_build_review_intelligence_cycle.py`
- evidence rows: `1603`
- decision rows: `1603`
- checklist rows: `1603`
- rule suggestion rows: `10`
- remove from clean Pass decisions: `1353`
- rescan needed decisions: `246`
- manual review decisions: `1`
- allow if other checks pass decisions: `3`
- F032 health FAIL rows: `0`
- F032 health WARN rows: `0`
- F033 command: `python scripts\one_off\F033_build_f032_blind_validation_pack.py`
- blind input rows: `9`
- hidden expected rows: `9`
- leaked answer columns: `0`
- F034 command: `python scripts\one_off\F034_score_f032_blind_agent_runs.py`
- agent run files scored: `3`
- agent decision rows scored: `27`
- acceptable action agreement: `100.0%`
- exact action agreement: `96.3%`
- exact bucket agreement: `96.3%`
- action consistency: `88.89%`
- bucket consistency: `88.89%`
- fail-to-clear flip cases: `0`

Monitoring target:
- No passive monitoring is active.
- Live F-owned proof is not yet proven because `out/systems/F/price_list_manager/live/live_cycle.lock` is active with owner `FPM130_live_cycle`.

Next automatic step:
- Expand the blind validation sample set to at least `20` clear-pass, `20` clear-fail, and `20` manual/ambiguous rows.
- Add CLF food/drink pack-size cases when CLF runs.
- Rerun the three-agent blind consistency test.

## Current implementation addendum - 2026-05-19 feedback handoff pack inclusion

Active phase:
- F021 feedback triage now reads completed handoff review packs referenced by `feeder_review_events.csv`.

Allowed files for this phase:
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`
- `tests/test_f021_build_new_product_review_fail_triage.py`
- `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`
- `plans/active/f-new-product-review-fail-automation-v1/FIX_LIST.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`

Implementation:
- F021 still reads the normal top-level pass and near-miss review packs.
- F021 also reads supplier handoff folders named by `active_supplier_id` and `active_run_id` in review feedback events.
- Duplicate review rows are removed by supplier, run, batch, candidate, SKU, and ASIN identity.

Tests and isolated proof:
- `python -m py_compile scripts\one_off\F021_build_new_product_review_fail_triage.py tests\test_f021_build_new_product_review_fail_triage.py`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py -q` -> `19 passed`

Live artifact proof:
- `python scripts\one_off\F020_check_review_event_contract.py` -> `status=pass`, `row_count=21`
- `python scripts\one_off\F021_build_new_product_review_fail_triage.py` -> `unclassified_rows=0`
- F021 loaded:
  - `dhb/fpm_dhb_20260507T055804Z`
  - `entertainment_trading/fpm_entertainment_trading_20260430T151417Z`
- F021 indexed `18` manual fail rows from review memory.
- All `18` manual fail feedback events now match triage rows as `type_2_known_policy_or_memory` / `review_memory_fail_decision`.
- The `3` manual pass feedback events are correctly absent from fail triage.

Monitoring target:
- No passive monitoring required. This was a local triage rebuild and focused code fix.

Next automatic step:
- Review the 18 matched manual fails by reason theme and choose which themes should become upstream auto-fail rules.

## Current implementation addendum - 2026-04-29 history rule v1 audit

Active phase:
- Fix 009 read-only history-rule v1 calibration audit.

Allowed files for this phase:
- `scripts/one_off/F029_build_history_borderline_near_miss_audit.py`
- `tests/test_f029_build_history_borderline_near_miss_audit.py`
- `out/analysis_reports/f_history_borderline_near_miss_audit_latest.csv`
- `out/analysis_reports/f_history_borderline_near_miss_summary_latest.md`
- `plans/active/f-new-product-review-fail-automation-v1/FIX_LIST.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`

Implementation:
- F029 now calculates recent 30/90/180-day phase metrics from stored scrape evidence.
- F029 now calculates Amazon below-break-even evidence from stored Amazon daily price series.
- V1 classification separates:
  - recent recovery pass candidates
  - Amazon below-break-even supported fails
  - current recent weakness supported fails
  - limited-upside holds

Tests and isolated proof:
- `python -m py_compile scripts\one_off\F029_build_history_borderline_near_miss_audit.py tests\test_f029_build_history_borderline_near_miss_audit.py`
- `pytest tests\test_f029_build_history_borderline_near_miss_audit.py -q`
- Expected: compile passes and focused tests pass.

Live artifact proof:
- `python scripts\one_off\F029_build_history_borderline_near_miss_audit.py`
- Success threshold:
  - audit output exists
  - unclassified rows are `0`
  - user-calibrated examples route as expected

Monitoring target:
- No passive monitoring required. This is a read-only one-off audit.

Next automatic step:
- If the user accepts the 19 recovery candidates, implement the accepted v1 rule upstream in `F019_build_live_price_file_near_miss_pack.py` and its tests.

## Current implementation addendum - 2026-04-29

Active phase:
- Manual fail-memory upstream routing in F019.

Allowed files for this phase:
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `plans/active/f-new-product-review-fail-automation-v1/FIX_LIST.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`

Implementation:
- F019 reads latest `feeder_review_events.csv` decisions when run from CLI.
- Latest `fail` routes a Pass row to Near Miss as `review_memory_fail`.
- Latest `pass` overrides an older fail so stale memory does not permanently block a row.
- Review-memory evidence columns are carried into Pass/Near Miss outputs.

Tests and isolated proof:
- `python -m py_compile scripts\one_off\F019_build_live_price_file_near_miss_pack.py scripts\one_off\F021_build_new_product_review_fail_triage.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py -q`
- Expected: compile passes and targeted tests pass.

Live artifact proof:
- `python scripts\one_off\F020_check_review_event_contract.py`
- `python scripts\one_off\F019_build_live_price_file_near_miss_pack.py`
- `python scripts\one_off\F021_build_new_product_review_fail_triage.py`
- Success threshold:
  - F020 status is `pass`.
  - F019 summary includes `review_memory_routed_remove_from_clean_pass_rows > 0`.
  - `1167948 / B007SJSX3M` is absent from clean Pass.
  - `1167948 / B007SJSX3M` is present in Near Miss as `review_memory_fail`.
  - F021 classifies the row as `type_2_known_policy_or_memory`.

Monitoring target:
- No passive monitoring required after this isolated rebuild.

Next automatic step:
- Build and isolated-test `competition-table-seller-capture-v2`.

Follow-up phase completed:
- `competition-table-seller-capture-v2`

Allowed files:
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`
- focused tests and plan files

Implementation:
- Capture rank-1 to rank-3 BBP competition-table rows as structured evidence.
- Propagate fields through F061 scrape evidence and F schema.
- Route proven rank-1 brand-owner seller or Amazon buy-box brand-owner seller out of clean Pass in F019.
- Keep Dashboard `NO + multi-seller` as alert/supporting evidence only unless brand ownership is proven.

Isolated proof:
- Compile command passed.
- Focused pytest passed: `63 passed`.

Live proof:
- Not yet proven.
- Next verifier: a scoped F061 run with BBP competition table visible, then check `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` for populated `bbp_seller_rank_1_name`.

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 | Build baseline fail audit and deterministic Type 1 checks | new one-off script, tests, plan files | targeted pytest | no | planned |
| Phase 2 | Add Type 2 auto-fail from stored evidence and decision memory | new one-off script, tests, plan files | targeted pytest | no | planned |
| Phase 3 | Add Type 3 targeted rescan planner and F007 handoff bridge | new one-off script, tests, runbook | targeted pytest plus dry-run command | yes | planned |
| Phase 4 | Run bounded day and evening proof cycle and validate outputs | runbook plus plan status artifacts | command proofs and count reconciliation | yes | planned |

## 2) Phase details

### Phase 1 - Type 1 baseline and data or calc fail checks
Goal:
- Build one row-level fail audit that classifies deterministic data-quality and calculation failures without rescanning.

Files allowed to change:
- `scripts/one_off/F020_build_new_product_review_fail_triage_pack.py`
- `tests/test_f020_build_new_product_review_fail_triage_pack.py`
- `plans/active/f-new-product-review-fail-automation-v1/*`

Implementation tasks:
- read current F review and screening artifacts
- emit one triage output with `fail_type` and `fail_reason_code`
- implement Type 1 checks for:
  - missing or invalid ASIN identity
  - impossible or inconsistent numeric fields
  - contradictory pass or fail status combinations
  - missing demand basis fields where calculation should exist

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/F020_build_new_product_review_fail_triage_pack.py tests/test_f020_build_new_product_review_fail_triage_pack.py`
  - `pytest tests/test_f020_build_new_product_review_fail_triage_pack.py -q`
- expected result:
  - tests pass and output schema is stable

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - not required, one-off artifact build
- artifacts to poll:
  - `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- poll cadence:
  - one check after script run
- success threshold:
  - output exists with non-empty classification rows
- timeout rule:
  - park with exact missing source file or schema mismatch
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 2
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only for source-contract contradiction

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 2 - Type 2 stored-evidence auto-fail
Goal:
- auto-apply fail outcomes for rows that can be blocked from evidence we already store.

Files allowed to change:
- `scripts/one_off/F021_build_new_product_review_auto_fail_pack.py`
- `tests/test_f021_build_new_product_review_auto_fail_pack.py`
- `plans/active/f-new-product-review-fail-automation-v1/*`

Implementation tasks:
- consume Type 1 triage output
- consume stored evidence from:
  - `feeder_backtest_summary_live.csv`
  - `f_pass_gate_review_pack_latest.csv`
  - `feeder_review_events.csv` when present
- output rows with:
  - `auto_fail_flag`
  - `auto_fail_reason_code`
  - `evidence_source`
  - `evidence_observed_utc`

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/F021_build_new_product_review_auto_fail_pack.py tests/test_f021_build_new_product_review_auto_fail_pack.py`
  - `pytest tests/test_f021_build_new_product_review_auto_fail_pack.py -q`
- expected result:
  - tests pass and no row is auto-failed without explicit reason

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - not required, one-off artifact build
- artifacts to poll:
  - `out/analysis_reports/f_new_product_review_auto_fail_latest.csv`
- poll cadence:
  - one check after script run
- success threshold:
  - auto-fail output exists and reason coverage is explicit
- timeout rule:
  - park with exact missing evidence source
- fallback if forced proof is blocked:
  - fallback to Type 1-only mode with explicit warning
- next automatic step after success:
  - Phase 3
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if auto-fail conflicts with current manual decisions

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 3 - Type 3 targeted rescan planner and bridge
Goal:
- route evidence-gap rows to bounded rescan batches without restarting the full fail set.

Files allowed to change:
- `scripts/one_off/F022_build_new_product_review_rescan_plan.py`
- `tests/test_f022_build_new_product_review_rescan_plan.py`
- `plans/active/f-new-product-review-fail-automation-v1/*`

Implementation tasks:
- consume Type 1 and Type 2 outputs
- select Type 3 rows and split by batch
- output rescan plan with:
  - recommended queue source
  - recommended batch size
  - recommended day or evening window
  - handoff command for `F007`
- keep behavior read-only by default

Isolated verification:
- command:
  - `python -m py_compile scripts/one_off/F022_build_new_product_review_rescan_plan.py tests/test_f022_build_new_product_review_rescan_plan.py`
  - `pytest tests/test_f022_build_new_product_review_rescan_plan.py -q`
  - `python scripts/one_off/F022_build_new_product_review_rescan_plan.py`
- expected result:
  - output plan is created and uses only Type 3 rows

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - one bounded dry-run only, no queue apply
- artifacts to poll:
  - `out/analysis_reports/f_new_product_review_rescan_plan_latest.csv`
  - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv` after dry-run command
- poll cadence:
  - one check after each command
- success threshold:
  - rescan plan exists and is reconcilable to Type 3 counts
- timeout rule:
  - park with exact mismatch between Type 3 count and planned subset count
- fallback if forced proof is blocked:
  - keep planner output and skip handoff commands
- next automatic step after success:
  - Phase 4
- notification mode:
  - milestone only
- user interruption threshold:
  - explicit approval required before any `--apply` queue rewrite

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 4 - Bounded day and evening proof cycle
Goal:
- prove practical operation: day for deterministic easy fixes, evening for bounded rescan batches.

Files allowed to change:
- `plans/active/f-new-product-review-fail-automation-v1/RUNBOOK.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`

Implementation tasks:
- execute one day-mode artifact refresh
- execute one evening-mode bounded rescan handoff plan
- capture proof counts before and after

Isolated verification:
- command:
  - run Phase 1, 2, and 3 scripts in sequence
  - run `F007` in dry-run mode from planned subset
- expected result:
  - outputs reconcile and no full-wave reset occurs

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - bounded evening dry-run first, apply run only after approval
- artifacts to poll:
  - triage, auto-fail, and rescan-plan outputs
  - `supplier_price_list_active_run.csv` row count before and after if apply is approved
- poll cadence:
  - first check at +5 minutes
  - second check at +10 minutes
  - then every +15 minutes up to +60 minutes for apply runs
- success threshold:
  - no contradiction in counts and clear reduction in manual review burden signals
- timeout rule:
  - park pending next approved proof window with exact missing threshold
- fallback if forced proof is blocked:
  - keep outputs in planning mode and defer queue apply
- next automatic step after success:
  - close this phase and move to rollout ticket
- notification mode:
  - passive during interval checks, milestone only to user
- user interruption threshold:
  - approval needed for apply runs or contradictory evidence

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.

## 4) Upstream Resolution All-Phase Execution Update - 2026-05-19

Changed at UTC:
- `2026-05-19T13:02:06Z`

Scope completed:
- Phase 0 feedback theme report implemented in `scripts/one_off/F030_build_review_feedback_reason_theme_report.py`.
- Phase 1 product identity routing added to `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`.
- Phase 2 seller ownership gate was already present in F019 and is now kept in the central priority order.
- Phase 3 profit/upside routing added to F019 using F027 audit evidence and expected-profit fallbacks.
- Phase 4 demand confidence gate remains active in F019 and still reports missing seller stock as an evidence gap, not a fake hard fail.
- Phase 5 UK review gate remains active in F019.
- Phase 6 central priority order is now identity, seller ownership, history, profit, demand, UK review, rank, then low sales.
- Phase 8 structured UI feedback reason codes added to `scripts/flows/O/O400_operator_ui.py`, `scripts/flows/F/_schemas.py`, and `scripts/flows/O/_schemas.py`.

Allowed files touched in this execution:
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/one_off/F020_check_review_event_contract.py`
- `scripts/one_off/F030_build_review_feedback_reason_theme_report.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_f020_check_review_event_contract.py`
- `tests/test_f030_build_review_feedback_reason_theme_report.py`
- `tests/test_o_ui_operator_view.py`
- this plan/status folder

Rollback snapshot:
- `out/backups/all_upstream_phases_20260519T124628Z`
- empty F019 rebuild outputs preserved under `out/backups/all_upstream_phases_20260519T124628Z/empty_f019_rebuild_20260519T125306Z`

Isolated proof passed:
- `python -m py_compile scripts\flows\F\_schemas.py scripts\flows\O\_schemas.py scripts\flows\O\O400_operator_ui.py scripts\one_off\F020_check_review_event_contract.py scripts\one_off\F030_build_review_feedback_reason_theme_report.py tests\test_o_ui_operator_view.py tests\test_f020_check_review_event_contract.py tests\test_f030_build_review_feedback_reason_theme_report.py` -> pass
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f020_check_review_event_contract.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `48 passed`
- `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `17 passed, 53 deselected`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py -q` -> `19 passed`

Read-only artifact proof passed:
- `python scripts\one_off\F020_check_review_event_contract.py`
  - `status=pass`
  - `row_count=21`
  - `invalid_review_reason_code_rows=0`
- `python scripts\one_off\F021_build_new_product_review_fail_triage.py`
  - `output_rows=2337`
  - `pass_input_rows=67`
  - `pass_rows_included=31`
  - `near_miss_input_rows=2306`
  - `unclassified_rows=0`
- `python scripts\one_off\F030_build_review_feedback_reason_theme_report.py`
  - `feedback_rows=21`
  - `manual_fail_rows=18`
  - `manual_pass_rows=3`
  - `unclassified_manual_fail_rows=0`

Live F019 proof status:
- status: `parked pending F-owned proof window`
- reason: the default F019 launch baseline currently points at `stocklist_supplier_rescrape_subset_20260421T103451Z`, but the current live row-state source has no matching active rows for that run, so a default F019 rebuild produced empty pass and near-miss outputs.
- immediate remediation already done: restored the last non-empty review outputs to `out/analysis_reports/f_live_price_file_pass_review_latest.csv` and `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`.
- current restored counts:
  - clean pass rows: `3`
  - near-miss rows: `1600`
- guard implemented at `2026-05-19T13:16:19Z`:
  - F019 now returns `blocked_source_window_empty` when the selected supplier/run has zero row-state rows and existing review outputs are non-empty.
  - The guard does not write replacement pass, near-miss, or summary snapshots in that state.
- guard proof:
  - command: `python scripts\one_off\F019_build_live_price_file_near_miss_pack.py`
  - result: `status=blocked_source_window_empty`
  - selected supplier/run: `stocklist_supplier` / `stocklist_supplier_rescrape_subset_20260421T103451Z`
  - row-state source rows: `142685`
  - matching supplier rows: `0`
  - matching source-window rows: `0`
  - preserved pass rows: `3`
  - preserved near-miss rows: `1600`
  - no timestamped F019 pass, near-miss, or summary snapshot was written for the blocked run.
- file preservation proof after guard:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`: `3` rows, timestamp unchanged at `2026-04-29T15:02:15Z`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`: `1600` rows, timestamp unchanged at `2026-04-29T15:02:15Z`
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`: `28` rows, timestamp unchanged at `2026-05-19T12:53:08Z`
- focused guard test:
  - `pytest tests\test_f019_build_live_price_file_near_miss_pack.py -q` -> `45 passed`

Required live proof trigger:
- Run only after an approved F-owned scoped proof window exists and the F owner process is not actively writing the same live files.
- Current blocker at guard proof time:
  - `out/systems/F/price_list_manager/live/live_cycle.lock` existed with owner `FPM130_live_cycle`.
  - active F061 child was running for `td_synnex`.

Artifacts to inspect during live proof:
- `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`

Live proof success condition:
- F019 source window has non-empty matching rows for the active supplier/run.
- F019 completes without replacing non-empty review outputs with empty source-window artifacts.
- Review summary includes separate identity, seller-history, profit, demand, and UK-review routing counts.
- F020, F021, and F030 still pass after the F019 rebuild.

Remediation path if live proof fails:
- If F019 still has zero matching source rows, refresh or rebuild the F018 launch baseline from the current F active run before rerunning F019.
- If BBP login blocks seller/dashboard proof, use the normal F061 script-owned visible browser path, not a separate standalone login window.
- If review outputs are blanked again, restore from the latest non-empty snapshot and keep the live phase parked until the source-window mismatch is fixed upstream.

## 5) Title Match Agent Phase - Added 2026-05-20

Reason for phase:
- User confirmed barcode is only the lookup route and is not proof of a correct product match.
- Product identity must be checked by comparing the supplier price-file title against the Amazon title.
- High ROI must be treated as a warning light because wrong item, pack-size, or accessory-vs-device mistakes can create unrealistically strong profit.

Durable plan:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_PLAN.md`

Seed sample collection:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv`

Seed examples pulled:
- Fluval filter cartridge vs Fluval 307 external filter device
- Calvin Klein perfume vs Carolina Herrera perfume
- Joby phone/tablet rig vs Lexar memory card
- MrBeast item with pack/variant wording risk
- TePe item where source presence needs guidance
- Plus-Plus item requiring title/ownership guidance

Required implementation before acceptance:
- build a durable title-match backlog
- preserve supplier title and Amazon title on every candidate row
- include ROI/profit clue on every backlog row where available
- classify rows into clear breach, pack-size issue, accessory-vs-device breach, high-ROI suspicion, needs user guidance, or title match clear
- write agent decision output without changing Google Sheets or the local product database
- add health output for missing supplier title, missing Amazon title, unchecked backlog rows, and invalid agent decision buckets
- use the seed sample collection as regression proof

Automation status:
- planned, not switched on yet

Reason automation is not switched on yet:
- the backlog file and checker output do not exist yet.
- switching on a morning automation before those exist would create noisy checks instead of useful decisions.

Automatic next step:
- build the title-match backlog and checker before marking Fail Reason 1 accepted.

## 6) Title Match Checker Build Proof - 2026-05-20

Changed at UTC:
- `2026-05-20T11:08:00Z`

Code added:
- `scripts/one_off/F031_build_title_match_agent_backlog.py`

Tests added:
- `tests/test_f031_build_title_match_agent_backlog.py`

Calibration file updated:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv`

Important rule correction:
- similar title alone does not automatically fail
- suspicious title plus extreme ROI/profit automatically fails
- suspicious title without extreme ROI goes to user guidance

Fluval proof:
- supplier title: `FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)`
- Amazon title: `Fluval 307 External Filter, 1 kg`
- supplier cost: `3.05`
- estimated profit per unit: `123.72`
- estimated monthly profit: `5196.24`
- approximate profit-on-cost: `4056%`
- checker decision: `high_roi_identity_suspicion`
- checker action: `remove_from_clean_pass`

Isolated proof passed:
- `python -m py_compile scripts\one_off\F031_build_title_match_agent_backlog.py tests\test_f031_build_title_match_agent_backlog.py` -> pass
- `pytest tests\test_f031_build_title_match_agent_backlog.py -q` -> `4 passed`

Live artifact proof:
- command: `python scripts\one_off\F031_build_title_match_agent_backlog.py --observed-utc 2026-05-20T11:08:00Z`
- backlog rows: `1603`
- decision rows: `1603`
- remove from clean Pass decisions: `7`
- manual review decisions: `259`
- allow if other checks pass decisions: `1337`
- seed calibration rows: `9`
- seed calibration mismatches: `0`
- missing supplier title rows: `0`
- missing Amazon title rows: `39` as WARN because these rows have no ASIN yet
- missing Amazon title with ASIN rows: `0`

Output files:
- `out/analysis_reports/f_title_match_agent_backlog_latest.csv`
- `out/analysis_reports/f_title_match_agent_decisions_latest.csv`
- `out/analysis_reports/f_title_match_agent_health_latest.csv`
- `out/analysis_reports/f_title_match_agent_sample_calibration_latest.csv`
- `out/analysis_reports/f_title_match_agent_summary_latest.md`

Current limitation:
- The checker writes a standalone decision file.
- F019 now also uses the same title-match rule for clean-Pass routing.
- Full live-loop proof is still pending because the F owner process must not be overlapped.

Required next implementation step:
- build the broader `F032 Review Intelligence Cycle`
- add the non-title checklist categories
- then set the morning Codex automation time

## 7) F019 Title Match Routing Integration - 2026-05-20

Changed files:
- `scripts/flows/F/_title_match_agent.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/one_off/F031_build_title_match_agent_backlog.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_f031_build_title_match_agent_backlog.py`
- `plans/active/f-new-product-review-fail-automation-v1/F032_REVIEW_INTELLIGENCE_CYCLE.md`

What changed:
- moved the title-match rule into a shared F helper so F019 and F031 use the same decision logic
- added `supplier_title` and `amazon_title` as separate F019 review output fields
- added title-match action, bucket, reason, confidence, evidence, high-ROI flag, and profit-on-cost fields to F019 outputs
- wired `title_match_action=remove_from_clean_pass` into clean-Pass routing
- wired `title_match_action=manual_review` into reviewable near-miss routing
- added summary counts for title-match routed rows

Isolated proof passed:
- `python -m py_compile scripts\flows\F\_title_match_agent.py scripts\one_off\F031_build_title_match_agent_backlog.py scripts\one_off\F019_build_live_price_file_near_miss_pack.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f031_build_title_match_agent_backlog.py` -> pass
- `pytest tests\test_f031_build_title_match_agent_backlog.py -q` -> `4 passed`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py -q` -> `46 passed`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `20 passed`
- `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `17 passed, 53 deselected`

New cycle design:
- `plans/active/f-new-product-review-fail-automation-v1/F032_REVIEW_INTELLIGENCE_CYCLE.md`

Verification status:
- code fix applied
- isolated verification passed
- live loop verification not yet proven

## 8) F032 Real Pipeline Integration Design - 2026-05-20

Design file:
- `plans/active/f-new-product-review-fail-automation-v1/F032_REAL_PIPELINE_INTEGRATION_DESIGN.md`

What the process study found:
- FPM130 calls FPM150 after F061 scanner completion.
- FPM150 currently writes the operator-readable `manifest.csv`.
- O400 reads `pass_review_path` and `near_miss_review_path` from that manifest.
- F090 also reads `pass_review_path` from that manifest.
- F032 is not currently in that handover chain.

Required clean integration:
- FPM150 must write raw candidate output only.
- A new F-owned FPM155 gate must run F032 before any operator-ready manifest exists.
- O400 must show no product rows from raw-only handoffs.
- F090 must create no listing intake rows from raw-only handoffs.
- Every visible row must carry `f032_decision_id` and `f032_action`.

Verification status:
- design completed
- implementation completed
- isolated verification passed
- live loop verification not yet proven

## 9) F032 Real Pipeline Integration Implementation - 2026-05-20

Changed files:
- `scripts/flows/F/_review_intelligence.py`
- `scripts/one_off/F032_build_review_intelligence_cycle.py`
- `scripts/flows/F/price_list_manager/FPM150_build_completed_review_pack.py`
- `scripts/flows/F/price_list_manager/FPM155_apply_review_intelligence_gate.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/price_list_manager/_schemas.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `scripts/flows/F/_schemas.py`
- `tests/test_fpm155_apply_review_intelligence_gate.py`

What changed:
- F032 reusable logic now lives in production-safe F code instead of only inside a one-off script.
- The one-off F032 report command is now a wrapper around the shared F logic.
- FPM150 now writes a raw `candidate_manifest.csv` only.
- FPM155 now runs the F032 AI gate and writes the only operator-ready `manifest.csv`.
- FPM130 now calls FPM155 immediately after raw review-pack build.
- O400 now blocks raw candidate handoffs while the AI gate is pending.
- F090 now ignores non-AI-gated manifests and blocks raw latest fallback intake.
- review events can now carry F032 decision fields for learning.

Isolated proof passed:
- `python -m py_compile scripts\flows\F\_review_intelligence.py scripts\one_off\F032_build_review_intelligence_cycle.py scripts\flows\F\price_list_manager\FPM150_build_completed_review_pack.py scripts\flows\F\price_list_manager\FPM155_apply_review_intelligence_gate.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\O\O400_operator_ui.py scripts\flows\F\F090_build_amazon_listing_intake.py` -> pass
- `pytest tests\test_f032_build_review_intelligence_cycle.py tests\test_fpm150_build_completed_review_pack.py tests\test_fpm155_apply_review_intelligence_gate.py tests\test_fpm130_live_cycle.py::test_fpm130_builds_review_pack_when_active_run_completes tests\test_o_ui_operator_view.py::test_feeder_review_can_load_completed_handoff_pack tests\test_o_ui_operator_view.py::test_feeder_review_latest_is_blocked_while_ai_gate_is_pending tests\test_f090_build_amazon_listing_intake.py -q` -> `22 passed`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f031_build_title_match_agent_backlog.py tests\test_f032_build_review_intelligence_cycle.py tests\test_f033_build_f032_blind_validation_pack.py tests\test_f034_score_f032_blind_agent_runs.py tests\test_fpm150_build_completed_review_pack.py tests\test_fpm155_apply_review_intelligence_gate.py tests\test_f090_build_amazon_listing_intake.py -q` -> `75 passed`
- `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `18 passed, 53 deselected`
- `pytest tests\test_fpm130_live_cycle.py -q` -> `63 passed`
- `pytest tests\test_f090_build_amazon_listing_intake.py -q` -> `12 passed`
- `pytest tests\test_f000_paths_and_schemas.py tests\test_o000_paths_and_schemas.py -q` -> failed on existing `f_login_backtrack_evidence_live` contract expectation mismatch outside the F032 gate scope

Manual wrapper proof:
- `python scripts\one_off\F032_build_review_intelligence_cycle.py`
- evidence rows: `1603`
- decision rows: `1603`
- checklist rows: `1603`
- remove from clean Pass rows: `1353`
- rescan needed rows: `246`
- manual review rows: `1`
- allow if other checks pass rows: `3`
- health FAIL rows: `0`
- health WARN rows: `0`

Verification status:
- code fix applied
- isolated verification passed
- live loop verification not yet proven

Next proof target:
- controlled F-flow handoff where FPM150 writes `candidate_manifest.csv`, FPM155 writes AI-gated `manifest.csv`, O400 reads only AI-gated rows, and F090 intake rows trace to F032 decisions.

## 10) F032 Codex AI Decision Gate Revision - 2026-05-20

Design correction:
- Codex AI should be the judgement layer while daily volume is low.
- Rule logic should prepare the evidence and flag obvious risk, not be the final reviewer.
- UI release should depend on a completed Codex AI decision file.

Changed files:
- `scripts/flows/F/price_list_manager/FPM155_apply_review_intelligence_gate.py`
- `scripts/one_off/F035_refresh_f032_ai_review_queues.py`
- `plans/active/f-new-product-review-fail-automation-v1/F032_CODEX_AI_REVIEW_AUTOMATION.md`

What changed:
- FPM155 now writes `ai_review_queue.csv` for Codex review.
- FPM155 now writes `codex_ai_review_decision_template.csv`.
- FPM155 waits for `codex_ai_review_decisions.csv` before publishing the operator manifest.
- FPM155 still writes no operator-ready manifest while Codex decisions are missing.
- FPM155 uses Codex actions to route rows into pass, manual/near-miss, rescan, or removed audit.
- F035 refreshes all pending queues and finalizes any queue that already has completed Codex decisions.

Automation created:
- name: `F032 Codex AI review gate`
- id: `f032-codex-ai-review-gate`
- cadence: every day at `07:30` UK time
- workspace: `C:\Users\Luke\Desktop\SellerOne 2.0`
- purpose: fill missing `codex_ai_review_decisions.csv` rows and rerun F035 so FPM155 can publish the AI-gated manifest.

Verification status:
- code fix applied
- focused FPM155 proof passed
- F035 empty-root runtime proof passed
- automation created
- live loop verification not yet proven

Latest proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM155_apply_review_intelligence_gate.py scripts\one_off\F035_refresh_f032_ai_review_queues.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\O\O400_operator_ui.py scripts\flows\F\F090_build_amazon_listing_intake.py` -> pass
- `pytest tests\test_fpm155_apply_review_intelligence_gate.py tests\test_fpm130_live_cycle.py::test_fpm130_builds_review_pack_when_active_run_completes tests\test_o_ui_operator_view.py::test_feeder_review_latest_is_blocked_while_ai_gate_is_pending tests\test_f090_build_amazon_listing_intake.py -q` -> `16 passed`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f031_build_title_match_agent_backlog.py tests\test_f032_build_review_intelligence_cycle.py tests\test_f033_build_f032_blind_validation_pack.py tests\test_f034_score_f032_blind_agent_runs.py tests\test_fpm150_build_completed_review_pack.py tests\test_fpm155_apply_review_intelligence_gate.py tests\test_f090_build_amazon_listing_intake.py -q` -> `75 passed`
- `pytest tests\test_fpm130_live_cycle.py -q` -> `63 passed`
- `python scripts\one_off\F035_refresh_f032_ai_review_queues.py --root <empty temp root>` -> `candidate_manifest_count=0`

## 11) New Product Review Fail Reason Checklist Integration Plan - 2026-05-20

Plan file:
- `plans/active/f-new-product-review-fail-automation-v1/F032_FAIL_REASON_CHECKLIST_EXECUTION_TEST_PLAN.md`

Checklist source:
- `plans/active/f-new-product-review-fail-automation-v1/FAIL_REASON_REVIEW_CHECKLIST.md`

What changed:
- the Codex AI automation guide now names the fail-reason checklist as a mandatory guide
- the Codex automation prompt now requires the checklist categories to be applied one row at a time
- the execution/test plan defines sample proof, blind consistency proof, live F-flow proof, and learning review proof

Verification status:
- planning artifact written
- automation prompt updated
- isolated current New Product Review proof run
- live F-flow proof not yet run

Superseded wrong-scope proof:
- proof root: `out/proof/f032_current_new_product_review_manual_review_test_20260520T135941Z`
- source clean Pass rows tested: `3`
- queue rows: `3`
- Codex decision rows written: `3`
- action used: `manual_review`
- manifest `ai_gate_status`: `passed`
- manifest `operator_ready_flag`: `1`
- operator clean Pass rows after gate: `0`
- manual review rows after gate: `3`
- O400 loader clean Pass rows: `0`
- O400 loader manual review rows: `3`
- reason superseded: user clarified these were manually passed rows, not the intended unassessed New Product Review rows

Correct unassessed New Product Review proof:
- proof root: `out/proof/f032_unassessed_new_product_review_kuriboh_test_20260520T142028Z`
- source row: Bliss Distribution `KONKKS` / `B09HKZWBDN`
- supplier title: `Yu-Gi-Oh! - Kuriboh Kollection Sleeves 50 Pack`
- Amazon title: `Yu-Gi-Oh! Kuriboh Kollection Card Sleeves`
- approximate profit-on-cost: `65.61%`
- queue rows before Codex decision: `1`
- pending Codex decision rows before decision: `1`
- manifest before decision: not written
- operator ready flag before decision: `0`
- Codex action written: `manual_review`
- Codex category: `pack_size_or_quantity`
- manifest after decision `ai_gate_status`: `passed`
- manifest after decision `operator_ready_flag`: `1`
- operator clean Pass rows after gate: `0`
- manual review rows after gate: `1`
- O400 loader clean Pass rows: `0`
- O400 loader manual review rows: `1`

## 12) AI Check Notes And Amazon Page Evidence Capture - 2026-05-20

Changed files:
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/legacy_scanner_2_1/WebscraperS2.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/flows/F/_review_intelligence.py`
- `scripts/flows/F/price_list_manager/FPM155_apply_review_intelligence_gate.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm155_apply_review_intelligence_gate.py`

What changed:
- O400 now shows a short `AI check note` for Codex/F032 manual-review rows.
- The Kuriboh-style note becomes: `AI check: confirm the Amazon listing is for 50 units per pack.`
- F061 can now preserve Amazon page text evidence from product details, product description, and feature bullets.
- Product description capture uses the Amazon page after the BBP/pre-review kill gate passes, not the BBP iframe.
- First-choice description selector is now the exact Amazon page path `//*[@id="productDescription"]/p[1]/span`.
- F019 can carry that evidence into New Product Review rows.
- F032/FPM155 can carry that evidence into `ai_review_queue.csv` so Codex can use it before the user sees the product.
- FPM155 now writes health check `ai_queue_amazon_page_text_columns_present`; it fails if the AI queue loses the Amazon page-text evidence columns.

Isolated proof passed:
- `python -m py_compile scripts\flows\F\legacy_scanner_2_1\WebscraperS2.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\_schemas.py scripts\one_off\F019_build_live_price_file_near_miss_pack.py scripts\flows\F\_review_intelligence.py scripts\flows\F\price_list_manager\FPM155_apply_review_intelligence_gate.py scripts\flows\O\O400_operator_ui.py` -> pass
- `pytest tests\test_o_ui_operator_view.py::test_feeder_review_manual_row_prefers_ai_check_note tests\test_f061_run_legacy_first_checks_local.py::test_f061_scrape_evidence_preserves_product_page_text tests\test_fpm155_apply_review_intelligence_gate.py::test_fpm155_writes_only_ai_gated_operator_manifest -q` -> `3 passed`
- `pytest tests\test_fpm155_apply_review_intelligence_gate.py tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `19 passed, 55 deselected`
- `pytest tests\test_f061_run_legacy_first_checks_local.py::test_f061_scrape_evidence_preserves_product_page_text tests\test_f032_build_review_intelligence_cycle.py tests\test_f019_build_live_price_file_near_miss_pack.py -q` -> `50 passed`
- `pytest tests\test_f061_run_legacy_first_checks_local.py::test_webscraper_s2_prefers_exact_product_description_xpath tests\test_f061_run_legacy_first_checks_local.py::test_f061_scrape_evidence_preserves_product_page_text -q` -> `2 passed`
- isolated Kuriboh UI loader proof: `helper_label=AI check note`, `helper_text=AI check: confirm the Amazon listing is for 50 units per pack.`

Live proof status:
- code fix applied
- isolated verification passed
- controlled F061 proof scrape passed in isolated proof root
- full scheduled live F-flow handoff proof still not completed

Next verifier:
- next controlled FPM150/FPM155 handoff proof using a row with populated Amazon page evidence

Success condition:
- new successful scrape rows populate `product_description` or `product_feature_bullets` when Amazon exposes those sections
- follow-on F019/F032 queue rows carry them as `amazon_product_description` and `amazon_feature_bullets`

Remediation path if live proof fails:
- inspect the Amazon page selectors and add another description/bullet fallback selector

Controlled F061 proof scrape - 2026-05-20:
- Kuriboh proof root: `out/proof/f061_amazon_description_xpath_20260520T144431Z`
- Kuriboh result: stopped before browser scrape with `OVER50K`; `scrape_attempted_rows=0`
- meaning: F061 does not waste Amazon description scraping on rows already rejected before the BBP/page stage
- successful scraper proof root: `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z`
- proof row: DHB `PDL504` / `B001AI8AKI`
- mode: `data_collection`
- BBP result: authenticated, dashboard yes/no `YES`, pre-review kill gate passed
- scraper result: `scrape_attempted=True`, `scrape_success=True`
- evidence rows: `feeder_legacy_scrape_evidence_live.csv` rows `1`, chart daily rows `366`
- captured `product_description`: `TePe Interdental Blue Brushes 0.6mm - Pack of 6`
- captured `product_feature_bullets`: `Plastic coated wire`; `User-friendly handle`; `Developed in collaboration with dental expertise`
- F061 health in proof root: scrape evidence runtime `ok`, chart daily runtime `ok`, BBP seller-rank capture runtime `ok`

## 13) Before Execution Checklist - FPM150/FPM155 Amazon Page Evidence Handoff

Purpose:
- prove the Amazon page evidence captured by F061 is carried into the AI review queue before the user sees New Product Review rows
- keep the proof controlled and traceable, so no step is missed and no result is assumed from chat memory

Do not execute the FPM150/FPM155 handoff proof until this checklist is used as the run guide.

Already complete:
- [x] F061 Amazon-page description selector added with first-choice XPath `//*[@id="productDescription"]/p[1]/span`
- [x] F061 output schema includes `product_detail_text`, `product_description`, and `product_feature_bullets`
- [x] F019/F032/FPM155 queue schemas include `amazon_product_detail_text`, `amazon_product_description`, and `amazon_feature_bullets`
- [x] O400 can show an `AI check note` before the user reviews the product
- [x] Kuriboh controlled proof recorded: row stopped before browser scrape with `OVER50K`
- [x] Successful controlled F061 proof recorded: DHB `PDL504` / `B001AI8AKI` populated `product_description` and `product_feature_bullets`
- [x] Plan backup before checklist update: `out/backups/f032_handoff_checklist_plan_20260520T145445Z`

Next controlled proof steps:
- [x] Use isolated proof data first; do not write Google Sheets or align the local DB
- [x] Confirm the F061 proof source row exists at `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z/out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- [x] Confirm the proof row has non-blank `product_description` or `product_feature_bullets`
- [x] Build the controlled FPM150/F019 review handoff from the proof data or a proof-only fixture, not from the full live supplier queue
- [x] Confirm FPM150/F019 raw review rows carry `amazon_product_description`, `amazon_feature_bullets`, and `amazon_product_detail_text`
- [x] Run FPM155 once with no Codex decision file and confirm the product stays blocked from operator release
- [x] Confirm FPM155 writes `ai_review_queue.csv` with the Amazon page evidence columns present
- [x] Confirm FPM155 health row `ai_queue_amazon_page_text_columns_present` is `ok`
- [x] Write one controlled Codex decision that cites Amazon page evidence in `codex_ai_evidence`
- [x] Rerun FPM155 and confirm the AI-gated manifest releases only the decided row
- [x] Confirm O400 reads the AI-gated output and shows the short AI check note
- [x] Confirm F090 continues to use the AI-gated manifest only, not the raw handoff
- [x] Record row counts: raw review rows, AI queue rows, pending decision rows, Codex decision rows, released operator rows
- [x] Record pass/fail category used for the proof row and whether page evidence changed the recommendation
- [x] Update this checklist with exact artifact paths and results before moving to live F-flow proof

Current controlled proof root:
- `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z`
- seeded source: `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z/out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- seeded row: DHB `PDL504` / `B001AI8AKI`
- seeded `product_description`: `TePe Interdental Blue Brushes 0.6mm - Pack of 6`
- seeded `product_feature_bullets`: populated
- storage mode for proof: CSV only

FPM150/F019 handoff result:
- candidate manifest: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/price_list_manager/review_handoffs/dhb/proof_fpm155_amazon_page_evidence_20260520T150009Z/candidate_manifest.csv`
- raw pass rows: `0`
- raw near-miss rows: `1`
- raw routing reason: `DEMAND_RANGE_BLOCK` / `amazon_blank_bbp_high`
- raw near-miss row carried `amazon_product_description`, `amazon_feature_bullets`, and `amazon_product_detail_text`

FPM155 pre-decision gate result:
- status: `pending_ai_decision`
- queued rows: `1`
- pending decision rows: `1`
- operator ready flag: `0`
- operator manifest: not written
- live review handoff manifest: not written
- AI queue path: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/price_list_manager/review_handoffs/dhb/proof_fpm155_amazon_page_evidence_20260520T150009Z/ai_review_queue.csv`
- queue carried `amazon_product_description`, `amazon_feature_bullets`, and `amazon_product_detail_text`
- health `ai_queue_amazon_page_text_columns_present`: `ok`

FPM155 controlled Codex decision and final gate result:
- decision path: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/price_list_manager/review_handoffs/dhb/proof_fpm155_amazon_page_evidence_20260520T150009Z/codex_ai_review_decisions.csv`
- decision id: `f032_1b8190d2c789479e`
- Codex action: `manual_review`
- decision bucket: `codex_manual_review`
- fail category: `demand_range_conflict`
- confidence: `medium`
- user guidance flag: `1`
- evidence cited: `product_description=TePe Interdental Blue Brushes 0.6mm - Pack of 6`; feature bullets; `DEMAND_RANGE_BLOCK` / `amazon_blank_bbp_high`
- final FPM155 status: `gated`
- final AI gate status: `passed`
- final AI gate fail rows: `0`
- final AI gate warn rows: `0`
- final operator ready flag: `1`
- final manifest: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/price_list_manager/review_handoffs/dhb/proof_fpm155_amazon_page_evidence_20260520T150009Z/manifest.csv`
- live manifest inside proof root: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/price_list_manager/live/review_handoff_manifest.csv`

Controlled proof row counts:
- raw pass rows: `0`
- raw near-miss rows: `1`
- AI queue rows: `1`
- pending decision rows after first FPM155 run: `1`
- Codex decision rows: `1`
- released clean-pass operator rows: `0`
- released near-miss operator rows: `1`
- released manual-review rows: `1`
- removed-from-clean-pass audit rows: `0`

O400 proof result:
- O400 latest pass rows from proof root: `0`
- O400 latest near-miss rows from proof root: `1`
- O400 manual-review available rows: `1`
- O400 manual-review visible rows: `1`
- O400 normal near-miss visible rows after manual filter: `0`
- visible row action: `manual_review`
- visible row label: `AI check note`
- visible row note: `AI check: Amazon page confirms this is a 6-pack, but demand evidence conflicts, so keep it in manual review rather than clean pass.`
- visible row carried `amazon_product_description`: `TePe Interdental Blue Brushes 0.6mm - Pack of 6`

F090 proof result:
- first F090 run after AI gate: status `success`, listing intake rows `0`, listing hold rows `0`
- raw fallback trap file added under proof root only: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- raw fallback trap rows: `1`
- second F090 run after trap: status `success`, listing intake rows `0`, listing hold rows `0`
- F090 health path: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z/out/systems/F/health/amazon_listing_health.csv`
- F090 health `amazon_listing_intake_bridge`: `ok`, `intake_rows=0;hold_rows=0`
- meaning: F090 ignored the old raw analysis-report pass file and used only the AI-gated review handoff

Remaining live proof follow-up:
- trigger: next full scheduled F price-list manager live cycle that completes a real supplier run and writes a live FPM150/FPM155 review handoff
- artifacts to inspect: `out/systems/F/price_list_manager/live/review_handoff_manifest.csv`, the matching handoff directory under `out/systems/F/price_list_manager/review_handoffs`, O400 New Product Review loader output, and `out/systems/F/health/amazon_listing_health.csv`
- success condition: live FPM155 `ai_gate_status=passed`, `operator_ready_flag=1`, queued rows carry Amazon page evidence where available, O400 shows only AI-gated rows with AI notes for manual-review rows, and F090 does not consume raw analysis-report pass rows
- remediation path if it fails: pause live release, keep rows out of O400, inspect whether the break is F061 evidence capture, FPM150 carry-forward, FPM155 Codex decision gating, O400 manifest selection, or F090 manifest selection, then fix the earliest broken stage

Proof file backup before final checklist update:
- `out/backups/f032_handoff_final_plan_update_20260520T150700Z/CODING_PLAN.md`

Pass criteria:
- F061 proof evidence has at least one non-blank Amazon page evidence field
- FPM150/F019 carries that evidence into the review rows
- FPM155 carries that evidence into `ai_review_queue.csv`
- rows without Codex decisions stay hidden from the user-facing review output
- rows with Codex decisions can be released to O400 with the AI note attached
- F090 sees only the AI-gated output
- all proof artifacts are under `out/proof` unless the task is explicitly switched to a live F-flow proof

Stop conditions:
- any proof step tries to write Google Sheets
- any proof step changes the local DB
- the controlled proof starts consuming the full live supplier queue unexpectedly
- `ai_review_queue.csv` loses any Amazon page evidence column
- O400 shows a row before FPM155 has a Codex decision for it

## 14) Passed Product Amazon Page Evidence Backfill

Purpose:
- rescan previously passed products to collect the new Amazon page evidence fields now used by the review intelligence gate
- collect `product_detail_text`, `product_description`, and `product_feature_bullets` without changing prior user decisions
- use the same scanner-owned Amazon/BBP path where possible so the evidence is comparable with new scans

Read-only backlog count - 2026-05-20:
- pass-review files inspected: `30`
- total historical pass rows found: `2298`
- unique historical pass identities found: `295`
- unique historical pass ASINs found: `289`
- current latest Pass rows: `3`
- current latest unique Pass ASINs: `3`
- unique historical Pass ASINs with this new page evidence already present in live scrape evidence: `0` found in the pass set
- unique historical Pass ASINs still missing page evidence: `289`

Recommended implementation:
- build a dedicated backfill queue from historical clean Pass rows
- dedupe by ASIN first, then keep supplier SKU/title as supporting context
- skip any ASIN that already has nonblank `product_description`, `product_feature_bullets`, or `product_detail_text`
- run in small batches, starting with the current latest Pass rows only
- store the backfill output separately first, then merge evidence into the normal F evidence path only after proof
- do not change Google Sheets
- do not change local product database records
- do not mark old Pass decisions as newly passed or failed during evidence capture

Backfill pass criteria:
- queue row count equals the expected missing-evidence count for the selected scope
- sample batch uses scanner-owned Amazon page access and records `scrape_attempted=True`
- at least one of `product_description`, `product_feature_bullets`, or `product_detail_text` is captured when the Amazon page visibly provides it
- captured rows can be joined back to the pass-review rows by ASIN
- FPM155 can consume the enriched evidence on a proof row without exposing raw rows to O400
- F090 continues to consume only AI-gated clean Pass rows

Backfill stop conditions:
- the backfill tries to write Google Sheets
- the backfill writes product database changes
- the backfill overwrites prior scanner evidence without a backup
- Amazon/BBP login-required rows start blocking the normal F scanner
- the backfill opens a browser outside the scanner-owned F061 path

Next implementation step:
- [x] create a proof-only backfill queue builder for passed-product page evidence
- [x] first proof scope: the `3` current latest Pass rows
- [x] second proof scope: a capped historical batch, recommended `10` ASINs
- full backfill scope after proof: up to `289` unique historical Pass ASINs

Implementation result - 2026-05-20:
- script: `scripts/one_off/F036_build_passed_product_page_evidence_backfill_queue.py`
- tests: `tests/test_f036_build_passed_product_page_evidence_backfill_queue.py`
- one-off helper registry updated: `scripts/ONE_OFF_SCRIPTS.md`
- compile proof: `python -m py_compile scripts\one_off\F036_build_passed_product_page_evidence_backfill_queue.py tests\test_f036_build_passed_product_page_evidence_backfill_queue.py` -> pass
- focused test proof: `pytest tests\test_f036_build_passed_product_page_evidence_backfill_queue.py -q` -> `3 passed`

Latest Pass queue proof - 2026-05-20T15:25:00Z:
- command: `python scripts\one_off\F036_build_passed_product_page_evidence_backfill_queue.py --scope latest --observed-utc 2026-05-20T15:25:00Z`
- queue path: `out/analysis_reports/f_passed_product_page_evidence_backfill_queue_latest.csv`
- F061 staging path: `out/analysis_reports/f_passed_product_page_evidence_backfill_f061_active_run_latest.csv`
- health path: `out/analysis_reports/f_passed_product_page_evidence_backfill_health_latest.csv`
- summary path: `out/analysis_reports/f_passed_product_page_evidence_backfill_summary_latest.csv`
- report path: `out/analysis_reports/f_passed_product_page_evidence_backfill_summary_latest.md`
- pass files inspected: `1`
- raw Pass rows read: `3`
- unique Pass ASINs before skip: `3`
- existing evidence skip rows: `0`
- queue rows: `3`
- F061-ready rows: `3`
- missing barcode rows: `0`
- health FAIL rows: `0`
- health WARN rows: `0`
- queued ASINs: `B082NMTZC2`, `B09FQCWKPW`, `B084CTW7T8`

Historical sample queue proof - 2026-05-20T15:26:00Z:
- command: `python scripts\one_off\F036_build_passed_product_page_evidence_backfill_queue.py --scope all --limit 10 --observed-utc 2026-05-20T15:26:00Z --queue-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_queue_historical_sample_latest.csv --f061-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_f061_active_run_historical_sample_latest.csv --health-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_health_historical_sample_latest.csv --summary-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_summary_historical_sample_latest.csv --report-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_summary_historical_sample_latest.md`
- queue path: `out/analysis_reports/f_passed_product_page_evidence_backfill_queue_historical_sample_latest.csv`
- F061 staging path: `out/analysis_reports/f_passed_product_page_evidence_backfill_f061_active_run_historical_sample_latest.csv`
- health path: `out/analysis_reports/f_passed_product_page_evidence_backfill_health_historical_sample_latest.csv`
- pass files inspected: `30`
- raw Pass rows read: `2298`
- unique Pass ASINs before skip: `289`
- limit applied: `10`
- queue rows: `10`
- F061-ready rows: `10`
- missing barcode rows: `0`
- health FAIL rows: `0`
- health WARN rows: `0`

Next execution step:
- [x] create an isolated proof root from the latest `3` row F061 staging file
- [x] run F061 in `data_collection` mode against that proof root only
- success condition: at least one queued latest Pass row records nonblank `product_description`, `product_feature_bullets`, or `product_detail_text`
- remediation path if it fails: inspect whether the failure is browser/login access, catalog/barcode lookup, exact description selector coverage, or evidence write/merge

Isolated proof root staged - 2026-05-20T15:30:00Z:
- proof root: `out/proof/f036_passed_product_page_evidence_backfill_latest_queue_20260520T153000Z`
- latest pointer: `out/proof/latest_f036_passed_product_page_evidence_backfill_proof_root.txt`
- source F061 staging file: `out/analysis_reports/f_passed_product_page_evidence_backfill_f061_active_run_latest.csv`
- proof active-run path: `out/proof/f036_passed_product_page_evidence_backfill_latest_queue_20260520T153000Z/out/systems/F/inbox/supplier_price_list_active_run.csv`
- proof supplier active-run path: `out/proof/f036_passed_product_page_evidence_backfill_latest_queue_20260520T153000Z/out/systems/F/inbox/suppliers/stocklist_supplier/active_run.csv`
- staged rows: `3`
- execution status: `staged_only_not_run`
- reason not run now: live F price-list scanner is already running `td_synnex` with owner PID `10716`; starting another F061 browser session would overlap the BBP Chrome profile
- next safe trigger: live F scanner idle or controlled F maintenance window
- next command shape after trigger: run F061 against the proof root with `F061_MODE=data_collection`, supplier `stocklist_supplier`, and max rows `3`

Plan backup before this section:
- `out/backups/f032_passed_product_page_evidence_backfill_plan_20260520T151500Z`

Forced latest-Pass F061 evidence proof - 2026-05-20:
- user instruction: force the proof window instead of waiting for the next idle scanner window
- live F scanner before force: `td_synnex`, owner PID `10716`, child PID `26864`, pending rows `51872`
- control method used: wrote `out/locks/maintenance.requested` with `exit_after_drain=1` and `action=reload`
- direct Windows process kill result: blocked by Windows access control, so the scanner was forced through its own maintenance/drain gate
- forced drain marker: `out/systems/F/price_list_manager/live/F_restart_drain.ready`
- live drain status: `drain_exit`, pending rows `51847`, no overlapping F061 process before proof
- first isolated proof root: `out/proof/f036_passed_product_page_evidence_backfill_latest_queue_20260520T153000Z`
- first F061 result: `processed_rows=3`, `pass_rows=3`, `fail_rows=0`, `scrape_attempted_rows=3`, `scrape_success_rows=3`, `scrape_failed_rows=0`, `chart_daily_rows_captured=1098`
- integration gap found during proof: `supplier_title` was present in the staged queue but missing from F061 scrape evidence and screening state outputs
- upstream correction applied: `supplier_title` is now carried into `feeder_legacy_scrape_evidence_live.csv` and `f_screening_row_state_live.csv`
- changed files for correction: `scripts/flows/F/_schemas.py`, `scripts/flows/F/F061_run_legacy_first_checks_local.py`, `tests/test_f061_run_legacy_first_checks_local.py`
- compile proof after correction: `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\_schemas.py tests\test_f061_run_legacy_first_checks_local.py` -> pass
- focused F061/page-evidence tests after correction: `2 passed, 60 deselected`
- queue-builder regression tests after correction: `3 passed`
- second isolated proof root after correction: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z`
- second F061 result: `processed_rows=3`, `pass_rows=3`, `fail_rows=0`, `scrape_attempted_rows=3`, `scrape_success_rows=3`, `scrape_failed_rows=0`, `chart_daily_rows_captured=1098`
- second health result: all `feeder_legacy_sheet_health.csv` checks `ok`
- proof evidence path: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z/out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- proof health path: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z/out/systems/F/live/feeder_legacy_sheet_health.csv`
- proof rows confirmed with supplier title and Amazon page evidence:
  - `B082NMTZC2`: supplier title `JVC - Boomblaster DAB+ /Audio  and  HiFi /Black`, Amazon title and feature bullets captured
  - `B084CTW7T8`: supplier title `Embryolisse - Hydra-Creme Legere Tube 40 ml /Skin care /40`, Amazon title, feature bullets, and product description captured
  - `B09FQCWKPW`: supplier title `Kensington - Orbit Trackball with Scroll Ring wireless - Black`, Amazon title and feature bullets captured
- live F ownership restored after proof: supervisor `ok`, manager PID `21680`, child PID `12776`, active supplier `td_synnex`, pending rows `51847`, scanner running
- final status: isolated backfill proof passed and live F scanner restored

## 15) Controlled Historical Backfill Runner

Purpose:
- work through the full passed-product page-evidence backlog without losing track
- keep a durable row status for every queued ASIN
- run F061 in controlled batches only, using isolated proof roots
- save captured Amazon page evidence into a backfill results file before any live merge

Implementation boundary:
- no Google Sheets writes
- no product database writes
- no automatic merge into `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` in this phase
- no second F061 browser while the live F scanner owns the BBP Chrome profile
- if a forced proof window is used, it must go through the F scanner maintenance/drain marker and then restore live F ownership

Allowed files:
- `scripts/one_off/F037_run_passed_product_page_evidence_backfill_batch.py`
- `tests/test_f037_run_passed_product_page_evidence_backfill_batch.py`
- `scripts/ONE_OFF_SCRIPTS.md`
- `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`
- `plans/active/f-new-product-review-fail-automation-v1/PLAN_STATUS.md`
- output under `out/systems/F/page_evidence_backfill/`
- proof roots under `out/proof/`

Pass criteria:
- full queue can be loaded into a durable state file
- next pending rows can be staged into an isolated F061 active-run root
- each row records pending, staged, succeeded, failed, or blocked status
- batch output records supplier title, Amazon title, product detail text, product description, and feature bullets
- health output shows schema state, pending rows, succeeded rows, failed rows, and last batch status
- execute mode refuses to run when live F is active unless an explicit maintenance/drain force option is used

Stop conditions:
- live F scanner is active and the runner is not in explicit force-maintenance mode
- F061 output has no matching evidence rows for the staged ASINs
- any batch attempts to write Google Sheets or the product database
- live F scanner is not restored after a forced maintenance window

Initial status:
- backup before implementation: `out/backups/f037_historical_backfill_runner_plan_20260520T155114Z`
- live F state before implementation: active `td_synnex` scanner, so implementation and prepare-only proof are allowed, but live execute must be gated

Implementation result - 2026-05-20:
- runner script: `scripts/one_off/F037_run_passed_product_page_evidence_backfill_batch.py`
- tests: `tests/test_f037_run_passed_product_page_evidence_backfill_batch.py`
- registry updated: `scripts/ONE_OFF_SCRIPTS.md`
- compile proof: `python -m py_compile scripts\one_off\F036_build_passed_product_page_evidence_backfill_queue.py scripts\one_off\F037_run_passed_product_page_evidence_backfill_batch.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\_schemas.py tests\test_f036_build_passed_product_page_evidence_backfill_queue.py tests\test_f037_run_passed_product_page_evidence_backfill_batch.py tests\test_f061_run_legacy_first_checks_local.py` -> pass
- focused test proof: `9 passed, 57 deselected`

Full queue build - 2026-05-20T15:55:00Z:
- command: `python scripts\one_off\F036_build_passed_product_page_evidence_backfill_queue.py --scope all --observed-utc 2026-05-20T15:55:00Z --queue-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_queue_full_latest.csv --f061-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_f061_active_run_full_latest.csv --health-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_health_full_latest.csv --summary-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_summary_full_latest.csv --report-output-path out\analysis_reports\f_passed_product_page_evidence_backfill_summary_full_latest.md`
- pass files inspected: `30`
- raw pass rows: `2298`
- unique ASINs queued: `289`
- F061-ready rows: `289`
- missing barcode rows: `0`
- health FAIL rows: `0`
- health WARN rows: `0`

Prepare-only proof:
- command: `python scripts\one_off\F037_run_passed_product_page_evidence_backfill_batch.py --queue-path out\analysis_reports\f_passed_product_page_evidence_backfill_queue_full_latest.csv --batch-size 5 --batch-id f037_full_backfill_batch_001_20260520T155600Z --observed-utc 2026-05-20T15:56:00Z`
- status: `prepared`
- staged rows: `5`
- proof root: `out/proof/f037_full_backfill_batch_001_20260520T155600Z`
- state path: `out/systems/F/page_evidence_backfill/page_evidence_backfill_state.csv`
- manifest path: `out/systems/F/page_evidence_backfill/page_evidence_backfill_batch_manifest.csv`
- health path: `out/systems/F/page_evidence_backfill/page_evidence_backfill_health.csv`

Live overlap safety proof:
- command: same batch with `--execute` and no `--force-maintenance`
- result: `blocked_live_f_active`
- block evidence: active F061 child PID `15848`
- meaning: runner did not open another F061 browser while live F owned the BBP profile

Forced batch 001 execution:
- command: same batch with `--execute --force-maintenance --force-timeout-seconds 1800 --f061-timeout-seconds 7200`
- status: `executed`
- F061 return code: `0`
- staged rows: `5`
- processed rows: `5`
- succeeded rows: `5`
- failed rows: `0`
- captured rows: `5`
- results path: `out/systems/F/page_evidence_backfill/page_evidence_backfill_results.csv`
- state result: `5` succeeded, `284` pending
- health result: all page-evidence backfill health checks `ok`
- live F restored after force window: supervisor `ok`, manager PID `25036`, child PID `10156`, active supplier `td_synnex`, pending rows `51722`
- maintenance markers after restore: `out/locks/maintenance.requested=absent`, `out/systems/F/price_list_manager/live/F_restart_drain.ready=absent`
- example captured rows:
  - `B0C8C3JF9X`: PowerA Xbox controller, supplier title and Amazon description/bullets captured
  - `B0DTJBRNG5`: PowerA Nintendo Switch controller, supplier title and Amazon description/bullets captured
  - `B082NMTZC2`: JVC boombox, supplier title and Amazon description/bullets captured
  - `B09FQCWKPW`: Kensington trackball, supplier title and Amazon description/bullets captured
  - `B084CTW7T8`: Embryolisse 40 ml cream, supplier title and Amazon description/bullets captured

Remaining controlled work:
- remaining rows: `284`
- recommended next batch size: `5` to `10` rows until failure behavior is observed
- do not merge backfill results into live scrape evidence until the next merge phase is planned and tested

Continuous execution status - 2026-05-20T17:45:43Z:
- user instruction: keep managing the task through completion using agents and local checks
- live scanner control: live F scanner drained through `out/locks/maintenance.requested`; backfill runner owns the F scanner window while historical backfill runs
- local control runner: `out/systems/F/page_evidence_backfill/run_backfill_until_complete.ps1`
- heartbeat file: `out/systems/F/page_evidence_backfill/run_backfill_until_complete_heartbeat.json`
- current heartbeat batch: `f037_full_backfill_auto_0034_20260520T174543Z`
- current durable state: `33` succeeded with page evidence, `52` skipped because the current scanner now rejects the old historical pass, `204` pending, `0` failed, `0` staged
- current health: all page-evidence backfill checks `ok`
- independent agent checks completed:
  - queue/state/data audit confirmed `289` queued rows, `5` first-batch successes at the time of audit, clean schema, and usable first captured evidence
  - runner safety audit confirmed F037 isolated proof-root execution, no Sheets/Product DB writes, and the need to watch `captured_rows`, not just `succeeded_rows`
- new source fixes added while running:
  - `skipped_current_scanner_fail` status for historical passes now rejected by the current scanner before page evidence
  - `NOASIN` screening-state rejects are treated as handled current scanner rejects, not broken scrapes
  - evidence now matches by `backfill_id`/candidate id before old queued ASIN, so a current barcode-resolved ASIN change can still capture page evidence
  - `resolved_asin` is recorded in the backfill results so old queued ASIN and current resolved ASIN are both visible
- latest focused proof after these fixes: `pytest tests\test_f037_run_passed_product_page_evidence_backfill_batch.py -q` -> `7 passed`
- backups made during live correction:
  - `out/backups/f037_reclassify_current_scanner_fail_20260520T163053Z`
  - `out/backups/f037_reclassify_noasin_20260520T165050Z`
  - `out/backups/f037_reclassify_resolved_asin_20260520T172933Z`
- current pass criteria for continued automated execution:
  - each batch must end `status=executed`
  - `failed_rows` must stay `0`
  - `processed_rows` must equal `captured_rows + skipped_current_scanner_fail`
  - state must have `0` staged rows before the next batch
  - if a new unmatched failure appears, diagnose it from the proof root and fix the earliest classifier/matcher stage before restarting
- next automatic action: keep polling the heartbeat, state, manifest, and health files until pending reaches `0` or a genuinely new failure pattern appears
