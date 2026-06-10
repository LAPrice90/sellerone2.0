# Execution Batch 001

## Title
- UI design lock for temporary feeder review page

## Purpose
- Define the temporary operator-review page before any coding starts.

## Scope
- In scope:
  - page placement
  - row layout
  - decision flow
  - note capture
  - send-back path
  - ASIN link rule
- Out of scope:
  - implementation code
  - schema changes
  - UI tests
  - runtime proof

## Key design decisions
- Use the existing `O400_operator_ui.py` tab pattern.
- Add a new tab called `New Product Review`.
- Keep the primary decision binary for v1:
  - `Pass`
  - `Fail`
- Capture reasoning with a note box on every reviewed row.
- Use a dedicated feeder review event inbox instead of piggybacking on restock events.
- Add an external Amazon link icon using zero-padded 10-character ASINs.

## Deliverables
- `PROJECT_BRIEF.md`
- `PLAN.md`
- `UI_DESIGN.md`
- `CODING_PLAN.md`
- `PLAN_STATUS.md`
- `RUNBOOK.md`
- `EXECUTION_BATCH_001.md`
