# Coding Plan

Date: 2026-04-22
Scope: Temporary feeder review tab inside the operator UI, plus feeder review inbox and launcher

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Lock UI design, page boundary, and event path | `plans/active/o-f-feeder-review-ui-v1/*`, `WORK_LOG.md` | docs review | no | completed |
| Phase 1 | Implement temporary UI tab in `O400_operator_ui.py` | `scripts/flows/O/O400_operator_ui.py`, `tests/test_o_ui_operator_view.py`, `run_O_operator_ui.bat`, plan files | targeted O UI tests | no | completed |
| Phase 2 | Add feeder review event inbox contract and send path | `scripts/flows/F/_schemas.py`, `scripts/flows/O/O400_operator_ui.py`, `tests/test_o_ui_operator_view.py`, plan files | targeted F and O tests | no | completed |
| Phase 2A | Hardening pass on review isolation and batch behavior | `scripts/flows/O/O400_operator_ui.py`, `tests/test_o_ui_operator_view.py`, plan files | targeted O UI regression tests | no | completed |
| Phase 2B | User-flow improvements before live review | `scripts/flows/O/O400_operator_ui.py`, `tests/test_o_ui_operator_view.py`, `run_O_operator_ui.bat`, plan files | targeted O UI regression tests | no | completed |
| Phase 3 | Pilot live review batches | runtime artifacts only | targeted artifact checks | yes | planned |

## 2) Phase details

### Phase 0 - Design lock
Goal:
- Define exactly how the feeder review page should work before any coding starts.

Files allowed to change:
- `plans/active/o-f-feeder-review-ui-v1/PROJECT_BRIEF.md`
- `plans/active/o-f-feeder-review-ui-v1/PLAN.md`
- `plans/active/o-f-feeder-review-ui-v1/UI_DESIGN.md`
- `plans/active/o-f-feeder-review-ui-v1/CODING_PLAN.md`
- `plans/active/o-f-feeder-review-ui-v1/PLAN_STATUS.md`
- `plans/active/o-f-feeder-review-ui-v1/RUNBOOK.md`
- `plans/active/o-f-feeder-review-ui-v1/EXECUTION_BATCH_001.md`
- `WORK_LOG.md`

Implementation tasks:
- lock the page placement
- lock the visible fields
- lock the pass/fail + notes input model
- lock the append-only send-back path
- lock the ASIN link rule

Isolated verification:
- command:
  - review the design files and confirm the page boundary and event boundary are explicit
- expected result:
  - one active plan folder exists with a design brief, plan, UI design, coding plan, runbook, and batch file

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - design package complete
- timeout rule:
  - none
- next automatic step after success:
  - wait for user approval before implementation

Phase status:
- code fix applied:
  - yes, planning files written
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 1 - Temporary UI tab
Goal:
- Add a feeder review tab to the existing operator UI without disturbing reorder behavior.

Files allowed to change:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `run_O_operator_ui.bat`
- `plans/active/o-f-feeder-review-ui-v1/PLAN_STATUS.md`
- `plans/active/o-f-feeder-review-ui-v1/EXECUTION_BATCH_002.md`
- `plans/active/o-f-feeder-review-ui-v1/CODING_PLAN.md`
- `WORK_LOG.md`

Implementation goals:
- add `New Product Review` tab
- keep the restocker visual language
- render batch-based feeder review cards
- show only up to 10 undecided rows at a time
- require an end-of-batch completion checkbox before send
- after send, advance to the next undecided 10 rows automatically
- provide a clickable UI launcher batch file

Isolated verification:
- `python -m py_compile scripts/flows/O/O400_operator_ui.py tests/test_o_ui_operator_view.py`
- `pytest tests/test_o_ui_operator_view.py -q`

### Phase 2 - Event path and analysis
Goal:
- Capture UI reviews safely and convert them into useful analysis.

Files allowed to change:
- `scripts/flows/F/_schemas.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-f-feeder-review-ui-v1/PLAN_STATUS.md`
- `plans/active/o-f-feeder-review-ui-v1/EXECUTION_BATCH_002.md`
- `plans/active/o-f-feeder-review-ui-v1/CODING_PLAN.md`
- `WORK_LOG.md`

Implementation goals:
- append-only feeder review event inbox
- write reviewed rows back through one button
- keep feeder review decisions separate from O restock events and F approval logs
- use the inbox itself as the immediate review-history source for next-10 pagination in v1

Isolated verification:
- confirm `feeder_review_events` contract exists
- confirm UI submission writes append-only inbox rows
- confirm submitted rows are hidden from the next undecided batch

### Phase 3 - Pilot
Goal:
- Use the temporary page against the current live feeder review batches.

Proof target:
- the user can review a batch, send it, and see the result captured for analysis without touching the CSVs directly

### Phase 2A - Hardening pass
Goal:
- Remove correctness risks in how "next 10" and prior review events are resolved.

Files changed:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-f-feeder-review-ui-v1/EXECUTION_BATCH_003.md`

Implementation outcomes:
- latest review event matching is now scoped by run and pack identity
- undecided rows are priority-sorted before `head(10)`
- feeder review submission writes the full reviewed set in one append call
- done-checkbox key is scoped to the current filter set

Isolated verification:
- `python -m py_compile scripts/flows/O/O400_operator_ui.py scripts/flows/F/_schemas.py tests/test_o_ui_operator_view.py`
- `pytest tests/test_o_ui_operator_view.py -q`
- result: `29 passed`

### Phase 2B - User-flow improvements
Goal:
- Improve operator clarity and correction capability before first live batch.

Files changed:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `run_O_operator_ui.bat`
- `plans/active/o-f-feeder-review-ui-v1/EXECUTION_BATCH_004.md`

Implementation outcomes:
- sent decisions are now visible in-page for current filters
- per-row reopen action is available from sent decisions
- undo-last-send path is available for current lane in current session
- progress metrics are visible for current view and current 10-row window
- widget state is scoped by lane and run identity to avoid row-state bleed
- launcher now shows a friendlier error hint and pauses on failure

Isolated verification:
- `python -m py_compile scripts/flows/O/O400_operator_ui.py tests/test_o_ui_operator_view.py`
- `pytest tests/test_o_ui_operator_view.py -q`
- result: `32 passed`

## 3) Current implementation target

Batch 002 will deliver:
- a clickable `run_O_operator_ui.bat`
- a `New Product Review` tab inside the existing operator UI
- lane selection for `Passes` and `Near misses`
- up to 10 undecided rows shown at a time
- per-row `Pass` / `Fail` decision and note capture
- an end-of-batch checkbox that blocks send until the visible rows are complete
- append-only writes to `out/systems/F/inbox/feeder_review_events.csv`

### Phase 2C - Original 5-point score visibility + backfill hardening
Status:
- complete (code + isolated proof + live artifact check)
Goal:
- Keep the original 5-point test visible in feeder review outputs and UI, and improve score coverage for near-miss rows where candidate IDs include alternate-ASIN suffixes.
Allowed files:
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_o_ui_operator_view.py`
- this coding plan file
Implementation tasks:
1. Keep the score/result/status/gate fields in pass and near-miss outputs and loader defaults.
2. Add a safe candidate-id fallback for first-check lookups using base candidate id before `__` when present.
3. Prove no regression in existing matching paths and no score/result mismatch where scores exist.
Isolated verification:
- `python -m pytest tests/test_f019_build_live_price_file_near_miss_pack.py tests/test_o_ui_operator_view.py -q`
- `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py scripts/flows/O/O400_operator_ui.py`
Monitored validation:
- live proof needed:
  - no loop ownership handoff required for this phase
- artifact check after one F019 run:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- success threshold:
  - output columns exist in both packs
  - score/result mismatch count remains `0` where scores are present
  - near-miss scored-row count is equal or higher than the pre-change baseline
- Evidence:
- `python -m pytest tests/test_f019_build_live_price_file_near_miss_pack.py tests/test_o_ui_operator_view.py -q` -> `33 passed`
- `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py scripts/flows/O/O400_operator_ui.py` -> success
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py` regenerated latest packs at `2026-04-23T07:27:49Z`.
- Current latest pack consistency:
  - pass rows `266`, scored rows `266`, score/result mismatch `0`
  - near-miss rows `3056`, scored rows `2`, score/result mismatch `0`
- Candidate-base fallback was added for future alt-candidate rows and is regression-locked by unit tests.
