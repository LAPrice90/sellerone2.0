# Coding Plan

Date: `2026-04-16`
Scope: sign off the completed H alignment slice, then execute the next H strategy phase in this order: truth repair first, conversion tuning second.

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 | Repair truth contracts for ceiling/floor and daily rollup integrity | `phase1_probe_engine.py`, `phase1_main_loop.py`, `phase1_storage.py`, `A015_build_system_health_check.py`, targeted tests | yes | yes | completed (live proof confirmed) |
| Phase 2 | Repair earliest-stage ceiling source behavior so invalid raw ceilings do not become effective live ceilings | `phase1_probe_engine.py`, `phase1_main_loop.py`, `phase1_storage.py`, targeted tests | yes | yes | completed (live proof confirmed) |
| Phase 3 | Tune scenario conversion for crowded ladders, suppression, controlled exit, and seller-detail holds | `phase1_probe_engine.py`, `phase1_main_loop.py`, `phase1_storage.py`, `A015_build_system_health_check.py`, targeted tests | yes | yes | parked pending next proof window (sample thresholds not met) |
| Phase 4 | Sign-off review, monitored validation, archive | plan docs only unless a scoped follow-up is required | no new tests unless follow-up needed | yes | completed (active plan retained with explicit park condition) |
| Phase 5 | Produce undeniable sign-off proof for the current H candidate or fail truthfully with exact missing proof | plan docs plus optional one-off proof-pack builder/test only | yes if builder added | yes | parked pending next proof window (proof pack generated; sign-off gates failed) |
| Phase 6 | Apply root-cause conversion patch (multi-seller reset-up + suppression timeout floor-stall classification) | `phase1_probe_engine.py`, `phase1_main_loop.py`, targeted tests, plan docs | yes | yes | parked pending next proof window (post-change behavior moved; sign-off gates still open) |

## 2) Phase details

### Phase 1 - Truth contract repair
Goal:
- Make the outputs trustworthy enough to support the next optimisation phase.

Files allowed to change:
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_storage.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_phase1_probe_engine.py`
- `tests/test_phase1_main_loop.py`
- `tests/test_phase1_storage.py`

Implementation tasks:
- Add a clear raw-vs-effective ceiling contract so operator outputs can show source conflict without exposing an invalid effective binding ceiling.
- Repair the daily rollup logic so impossible counts cannot persist silently.
- Add scoped health checks for:
  - effective ceiling below hard floor
  - `at_floor_rows > decision_rows`
  - `below_break_even_rows > decision_rows`
  - any terminal-count contract mismatch that should be impossible

Isolated verification:
- command:
  - `pytest tests/test_phase1_probe_engine.py -q`
  - `pytest tests/test_phase1_main_loop.py -q`
  - `pytest tests/test_phase1_storage.py -q`
  - `python -m py_compile scripts/phase1/phase1_probe_engine.py scripts/phase1/phase1_main_loop.py scripts/phase1/phase1_storage.py scripts/flows/A/A015_build_system_health_check.py`
- expected result:
  - all targeted tests pass
  - compile passes with no syntax errors

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - H truth outputs plus scoped H health from a forced H proof window:
    - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
    - `.\run_H_isolation_pause.bat`
    - `.\run_H_isolation_success.bat`
    - `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
    - `.\run_H_isolation_resume.bat`
- artifacts to poll:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/system_health_checklist.csv`
- poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+60 minutes`
- success threshold:
  - latest fresh H slice has `0` rows where effective binding ceiling is below the hard floor
  - latest daily rollup has `0` rows where `at_floor_rows > decision_rows`
  - latest daily rollup has `0` rows where `below_break_even_rows > decision_rows`
  - forced H-scoped proof writes the new H integrity checks as `ok`
- timeout rule:
  - if no fresh H slice or no forced H proof completes inside the monitoring window, park as `pending next H proof window` and record the exact missing artifact, blocker, and timestamp
- fallback if forced proof is blocked:
  - record the exact H owner, lock, or resume blocker; only then fall back to the next owned proof boundary
- next automatic step after success:
  - start Phase 2 immediately
- notification mode:
  - passive
- user interruption threshold:
  - phase complete, new/worse alert, contradiction, approval-required action, or timeout park

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: completed for H artifacts (`latest_ceiling_run_id=20260417T035032Z`, `ceiling_conflicts=0`, daily integrity mismatches `0`); scoped H health confirmation now belongs to the forced H proof window, not a vague next-cycle wait

### Phase 2 - Earliest-stage ceiling source repair
Goal:
- Fix the ceiling source path so raw invalid ceilings are recorded as evidence but do not become live effective ceilings.

Files allowed to change:
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_storage.py`
- `tests/test_phase1_probe_engine.py`
- `tests/test_phase1_main_loop.py`
- `tests/test_phase1_storage.py`

Implementation tasks:
- Trace how `COMPLIANCE`, `ELIGIBILITY`, `DEMAND`, and suppression ceilings compete.
- When a raw winning ceiling lands below the hard floor:
  - keep the raw conflict visible
  - prevent the effective binding ceiling from remaining below floor
  - keep reason codes explicit about source and resolution
- Ensure the runtime floor snapshot and ceiling-event output agree on the effective ceiling contract.

Isolated verification:
- command:
  - `pytest tests/test_phase1_probe_engine.py -k "ceiling or floor or suppression" -q`
  - `pytest tests/test_phase1_main_loop.py -k "ceiling or floor" -q`
  - `pytest tests/test_phase1_storage.py -k "ceiling" -q`
  - `python -m py_compile scripts/phase1/phase1_probe_engine.py scripts/phase1/phase1_main_loop.py scripts/phase1/phase1_storage.py`
- expected result:
  - targeted ceiling/floor tests pass
  - outputs serialize with the updated ceiling contract

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- artifacts to poll:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_floor_truth_trace.csv`
  - `out/system_health_checklist.csv`
- poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+60 minutes`
- success threshold:
  - latest H slice shows `0` effective binding-ceiling conflicts
  - if raw conflicts still appear, they are explicitly visible as raw conflict evidence and no longer land as live effective ceiling values below floor
  - latest runtime floor snapshot and ceiling-event output agree for the same SKUs on the effective ceiling
- timeout rule:
  - if proof does not arrive inside the monitoring window, park with the exact count of remaining conflicting rows and the next required H artifact timestamp
- fallback if forced proof is blocked:
  - record the exact ownership blocker or stale-marker blocker before deferring to the next safe H boundary
- next automatic step after success:
  - start Phase 3 immediately
- notification mode:
  - passive
- user interruption threshold:
  - phase complete, new/worse alert, contradiction, approval-required action, or timeout park

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: completed for runtime artifact contract (`runtime_conflicts=0` at `snapshot_utc=2026-04-17T03:50:32Z`) after suppression-truth clamp fix

### Phase 3 - Conversion tuning on truthful data
Goal:
- Improve real strategy performance now that the fail-vs-expired-vs-aborted split is cleaner and the truth layer is fixed.

Files allowed to change:
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_storage.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_phase1_probe_engine.py`
- `tests/test_phase1_main_loop.py`
- `tests/test_phase1_storage.py`

Implementation tasks:
- Review crowded-ladder regain behavior against seller count and ladder spacing.
- Decide when repeated `expired` or `aborted` states should escalate to:
  - hold
  - controlled exit
  - reset retry
- Review `SELLER_DETAIL_HOLD` behavior and the meaning of current `23` failed rows.
- Review controlled-exit success semantics so we can tell whether the tactic is ineffective or just measured badly.
- Keep the new work tied to outputs that show whether the logic improved.

Isolated verification:
- command:
  - `pytest tests/test_phase1_probe_engine.py -k "ladder or regain or suppression or seller_detail or controlled_exit" -q`
  - `pytest tests/test_phase1_main_loop.py -k "ladder or regain or suppression or seller_detail or controlled_exit" -q`
  - `python -m py_compile scripts/phase1/phase1_probe_engine.py scripts/phase1/phase1_main_loop.py scripts/phase1/phase1_storage.py scripts/flows/A/A015_build_system_health_check.py`
- expected result:
  - targeted tactic tests pass
  - reason-code and terminal-state outputs stay populated

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - reuse the H forced proof window after the conversion patch so the new scenario outcomes and H-scoped health are fresh in the same proof block
- artifacts to poll:
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/system_health_checklist.csv`
- poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+60 minutes`
- success threshold:
  - over the first fresh post-change sample:
    - `multi_seller_ladder_cap` has at least `150` rows and `success_rows_per_100_decisions >= 2.0`
    - `multi_seller_ladder_cap` combined `expired_rows + aborted_rows` share is `<= 95%`
    - `suppression_reactivation` has at least `30` rows and `success_rows >= 2`
    - `suppression_reactivation` expired share is `<= 55%`
    - `controlled_exit` has at least `10` rows and either:
      - `success_rows >= 1`, or
      - its success contract is explicitly corrected and documented so expiry is not misread as failure
- timeout rule:
  - if the sample threshold is not met inside the monitoring window, park as `pending next H proof window` with the exact missing counts by scenario
- fallback if forced proof is blocked:
  - record the exact ownership blocker and the exact artifact needed to resume proof
- next automatic step after success:
  - move to Phase 4 sign-off review
- notification mode:
  - passive
- user interruption threshold:
  - phase complete, new/worse alert, contradiction, approval-required action, or timeout park

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: second Phase 3 patch validated (`2026-04-17T11:13:01Z` code change) with isolated and live runtime proof:
  - isolated proof: `.\run_H_isolation_success.bat` terminal run `run_id=20260417T111643Z`, `finalized/succeeded`
  - ownership restore: `.\run_H_isolation_resume.bat` then scheduler-owned run `run_id=20260417T113701Z` reached `finalized/succeeded`
  - post-fix outcome evidence (`event_ts_utc >= 2026-04-17T11:13:01Z`):
    - `rows_since_fix=366`
    - `same_target_rows=359`, `same_target_applied=0`
    - pre-fix comparison (`2026-04-17T10:00:00Z` -> `2026-04-17T11:13:01Z`, multi-seller only): `same_target_applied=72/72`
    - `multi_seller_ladder_cap rows=0` (floor-clamped no-headroom decisions now reclassified instead of no-op applied writes)
    - `share_hold rows=353` with `OUTCOME_RECLASSIFIED_NON_ACTION_HOLD` on `329` rows
    - `suppression_reactivation rows=12` (`pending=4`, `expired=8`, `success=0`)
  - current park reason:
    - conversion sign-off thresholds are still not met (`multi_seller_ladder_cap` and `controlled_exit` sample minima not met in this post-fix window; suppression still pending)
  - exact resume trigger: next proof window after pending rows age out of response windows (earliest expected boundary about `2026-04-17T14:00:00Z`)

### Phase 4 - Sign-off and archive
Goal:
- Close the plan with evidence and leave one clear successor state.

Files allowed to change:
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN_STATUS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/CODING_PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_001_REPLY.md`
- archive path only if sign-off is earned

Implementation tasks:
- Re-rate coding status, result status, and sample-size confidence.
- Record whether each scenario is:
  - working
  - partly working
  - blocked by upstream truth
  - still needs logic changes
- Archive the plan only after evidence matches the archive rule in `PLAN.md`.

Isolated verification:
- command:
  - none beyond document consistency unless a scoped follow-up fix is needed
- expected result:
  - final plan status is factual and evidence-backed

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - use the same flow-owned proof window that belongs to the final changed phase before archiving
- artifacts to poll:
  - latest outputs already named above for the final phase that completed
- poll cadence:
  - immediate final review after the last proof window closes
- success threshold:
  - all planned phases are either completed with proof or explicitly parked with exact missing proof
- timeout rule:
  - do not archive on vague status; keep plan active until the missing proof is named exactly
- fallback if forced proof is blocked:
  - keep plan active with the exact blocker, boundary, and resume trigger
- next automatic step after success:
  - archive this plan and stop
- notification mode:
  - passive until milestone or park state
- user interruption threshold:
  - final sign-off or blocked park

Phase status:
- code fix applied: yes
- isolated verification passed: n/a (docs phase)
- monitored validation: completed for runtime ownership chain (pause -> isolated proof -> resume -> scheduler-owned run `run_id=20260417T102219Z` finalized/succeeded and next run observed `run_id=20260417T103625Z`); plan remains active with explicit Phase 3 park condition

### Phase 4 follow-up - A015 latest-run scope repair (`2026-04-17`)
Goal:
- Close the truth-vs-health mismatch where historical `h_ceiling_events` rows were failing the current gate despite fresh slices being clean.

Files changed:
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_a015_health_check_runtime.py`
- plan status/report docs in this plan folder

Implementation completed:
- Added `_h_ceiling_effective_floor_integrity_result(...)` to evaluate only the latest non-empty `run_id` scope.
- Replaced inline all-history scan in `h_ceiling_effective_floor_integrity` with the scoped helper.
- Added targeted runtime tests proving:
  - historical bad rows do not fail when latest run is clean
  - latest-run conflict still fails correctly

Isolated verification:
- command:
  - `pytest tests/test_a015_health_check_runtime.py -k "ceiling_effective_floor_integrity" -q -p no:cacheprovider`
  - `python -m py_compile scripts/flows/A/A015_build_system_health_check.py tests/test_a015_health_check_runtime.py`
- result:
  - pass (`2 passed`)
  - compile pass

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_status.bat`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- artifacts to poll:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/health_status_H.csv`
- success threshold:
  - post-change forced H proof writes `h_ceiling_effective_floor_integrity` as `ok` with `value=0`
- timeout rule:
  - if no post-change forced H proof completes in the next proof window, keep plan parked and record exact latest snapshot timestamp and blocker seen
- fallback if forced proof is blocked:
  - record the exact pause, stale-lock, or ownership-restore blocker before using a later boundary

Follow-up status:
- code fix applied: yes
- isolated verification passed: yes
- live loop verification confirmed
- Verification status: Confirmed by forced H proof window
- Changed at: `2026-04-17T07:43:37Z`
- Latest health snapshot at: `2026-04-17T10:20:22.152493+00:00` (`out/health_status_H.csv`)
- Verifier chain completed:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat` -> terminal proof `run_id=20260417T100532Z`, `finalized/succeeded`
  - `python -m scripts.flows.A.A015_build_system_health_check --profile h --no-toast` -> `h_ceiling_effective_floor_integrity=ok,value=0` in `out/cycle_alerts/checklist_H.csv`
  - `.\run_H_isolation_resume.bat` -> scheduler ownership restored
  - scheduler-owned post-resume run proof: `run_id=20260417T102219Z` finalized/succeeded; next run observed `20260417T103625Z`

### Phase 5 - Undeniable sign-off proof batch
Goal:
- Produce a proof pack that makes the sign-off decision mechanical:
  - either the current H candidate is proven successful on fresh evidence
  - or the task stays open with the exact missing proof and exact failing gate

Files allowed to change:
- `plans/active/h-repricer-ceiling-floor-conversion-v2/CODING_PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN_STATUS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/EXECUTION_BATCH_002_REPLY.md`
- optional proof-only additions:
  - `scripts/one_off/H165_build_h_signoff_proof_pack.py`
  - `tests/test_h165_build_h_signoff_proof_pack.py`

Implementation tasks:
- Lock the final candidate timestamp before sign-off scoring:
  - current candidate timestamp: `2026-04-17T11:13:01Z`
- Refresh H-scoped proof after that timestamp:
  - no stale health snapshot may be used to sign off the candidate
- Build a proof pack output that reports:
  - per-run terminal results after the candidate timestamp
  - `same_target_applied`
  - raw `multi_seller_ladder_cap` population
  - reclassified non-action hold population
  - effective chaseable population if derived
  - suppression and controlled-exit sample sizes and outcomes
  - final live alert states used for sign-off
- Lock the denominator contract in writing before archive:
  - raw legacy ladder population
  - or effective chaseable population
  - no silent denominator change is allowed
- Denominator contract selected for sign-off scoring:
  - `effective_chaseable_population` (raw legacy population remains mandatory observability output)
- Apply explicit exception-list disposition for any remaining WARN before archive.

Isolated verification:
- command:
  - if a proof-builder script is added:
    - `pytest tests/test_h165_build_h_signoff_proof_pack.py -q -p no:cacheprovider`
    - `python -m py_compile scripts/one_off/H165_build_h_signoff_proof_pack.py tests/test_h165_build_h_signoff_proof_pack.py`
- expected result:
  - proof-builder tests pass if added
  - otherwise this phase has no new code-test surface outside document consistency

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python -m scripts.flows.A.A015_build_system_health_check --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- artifacts to poll:
  - `out/cycle_alerts/checklist_H.csv`
  - `out/health_status_H.csv`
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/systems/H/live/H_run_state.json`
  - `out/systems/H/live/H_worker_lifecycle.json`
  - `out/systems/H/live/h_seller_detail_measurement_alerts_latest.csv`
  - proof-pack outputs under `out/analysis_reports/`
- poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+180 minutes` or until 10 scheduler-owned runs finalize
- success threshold:
  - latest H-scoped health snapshot timestamp is later than `2026-04-17T11:13:01Z`
  - `h_ceiling_effective_floor_integrity=ok,value=0`
  - 10 consecutive scheduler-owned H runs after the candidate finalize as `succeeded`
  - `same_target_applied=0` for all rows with `event_ts_utc >= 2026-04-17T11:13:01Z`
  - proof pack reports both raw and reclassified/effective multi-seller populations
  - chosen denominator contract is written explicitly before archive
  - chosen sign-off contract thresholds are met:
    - `multi_seller_ladder_cap` threshold on the chosen basis
    - `suppression_reactivation` rows `>=30`, success `>=2`, expired share `<=55%`
    - `controlled_exit` rows `>=10` and success semantics proven
  - seller-detail live alert is either green at the final boundary or explicitly exception-listed with reason, owner, and review checkpoint
- timeout rule:
  - if the proof pack is incomplete, health is stale, 10 finalized runs are not captured, or thresholds are not met by the end of the bounded window, park with:
    - exact missing artifact
    - exact failing threshold
    - exact next proof boundary
- fallback if forced proof is blocked:
  - record the exact ownership blocker, stale marker, or resume blocker before deferring
- next automatic step after success:
  - archive the plan
- notification mode:
  - passive
- user interruption threshold:
  - sign-off earned, new/worse alert, contradiction, timeout park, or approval-required scope change

Phase status:
- code fix applied:
  - yes
  - added `scripts/one_off/H165_build_h_signoff_proof_pack.py`
  - added `tests/test_h165_build_h_signoff_proof_pack.py`
- isolated verification passed:
  - yes
  - `pytest tests/test_h165_build_h_signoff_proof_pack.py -q -p no:cacheprovider`
  - `python -m py_compile scripts/one_off/H165_build_h_signoff_proof_pack.py`
- monitored validation:
  - completed for Batch 002 forced proof window; parked with exact failing gates
- current blocker snapshot at plan time:
  - fresh H proof is now available:
    - latest H health snapshot `2026-04-17T14:32:51Z` (`> 2026-04-17T11:13:01Z`)
    - `h_ceiling_effective_floor_integrity=ok,value=0`
  - scheduler run-chain gate is met:
    - 13 scheduler-owned runs captured after candidate
    - consecutive succeeded max streak `12`
  - sign-off still blocked by conversion/result gates in proof pack (`out/analysis_reports/h_signoff_proof_pack_20260417T143546Z.json`):
    - multi-seller threshold on chosen contract: `denominator=0` (`effective_chaseable_population`)
    - suppression threshold: `rows=22`, `success=0`, `expired_share_pct=72.73`
    - controlled-exit threshold: `rows=0`, `success=0`
  - live seller-detail gate still failed at proof boundary:
    - `amazon_missing_pressure=warn,current=3,threshold=3` (`snapshot_utc=2026-04-17T14:20:39Z`)
  - exact resume trigger:
    - regenerate proof pack on next finalized scheduler-owned run after `run_id=20260417T142039Z`
    - keep 15-minute cadence until suppression/controlled-exit sample gates move and live seller-detail alert returns to `ok` (or is exception-listed with owner/review checkpoint)

### Phase 6 - Conversion follow-up patch (`2026-04-17`)
Goal:
- move multi-seller rows from no-action hold into explicit ladder-reset writes when upward room exists
- stop counting floor-bound suppression timeout rows as `expired` when they are non-action stalls

Files changed:
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `tests/test_phase1_probe_engine.py`
- `tests/test_phase1_main_loop.py`

Implementation completed:
- Added multi-seller `REGAIN` upward reset behavior:
  - when ladder-cap target is above current price and `max_step_up > 0`, step upward toward the ladder cap (`STEP_REGAIN_MULTI_SELLER_RESET_UP`) instead of forcing `NO_DOWNWARD_HEADROOM` hold.
- Updated timeout closure path for pending outcomes:
  - floor-bound timeout rows now resolve to `aborted` (not `expired`) when reason codes show floor-bound stall behavior.
  - suppression floor-bound timeout rows infer `stop_rule_code=SUPPRESSION_FLOOR_CLAMP_STALLED` when no explicit stop rule exists.

Isolated verification:
- command:
  - `python -m pytest tests/test_phase1_probe_engine.py -q -p no:cacheprovider`
  - `python -m pytest tests/test_phase1_main_loop.py -q -p no:cacheprovider`
  - `python -m py_compile scripts/phase1/phase1_probe_engine.py scripts/phase1/phase1_main_loop.py tests/test_phase1_probe_engine.py tests/test_phase1_main_loop.py`
- result:
  - pass (`7 passed`, `43 passed`)
  - compile pass

Monitored validation (post-change candidate):
- candidate timestamp:
  - `2026-04-17T14:49:33Z`
- runtime proof chain:
  - `.\run_H_isolation_pause.bat` -> success
  - stale marker reconciled: `out/locks/archive/H_run_in_progress.20260417T145240Z.stale.20260417T144139Z.txt`
  - `.\run_H_isolation_success.bat` -> terminal success confirmed `run_id=20260417T145434Z`, `state=finalized`, worker `succeeded`
  - `.\run_H_isolation_resume.bat` -> scheduler ownership restored (owner process chain back online)
- proof-pack outputs:
  - effective: `out/analysis_reports/h_signoff_proof_pack_20260417T154532Z.json`
  - raw: `out/analysis_reports/h_signoff_proof_pack_20260417T154533Z.json`
- observed change in first post-change sample:
  - `effective_chaseable_multi_seller_population` moved from `0` to `8`
  - `multi_seller_ladder_cap` now has `8` rows with `applied=8`
  - `suppression_expired_share_pct` in candidate-window sample is `0.0` (`rows=6`, pending at sample boundary)
  - `controlled_exit` now appears in candidate-window sample (`rows=1`, `success=0`)

Phase 6 status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: `parked pending next proof window` (not yet proven for sign-off)
- Verification status: Pending next cycle check
- Changed at: `2026-04-17T14:49:33Z`
- Latest health snapshot at: `2026-04-17T14:32:51Z`
- Next verifier: next scheduled cycle A015
- exact remaining blockers:
  - health freshness gate is stale vs candidate (`14:32:51Z < 14:49:33Z`)
  - scheduler-owned 10-run chain after candidate not yet accumulated (`3` scheduler-owned succeeded runs so far)
  - conversion sample gates still below threshold (`multi_seller denominator=8`, `suppression rows=6`, `controlled_exit rows=1`)
  - live seller-detail alert still WARN (`amazon_missing_pressure=3/3`)

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
