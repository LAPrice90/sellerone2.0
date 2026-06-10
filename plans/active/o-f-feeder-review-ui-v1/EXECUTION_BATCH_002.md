# Execution Batch 002

## Title
- Implement temporary feeder review tab, inbox, and launcher

## Purpose
- Turn the design-only operator review page into a usable temporary UI flow.

## Scope
- In scope:
  - temporary `New Product Review` tab inside `O400_operator_ui.py`
  - dedicated F feeder review inbox contract
  - per-row `Pass` / `Fail` plus note capture
  - show only 10 undecided rows at a time
  - require an end-of-batch completion checkbox before send
  - clickable `.bat` launcher for the operator UI
- Out of scope:
  - downstream gap-analysis builder
  - feeder approval queue changes
  - PO handoff changes
  - Google Sheets changes

## Key implementation decisions
- Keep feeder review decisions fully separate from:
  - O restock decision events
  - F approval history
- Use `out/systems/F/inbox/feeder_review_events.csv` as the immediate append-only return path.
- In v1, use prior feeder review inbox events to decide which rows are already completed and hide them from the next 10-row window.
- Block submission unless:
  - the operator ticks the batch-complete checkbox
  - every visible row has a `Pass` or `Fail` decision

## Deliverables
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/_schemas.py`
- `tests/test_o_ui_operator_view.py`
- `run_O_operator_ui.bat`
- plan-status updates and proof notes

## Implementation proof
- Added `New Product Review` tab after `Reorder` in the operator UI.
- Added dedicated F inbox contract:
  - `out/systems/F/inbox/feeder_review_events.csv`
- Added 10-row undecided review window logic:
  - current live pass window: `10` visible from `266` undecided
  - current live near-miss window: `10` visible from `3056` undecided
- Added end-of-batch checkbox gating:
  - send is blocked unless all visible rows have `Pass` or `Fail`
  - send is blocked unless the operator confirms the batch is complete
- Added clickable launcher:
  - `run_O_operator_ui.bat`

## Verification
- `python -m py_compile scripts/flows/O/O400_operator_ui.py scripts/flows/F/_schemas.py tests/test_o_ui_operator_view.py`
  - pass
- `pytest tests/test_o_ui_operator_view.py -q`
  - `26 passed`
