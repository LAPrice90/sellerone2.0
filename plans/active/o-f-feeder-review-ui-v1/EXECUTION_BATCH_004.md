# Execution Batch 004

## Title
- User-flow and ease-of-use improvements for New Product Review

## Purpose
- Improve operator usability before live review by adding safer correction paths and clearer on-screen progress.

## Scope
- In scope:
  - add sent-decision review panel for current filters
  - add reopen and undo-last-send flows
  - improve per-window progress context
  - scope widget state by lane and run identity
  - improve filter options to favor actionable undecided rows
  - improve launcher failure message for non-technical use
- Out of scope:
  - downstream gap-analysis builder
  - feeder approval queue changes

## UX changes delivered
- Added "Recent sent decisions in this view" panel with per-row `Reopen`.
- Added `Undo Last Send` action (current lane, current browser session).
- Added explicit progress metrics:
  - rows in view
  - undecided
  - already reviewed
  - current window size
- Added current-window decision summary:
  - pass selected
  - fail selected
  - remaining
- Added product image tile support with fallback placeholder.
- Updated launcher to show a friendly failure message and pause on error.

## Root-cause quality fixes included
- Added shared helper for source + latest-event merge to avoid duplicated logic paths.
- Added sent-decision builder for safe operator-side visibility.
- Kept append-only event lineage and used explicit reopen events for corrections.

## Files changed
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `run_O_operator_ui.bat`

## Verification
- `python -m py_compile scripts/flows/O/O400_operator_ui.py tests/test_o_ui_operator_view.py`
  - pass
- `pytest tests/test_o_ui_operator_view.py -q`
  - `32 passed`
- live-state check:
  - passes: `10` visible from `266` undecided
  - near misses: `10` visible from `3056` undecided
