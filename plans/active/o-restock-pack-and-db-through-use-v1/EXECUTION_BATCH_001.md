# Execution Batch 001

## Purpose
- Lock the first usable pack-aware restock shape with fake SKU data only.

## Scope guardrails
- Only do:
  - add a mock quantity-profile layer
  - surface pack-aware quantity meaning in O source/UI path
  - add explicit blocker reasons for missing quantity truth
- Do not change:
  - Google Sheets
  - Product_DB authority model
  - A/B/E/H ownership boundaries
- Do not add:
  - live scheduler ownership for O
  - supplier-specific restock logic
  - real-SKU onboarding

## Files allowed to change
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O003_build_restock_review_queue.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `tests/test_o001_restock_source_view.py`
- `tests/test_o020_reorder_input_coverage.py`
- `tests/test_o_ui_operator_view.py`
- new mock fixture files under `tests/fixtures/o_phase_packs/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `PLAN.md`
- supporting files:
  - `RUNBOOK.md`
  - `MOCK_SKU_SCENARIOS.csv`
  - `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
  - `project_control/O_REORDER_BOARD_BLUEPRINT.md`

## Tasks
### Task 1
- Goal:
  - lock the mock quantity fields and their plain-English meaning
- Files:
  - O schemas, mock fixtures, tests
- Notes:
  - keep the field set small and readable

### Task 2
- Goal:
  - make the O UI show order meaning clearly for mock rows
- Files:
  - O UI, review queue, coverage report, tests
- Notes:
  - operator quantity must not depend on mental conversion

## Tests
- Command:
  - targeted `pytest` for O source, O coverage, and O UI tests
- Expected result:
  - mock quantity cases pass and no unrelated flow is used as a gate

## Monitoring plan
- Live proof needed:
  - no
- Artifacts to poll:
  - none
- Poll cadence:
  - none
- Success threshold:
  - mock scenarios render clearly and tests pass
- Timeout rule:
  - stop and record the exact scenario still causing confusion
- Next phase after success:
  - Batch 002 for pack-aware blocker reporting and operator walkthrough polish
- Notification mode:
  - milestone only
- User interruption threshold:
  - approval needed before the next batch

## Proof required
- Row counts:
  - mock rows present in expected outputs
- Health rows:
  - any new O-related blocker reasons visible
- Output files:
  - relevant O outputs and/or fixture-backed artifacts
- Notes:
  - planning ticket does not claim live-loop proof

## Completion checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Tests passed
- [x] Proof captured
- [x] Reply file updated
