# Coding Plan

Date: `2026-04-24`
Scope: repair the H `item_offers` budget regression that is making every H run behave like a one-cycle retry sweep, then prove the fix through the H controlled proof window.

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 | Fix the item-offers budget seed so H only expands beyond the base budget when the live retry queue proves it is needed | `scripts/cycles/run_H_pricing_cycle.py`, `tests/test_h_item_offers_retry_queue.py`, this plan folder | `python -m py_compile`, scoped `pytest` | yes | completed |
| Phase 2 | Run the H controlled proof window and confirm the repaired budget reaches terminal truth without breaking ownership restoration | no new code files unless proof exposes a direct defect | H controlled one-shot plus fresh H checklist | yes | completed |

## 2) Phase details

### Phase 1 - Budget seed fix
Goal:
- stop H from promoting the item-offers budget from `15` to the full candidate set when `active_pending_count=0`

Files allowed to change:
- `scripts/cycles/run_H_pricing_cycle.py`
- `tests/test_h_item_offers_retry_queue.py`
- `plans/active/h-item-offers-budget-repair-2026-04-24/CODING_PLAN.md`

Implementation tasks:
- remove the synthetic pending-count seed from the initial item-offers budget calculation
- keep one-cycle retry expansion available when the live retry queue actually contains pending ASINs
- add a regression test that covers the no-pending and active-pending paths at the budget-planning layer

Isolated verification:
- command:
- `python -m py_compile scripts/cycles/run_H_pricing_cycle.py tests/test_h_item_offers_retry_queue.py`
- `pytest tests/test_h_item_offers_retry_queue.py -q`
- expected result:
- compile passes and the new regression test proves the budget stays at the base cap when the retry queue is empty

Monitored validation:
- live proof needed:
- yes
- forced proof window:
- `python scripts/one_off/P002_plan_forced_proof_window.py --flow h --format text`
- artifacts to poll:
- `out/systems/H/live/H_cycle.log`
- `out/systems/H/live/H_cycle_last_terminal_info.txt`
- `out/systems/H/live/H_cycle_last_publish_info.txt`
- `out/cycle_alerts/checklist_H.csv`
- `out/systems/H/live/H_runtime_status.json`
- poll cadence:
- proof-run boundary checks during the controlled run, then one ownership-restoration check after resume
- success threshold:
- controlled H run reaches publish and finalized markers
- fresh `checklist_H.csv` has `0 FAIL`
- repaired run no longer logs `item_offers_budget_override ... effective_budget=65 ... active_pending_count=0`
- timeout rule:
- if the controlled proof cannot obtain the H pause boundary safely, record the blocker and do not claim runtime proof
- fallback if forced proof is blocked:
- park on the exact H ownership blocker and resume at the next safe controlled isolation boundary
- next automatic step after success:
- summarize current cycle repair status and remaining non-H failures from the MOT
- notification mode:
- passive unless proof completes or a blocker appears
- user interruption threshold:
- proof complete, new FAIL, contradictory runtime evidence, or blocked isolation window

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: completed

### Phase 2 - Controlled H proof
Goal:
- prove the repaired H runtime through the approved H-owned isolation path and confirm ownership restoration

Files allowed to change:
- `plans/active/h-item-offers-budget-repair-2026-04-24/CODING_PLAN.md`

Implementation tasks:
- pause H ownership safely
- run the guarded H controlled proof
- run fresh H-scoped health after the controlled run finalizes
- resume H ownership and confirm a live owner is back

Isolated verification:
- command:
- `run_H_isolation_status.bat`
- `run_H_isolation_pause.bat`
- `run_H_isolation_success.bat`
- `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
- `run_H_isolation_resume.bat`
- expected result:
- proof run finalizes, H health remains at `0 FAIL`, and resumed ownership is visible again

Monitored validation:
- live proof needed:
- yes
- forced proof window:
- H controlled isolation per `P002_plan_forced_proof_window.py --flow h`
- artifacts to poll:
- `out/systems/H/live/H_cycle.log`
- `out/systems/H/live/H_pricing_cycle.lock`
- `out/systems/H/live/H_runtime_status.json`
- poll cadence:
- first check immediately after the controlled run, then one post-resume ownership check
- success threshold:
- terminal marker written, publish marker written, fresh H checklist written, resumed owner observed
- timeout rule:
- stop when the proof chain completes or when ownership restoration fails
- fallback if forced proof is blocked:
- record the exact blocker and exact resume artifact; do not downgrade to vague next-cycle wording
- next automatic step after success:
- finish the ticket summary with the repaired H issue and the remaining A/B MOT blockers
- notification mode:
- passive unless proof completes or blocks
- user interruption threshold:
- proof complete, resume failure, new FAIL, or contradictory ownership evidence

Phase status:
- code fix applied: yes
- isolated verification passed: yes
- monitored validation: completed

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
