# Project Brief

## Ticket
- Ticket name: O Restock Phase 1A - Pack-aware quantity model and database tie-in
- Date opened: 2026-04-16
- Owner: Codex

## Business problem
- The O restock flow already exists as isolated code and tests, but it is not yet shaped around the real buying decisions you need to make as an operator.
- The current design does not yet lock where pack and bundle truth should live.
- The current O UI and source view do not yet carry enough structured quantity data for products bought in cases, repacked into sell packs, or sold as bundles.
- The current repo also does not have a dedicated restock database. Today O mainly reads `out/product_db_preview.csv`, which is a local CSV mirror of the Product_DB sheet.

## Goal
- Create a mock-data-first task that turns the current O scaffold into a user-shaped pack-aware design pass.
- Lock the plain-English workflow before real product data is introduced.
- Decide the short-term data boundary for pack truth without changing Google Sheets or rewriting the wider database architecture.

## Why now
- Price-list scanner work is already running in the background, so this is the right moment to resume operations-loop design.
- The repo already has enough O scaffolding to learn by using it, which matches the agreed planning rule: start with sensible defaults, then tune from evidence.
- Pack-aware ordering is a known gap and should be solved before real restock workflow is treated as operator-ready.

## Constraints
- Existing system boundaries:
  - Do not run A scripts unless explicitly asked.
  - Do not change Google Sheets unless explicitly asked.
  - Do not change local DB or sheet truth to force them to match without approval.
  - Respect the single-source rule from the restock blueprint: reuse A/B/E/H truth and create new O-owned files only for new workflow state.
- Out of scope:
  - No live scheduler wiring for O.
  - No Google Sheets schema changes in this ticket.
  - No full supplier-normalization project in this ticket.
  - No final canonical database decision for the whole repo in this ticket.
- Approval-sensitive areas:
  - Any Product_DB sheet changes.
  - Any decision to make a new canonical local database authority.
  - Any move from mock data to real SKU data.

## Definition of success
- Observable result 1: one clear task exists for pack-aware restock design using made-up data first.
- Observable result 2: the task explains, in plain English, how quantity logic should work for simple SKUs, case-bought SKUs, and repack/bundle SKUs.
- Observable result 3: the task clearly states where pack truth should live in v1 and how it will later connect to real product data without hidden assumptions.

## Reference material
- Research notes:
  - `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
  - `project_control/O_REORDER_BOARD_BLUEPRINT.md`
  - `project_control/O_DATA_SOURCE_MAP.md`
  - `project_control/O_REORDER_INPUT_RULES.md`
- Related repo files:
  - `scripts/cycles/run_O_cycle.py`
  - `scripts/flows/O/O001_build_restock_source_view.py`
  - `scripts/flows/O/O002_build_restock_recommendations.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - `out/systems/O/live/reorder_input_readiness_summary.md`
  - `out/systems/O/live/restock_recommendations_live.csv`
- Prior tickets or plans:
  - `project_control/EXPECTATIONS/operations_loop_expectations.md`
  - `project_control/TASK_QUEUE.md`
