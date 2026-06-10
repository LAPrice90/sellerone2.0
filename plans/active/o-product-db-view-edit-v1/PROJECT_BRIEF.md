# Project Brief

## Ticket
- Ticket name: O Product Database View And Edit System v1
- Date opened: 2026-04-17
- Owner: Codex

## Business problem
- There is no operator-friendly place to browse the product database as one working system.
- Fixed product truth, supplier buying truth, pack rules, tax settings, and live operating overlays are spread across different files.
- The reorder page is for action, not for understanding or maintaining product truth.

## Goal
- Design a near-finished product database page that shows the right information at a glance without turning into a data wall.
- Keep the browse page read-first.
- Put all manual entry into a separate edit workflow.
- Define the boundary between fixed truth and derived truth so the UI does not mix them.

## Why now
- The operations loop is now real enough that product truth needs its own home.
- Reorder quality depends on pack, case, VAT, and supplier truth being visible and maintainable.
- If this page is not designed now, product maintenance will keep leaking into action pages.

## Constraints
- Existing system boundaries:
  - Do not change Google Sheets unless explicitly asked.
  - Do not claim `out/product_db_preview.csv` is the canonical editable local DB; today it is a local preview of Product_DB truth exported by A/B scripts.
  - O flow should consume existing A/B/E/H outputs rather than duplicate them.
- Out of scope:
  - Rebuilding upstream vetting logic.
  - Rebuilding reorder quantity recommendation logic.
  - Direct sheet writeback in this ticket.
- Approval-sensitive areas:
  - Any change to Product_DB ownership.
  - Any sheet write path.
  - Any local canonical DB replacement claim.

## Definition of success
- Observable result 1:
  - one active plan folder exists for the product database page with clear browse and edit architecture
- Observable result 2:
  - the plan separates fixed editable truth from derived read-only truth
- Observable result 3:
  - the plan names the exact data contracts, page layout, statuses, and phased implementation path

## Reference material
- Research notes:
  - `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
  - `project_control/O_REORDER_BOARD_BLUEPRINT.md`
  - `project_control/O_DATA_SOURCE_MAP.md`
- Related repo files:
  - `scripts/flows/O/_source_contracts.py`
  - `scripts/flows/O/O001_build_restock_source_view.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - `out/product_db_preview.csv`
- Prior tickets or plans:
  - `plans/active/o-restock-pack-and-db-through-use-v1/`
