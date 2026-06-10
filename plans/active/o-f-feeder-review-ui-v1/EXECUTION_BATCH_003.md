# Execution Batch 003

## Title
- Harden feeder review UI decision isolation and batch behavior

## Purpose
- Improve correctness and operator safety in the temporary feeder review tab without changing the commercial workflow.

## Scope
- In scope:
  - review-state isolation by run and lane
  - deterministic next-10 ordering by priority
  - single-write batch submission for feeder review events
  - done-checkbox scoping to current filters
  - targeted regression tests
- Out of scope:
  - downstream feeder review analysis builder
  - changes to approval queue logic
  - Google Sheets changes

## Root-cause fixes
- Fixed decision leakage risk by scoping latest event matching to:
  - `active_supplier_id`
  - `active_run_id`
  - `review_pack_type`
  - `candidate_id`
- Fixed non-deterministic next-10 selection by sorting undecided rows on numeric `review_priority_score` descending before slicing.
- Fixed inefficient write pattern by replacing per-row file rewrites with one append call per submitted batch.
- Fixed done-checkbox state leakage by scoping its session key to lane + supplier + batch + search.

## Files changed
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`

## Verification
- `python -m py_compile scripts/flows/O/O400_operator_ui.py scripts/flows/F/_schemas.py tests/test_o_ui_operator_view.py`
  - pass
- `pytest tests/test_o_ui_operator_view.py -q`
  - `29 passed`
