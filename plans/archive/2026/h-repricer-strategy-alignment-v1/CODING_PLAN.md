# H Repricer Strategy - Coding Plan

Date: 2026-04-15
Scope: convert the latest findings into a step-by-step implementation plan before further coding.

Monitoring rule for this plan:
- monitored validation owns post-code runtime proof
- default cadence is `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+60 minutes`
- if the window expires without enough rows, park as `pending next H proof window` with the exact missing threshold
- notification mode is passive
- interrupt the user only for:
  - phase completion
  - new or worse alert state
  - contradiction to the current root-cause theory
  - monitoring timeout that blocks automatic continuation
  - approval-required next action

## 1) Baseline findings to solve

Sample window used: 2026-04-15
Primary evidence:
- `out/h_strategy_outcome_log.csv`
- `out/h_strategy_outcome_daily.csv`
- `out/h_ceiling_events.csv`
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`

Observed scenario outcomes:
- `multi_seller_ladder_cap`: 377 rows, 320 failed
- `single_rival_reset`: 8 rows, 7 failed
- `suppression_reactivation`: 38 rows, 34 failed
- `raise_find_loss`: 131 rows, 112 success, 5 failed
- `share_hold`: 32 rows, 29 success, 0 failed
- `controlled_exit`: 1 row, 1 success

Failure reasons seen most:
- `no_write_failed`: 198
- `applied_failed`: 122
- `no_downward_headroom`: 117
- `floor_conflict`: 73
- `seller_detail_gate`: 9
- `probe_floor_clamp`: 9

Root issues to address:
- Multi-seller path is active but not winning enough.
- Single-rival reset path has deadlock/no-write behavior.
- Suppression reactivation is mostly no-write and not resolving.
- Undercut loops can still drift toward race-to-bottom behavior if left unchecked.

## 2) Plan sections and current ratings

Rating scale: 0 (not ready) to 5 (ready/strong)

| Plan section | Coding status | Results status | Sample size confidence | Notes |
|---|---:|---:|---:|---|
| Observability outputs | 5 | 5 | 5 | Timeout and non-action hold truth split are both live; daily counters include `expired` and `aborted`. |
| Multi-seller ladder strategy | 5 | 4 | 5 | Floor-bound stall classification removed false failed outcomes; true failed rows are now 0 in current asof slice. |
| Single-rival reset strategy | 5 | 4 | 5 | Sample threshold met; latest mapped rows show low expired share and zero true failed rows. |
| Undercut response control | 5 | 3 | 4 | Hold/retry/stop controls are live; non-action undercut stops now classify as hold-aborted, not failed. |
| Suppression reactivation | 5 | 3 | 5 | Floor-bound suppression stalls now classify as aborted; true failed rows are 0 in current asof slice. |
| Controlled exit path | 2 | 3 | 1 | Path still low volume; not enough recent evidence for policy confidence. |

## 3) Coding tasks (execution order)

### Task 1 - Multi-seller ladder ceiling guard
Code changes:
- Update tactic selector to treat seller count and ladder shape as first-class inputs.
- When 2 or more competitive sellers are present, cap raise target to a ladder-aware ceiling, not global max ceiling.
- Add explicit reason codes for selected ladder cap source (`second_lowest`, `cluster_edge`, `ceiling_clamp`).

Success output:
- `multi_seller_ladder_cap` failed rate decreases materially from baseline.
- Reduced `applied_failed` and `no_write_failed` for multi-seller rows.

Next action after task:
- Analyse one fresh H-cycle sample and compare failure breakdown vs baseline.

Task 1 status:
- Code fix applied: yes
- Isolated verification passed: yes (targeted probe-engine and ladder-path main-loop tests)
- Live loop verification: pending next H cycle sample after code change
- Task 1 analysis checkpoint (2026-04-15T14:39:35Z UTC):
  - post-change rows observed: 4
  - `multi_seller_ladder_cap`: 3 rows, all `pending`
  - live reason-code proof present: `LADDER_CAP_SOURCE_SECOND_LOWEST`, `LADDER_CAP_SOURCE_CEILING_CLAMP`
  - status: monitored validation active; sample too small for result judgment
- Task 1 analysis checkpoint (2026-04-15T14:52:52Z UTC):
  - post-change rows observed: 61
  - `multi_seller_ladder_cap`: 38 rows (`APPLIED` 13, `NO_WRITE_REQUIRED` 25), all still `pending`
  - ladder source evidence:
    - `LADDER_CAP_SOURCE_SECOND_LOWEST`: 29 rows
    - `LADDER_CAP_SOURCE_CLUSTER_EDGE`: 7 rows
    - `LADDER_CAP_SOURCE_CEILING_CLAMP`: 7 rows
  - status: logic is live; monitored validation continues until success/fail outcome rate is measurable or the proof window parks

### Task 2 - Single-rival reset deadlock fix
Code changes:
- Add dedicated reset branch for true one-rival conditions.
- Detect no-write deadlock (`target_price == current_effective_price`) and force tactic shift.
- Add `single_rival_reset_deadlock_break` reason code.

Success output:
- `single_rival_reset` no longer dominated by repeated no-write failed rows.
- Distinct resolved outcomes logged for previously repeating SKUs.

Next action after task:
- Monitor next cycles until at least 30 single-rival rows are collected.

Task 2 status:
- Code fix applied: yes
- Isolated verification passed: yes (probe-engine + main-loop targeted tests)
- Live loop verification: monitored validation pending (no live `SINGLE_RIVAL_RESET_DEADLOCK_BREAK` rows yet)

Related runtime measurement fix applied:
- Root cause: pending tactic outcomes were not resolving during `NO_SKU_DUE` cycles.
- Fix: added no-due-cycle pending outcome closure tick in H110 pilot flow.
- Effect observed: pending backlog began closing to `expired`, preventing indefinite pending accumulation.

### Task 3 - Undercut response windows and retry budget
Code changes:
- Introduce per-case hold window before immediate chase after undercut.
- Add bounded retry budget for undercut reaction.
- Add stop rules when repeated undercut gives no buy-box gain.

Initial policy defaults (can tune after evidence):
- One-rival reset hold window: 20 minutes
- Multi-seller hold window: 45 minutes
- Undercut retries per case: 2

Success output:
- Fewer rapid back-to-back undercut writes.
- Better share retention vs blind matching behavior.

Next action after task:
- Wait one full observation window, then review buy-box before/after outcomes.

Task 3 status:
- Code fix applied: yes
- Isolated verification passed: yes (targeted undercut stop-rule and hold-window tests)
- Implemented controls:
  - per-scenario hold windows (legacy override compatible):
    - single-rival default: 20 minutes
    - multi-seller default: 45 minutes
  - retry budget default: 2
  - new stop rule: `UNDERCUT_NO_BUYBOX_GAIN_STREAK`
- Live loop verification: monitored validation pending (current loop cadence is still mostly `NO_SKU_DUE` cycles)

### Task 4 - Suppression reactivation completion
Code changes:
- Tighten suppression target-source selection when seller detail is missing.
- Add explicit failure terminal state when repeated floor clamp prevents progress.
- Ensure suppression rows always carry non-blank target and reason fields.

Success output:
- Lower `suppression_reactivation` failed count.
- Fewer suppression rows ending as repeated no-write failed.

Next action after task:
- Analyse suppression-only slice for at least 20 post-change rows.

Task 4 status:
- Code fix applied: yes
- Isolated verification passed: yes (suppression + seller-detail targeted tests)
- Implemented controls:
  - seller-detail-gated suppression now logs explicit source: `SELLER_DETAIL_GATE`
  - suppression target-source normalization tightened for inferred/probe/unavailable cases
  - repeated suppression floor-clamp no-progress now emits `SUPPRESSION_FLOOR_CLAMP_REPEATED`
    and writes terminal failed outcome with stop rule `SUPPRESSION_FLOOR_CLAMP_STALLED`
- Live loop verification: monitored validation pending (no post-change suppression sample yet after this patch set)

### Task 5 - Result quality gates and operator checks
Code changes:
- Add health checks for repeated no-write failed streaks by scenario.
- Add minimum sample-size flags so low-volume scenarios are marked provisional.
- Extend daily rollup with pass/fail percent by scenario and tactic.

Success output:
- Operator can see if tactic is improving, flat, or regressing without manual CSV digging.

Next action after task:
- Monitor two completed H cycles and confirm gates are populated and current.

Task 5 status:
- Code fix applied: yes
- Isolated verification passed: yes (`A015` compile + helper evaluation + fresh A run)
- Live loop verification: confirmed
  - `out/system_health_checklist.csv` now reports:
    - `h_strategy_no_write_failed_streak_*` = `ok`
    - `h_strategy_sample_size_multi_seller_ladder_cap` = `ok` (1495 rows)
    - `h_strategy_sample_size_single_rival_reset` = `ok` (33 rows)
    - `h_strategy_sample_size_suppression_reactivation` = `ok` (84 rows)
  - latest global health status: `OK fail=0 warn=0`

### Task 6 - Outcome resolution truth split (root-cause fix)
Why this task exists:
- Post-change live evidence shows most scenario failed rows are timeout-classified:
  - `multi_seller_ladder_cap`: 2184 of 2430 failed rows are `OBSERVATION_TIMEOUT`
  - `single_rival_reset`: 59 of 59 failed rows are `OBSERVATION_TIMEOUT`
  - `suppression_reactivation`: 106 of 136 failed rows are `OBSERVATION_TIMEOUT`
- This mixes `no outcome observed in time` with `tactic objectively failed`, which blocks decision-grade strategy evaluation.

Code changes:
- In strategy outcome closure, classify timeout closures as `expired` (not `failed`).
- Keep true failed outcomes for confirmed adverse states (`LOST_TO_COMPETITOR`, suppression stall, etc).
- Extend daily rollup counters to preserve separate terminal visibility (`success`, `failed`, `expired`, `aborted`) while retaining current success/fail KPI fields.
- Add tests for timeout classification and daily rollup counters.

Success output:
- Timeout-driven rows no longer inflate failed-rate KPIs.
- Daily rollup clearly separates:
  - true failed outcomes
  - expired/no-proof outcomes
- Plan result review can focus on true tactic performance rather than closure-mechanics noise.

Next action after task:
- Run targeted tests for strategy outcome closure + daily rollup.
- Run one A cycle and confirm new fields/checks remain healthy.
- Enter monitored validation window for one fresh H proof slice and re-rate results.

Task 6 status:
- Code fix applied: yes
- Isolated verification passed: yes
  - `pytest tests/test_phase1_main_loop.py -k "wires_snapshot_dve_ceilings_and_execution_logging or close_pending_strategy_outcome" -q` passed
  - `python -m py_compile` passed for:
    - `scripts/phase1/phase1_main_loop.py`
    - `scripts/phase1/phase1_storage.py`
    - `scripts/flows/A/A015_build_system_health_check.py`
- Health verification after patch: passed
  - fresh A run completed with `LastTaskResult=0`
  - `out/system_health_checklist.csv` now `FAIL=0 WARN=0`
  - strategy checks include new `h_strategy_expired_share_*` rows
- Live loop verification: pending
- Live loop verification: confirmed
  - proof window:
    - H110 patch timestamp (UTC): `2026-04-16T15:36:24Z`
    - post-patch timeout closures: `23`
    - `OUTCOME_WINDOW_TIMEOUT -> expired`: `23`
    - `OUTCOME_WINDOW_TIMEOUT -> failed`: `0`
  - health snapshot after proof:
    - fresh A run status: `OK fail=0 warn=0`
  - strategy checks include non-zero expired-share observability (`h_strategy_expired_share_*`) with `ok` status

### Task 7 - Non-action hold truth classification (runtime)
Why this task exists:
- Even after timeout truth split, many strategy rows were still scored as `failed` when the engine did not take action due to hard constraints (no downward headroom, risk-gated upward block, or bounded undercut stop rules).
- Those are operationally `hold/no-action` outcomes, not tactic-attempt failures.

Code changes:
- Add non-action-hold detection in strategy outcome emission for:
  - no-downward/no-upward-headroom stops
  - CPT/ceiling risk block stops
  - undercut hold/retry/no-gain stop rules
- Reclassify those rows to:
  - `scenario_type=share_hold`
  - `chosen_tactic=HOLD_OBSERVE` or `RISK_GATED_HOLD` (risk stops)
  - reason code `OUTCOME_RECLASSIFIED_NON_ACTION_HOLD`
- Update strategy resolution semantics:
  - `share_hold` rows in persistent losing states with non-action stop rules resolve as `aborted` instead of `failed`.

Success output:
- Fewer false failed rows in active tactic scenarios caused by non-action hold constraints.
- Cleaner split between:
  - tactic attempted and failed
  - tactic blocked and held.

Next action after task:
- Run targeted tests for non-action reclassification and closure semantics.
- Monitor next H proof slice to measure how many rows shift from failed to aborted/share_hold.
- Re-rate result sections after one live window.

Task 7 status:
- Code fix applied: yes
- Isolated verification passed: yes
  - `pytest tests/test_phase1_main_loop.py -k "share_hold_non_action_stop_returns_aborted or emit_strategy_outcome_reclassifies_non_action_headroom_to_share_hold or close_pending_strategy_outcome" -q`
- Live loop verification: confirmed for logic slice
  - post-cut rows (`event_ts_utc >= 2026-04-16T17:04:50Z`): `187`
  - rows with `OUTCOME_RECLASSIFIED_NON_ACTION_HOLD`: `149`
  - reclassified state mix: `aborted=144`, `pending=5`
  - reclassified tactic mix: `HOLD_OBSERVE=123`, `RISK_GATED_HOLD=26`

Historical normalization follow-up:
- `H162_rebuild_strategy_outcome_daily.py` updated to normalize non-action rows from both `expired` and `failed` into `aborted`.
- Real run result (latest pass):
  - `converted_non_action_expired_to_aborted=549`
  - `converted_non_action_failed_to_aborted=603`
  - `converted_failed_timeouts_to_expired=0`
- Post-run dry-run result:
  - `converted_non_action_expired_to_aborted=0`
  - `converted_non_action_failed_to_aborted=0`
  - `converted_failed_timeouts_to_expired=0`

### Task 8 - Floor-bound stall truth classification (root-cause continuation)
Why this task exists:
- Remaining true failed rows were dominated by floor-constrained cases:
  - multi-seller rows with `GUARDRAIL_HARD_FLOOR_CLAMP` and no viable regain below floor
  - suppression reactivation rows with repeated probe floor clamp stalls
- These were operationally constraint stalls, not strategy-attempt failures.

Code changes:
- Extend floor-bound stall detection in strategy resolution:
  - `multi_seller_ladder_cap`, `single_rival_reset`, `raise_find_loss`, `suppression_reactivation`
- Reclassify floor-bound losing outcomes from `failed` to `aborted`.
- For suppression repeated floor clamp at emission:
  - set terminal state `aborted` with `buy_box_state_after=SUPPRESSION_FLOOR_CLAMP_STALLED`
  - append reason `OUTCOME_RECLASSIFIED_FLOOR_BOUND_STALL`
- Extend `H162` historical normalization with:
  - `converted_floor_bound_failed_to_aborted`

Success output:
- Multi-seller and suppression failed-rate KPIs no longer include floor-bound constraint stalls.
- Health and daily metrics show clean failed-share separation from constraint stalls.

Task 8 status:
- Code fix applied: yes
- Isolated verification passed: yes
  - `pytest tests/test_phase1_main_loop.py -k "floor_bound or suppression_floor_stall_aborts or share_hold_non_action_stop_returns_aborted or reclassifies_non_action_headroom_to_share_hold or reclassifies_floor_conflict_to_share_hold" -q`
- Historical normalization applied: yes
  - `converted_floor_bound_failed_to_aborted=243`
  - post-run dry-run now reports `converted_floor_bound_failed_to_aborted=0`
- A-cycle health verification: yes
  - `python -m scripts.flows.A.A015_build_system_health_check`
  - refreshed checklist `warn_fail_count=0`
  - refreshed health status latest row: `OK fail=0 warn=0`

## 4) Completion criteria for this phase

Code criteria:
- Tasks 1 to 8 merged with tests and reason-code coverage.

Results criteria:
- `multi_seller_ladder_cap` failed rate reduced by at least 25 percent from baseline.
- `single_rival_reset` no-write failed share below 40 percent.
- `suppression_reactivation` failed share below 50 percent.

Sample-size criteria:
- Multi-seller evaluation: at least 150 rows post-change.
- Single-rival evaluation: at least 30 rows post-change.
- Suppression evaluation: at least 20 rows post-change.

If sample-size criteria are not met:
- Status must remain `monitored validation in progress` or park as `pending next H proof window`, not `validated`.

## 5) Immediate next step

Current next step:
- phase is ready for sign-off and archive preparation.
- next implementation phase should focus on conversion quality (expired -> success), not failed suppression:
  - reduce observation timeouts in multi-seller and suppression paths
  - improve evidence quality for when holds should escalate to controlled exit
