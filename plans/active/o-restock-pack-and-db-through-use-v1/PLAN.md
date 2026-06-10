# Plan

## Goal
- Final outcome:
  - Turn the current O restock scaffold into a mock-data-first, pack-aware design task that a non-coder can evaluate step by step before real SKU data is introduced.

## Non-goals
- Do not do:
  - Do not change Google Sheets.
  - Do not rewire the repo-wide canonical database model.
  - Do not claim O is live-loop ready.
  - Do not push real product data into a new pack model until the mock walkthrough is approved.

## Current state
- What exists already:
  - The control docs still label the Operations Loop as planned.
  - The repo already has an `O` flow with isolated scripts for source view, recommendations, review queue, decisions, purchase orders, receiving, ordered-stock state, send-to-Amazon queue, handoff closure, diagnostics, coverage reporting, and an operator UI.
  - The repo has focused O tests across those stages.
  - The restock blueprint already says to launch with sensible defaults and tune from evidence rather than inventing every edge case up front.
- Known pain points:
  - `out/system_health_checklist.csv` currently shows 2 H warnings, but they are outside O scope and do not hard-block planning.
  - `out/systems/O/live/reorder_input_readiness_summary.md` shows 608 rows considered and 0 actionable rows in the last readiness snapshot.
  - `out/systems/O/live/restock_recommendations_live.csv` currently contains UI preview sample rows, not true live recommendations.
  - Pack-aware quantity logic is only blueprinted, not implemented end to end.
  - The current UI currently reduces `qtys` to `supplier_pack_size`, leaves `barcode` blank, and maps `supply_code` from `supplier_code`, which is not enough for real pack-driven ordering.
- Known alerts or reliability concerns:
  - Current O outputs are a mix of real isolated scaffolding and preview/demo state.
  - The Product_DB tie-in is still an interim CSV-cache model, not a dedicated restock database design.

## Target state
- What changes:
  - A new active task defines the pack-aware quantity model in plain English using mock SKU scenarios.
  - The task treats pack truth as product/supplier truth, not as temporary workflow state hidden inside O decisions.
  - The first implementation step becomes a local mock-data pass with 4-5 fake SKUs covering the main quantity shapes.
  - The real-data tie-in is staged after approval: read-only from existing Product_DB preview first, then later upgrade to a normalized supplier/item source when approved.
- What stays the same:
  - A/B/E/H remain the upstream truth providers.
  - O remains the owner of workflow state only.
  - No sheet writes are introduced in this task.

## Systems touched
- Flow(s):
  - O flow planning and UI/reorder design.
- Shared dependencies:
  - `out/product_db_preview.csv`
  - `out/inventory_summaries.csv`
  - `out/sku_sales_velocity.csv`
  - `out/sku_performance_summary.csv`
  - `out/listing_offer_snapshot_latest.csv`
- Runtime or scheduler ownership concerns:
  - None in this planning ticket. This task is planning-only and mock-data-first.

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Product DB preview | A/B integration snapshot | input | `out/product_db_preview.csv` | Interim product and supplier baseline. Read-only in this task. |
| Restock source view | `O001_build_restock_source_view.py` | output | `out/systems/O/live/restock_source_view.csv` | Current one-row-per-SKU O source view. |
| Restock recommendations | `O002_build_restock_recommendations.py` | output | `out/systems/O/live/restock_recommendations_live.csv` | Currently overwritten by UI preview samples. |
| Review queue | `O003_build_restock_review_queue.py` | output | `out/systems/O/live/restock_review_queue.csv` | Operator-facing queue projection. |
| Reorder board logic | `O400_operator_ui.py` | derived view | `scripts/flows/O/O400_operator_ui.py` | Current UI has quantity placeholders rather than full pack logic. |
| Mock SKU scenarios | planning ticket | planning input | `plans/active/o-restock-pack-and-db-through-use-v1/MOCK_SKU_SCENARIOS.csv` | Fake data to learn through use before real-data tie-in. |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `out/system_health_checklist.csv` | n/a | n/a | current repo health snapshot | Current snapshot at 2026-04-16 05:04:58 UTC shows 2 H warnings. Soft-block only for this task. |
| `out/systems/O/live/reorder_input_readiness_summary.md` | stale after code changes | stale after newer runtime proof | O readiness summary | Last summary is 2026-04-04 and should be treated as old context, not current proof. |
| `out/systems/O/live/restock_recommendations_live.csv` | stale when preview rows present | fail for live proof if preview rows present | O recommendation state | Current file is preview/demo state, not live-loop truth. |

## Integration points
- APIs:
  - None in this planning ticket.
- Sheets:
  - Product_DB Google Sheet is upstream context only via `out/product_db_preview.csv`.
- Local DB:
  - No dedicated restock database exists today.
  - For this task, treat Product_DB preview as an interim local cache, not a final canonical DB answer.
- CSV or file handoffs:
  - Mock scenarios will be the first design input.
  - Real data handoff will come later from `out/product_db_preview.csv` and the existing O source contracts.

## Risks and mitigations
- Risk:
  - Pack logic gets pushed into O workflow tables even though it is really product/supplier truth.
  - Mitigation:
    - Keep pack truth in a separate quantity-profile layer for the design pass.
- Risk:
  - Real-data cleanup gets mixed into the first usability pass.
  - Mitigation:
    - Force mock-data-first execution and require approval before any real SKU onboarding.
- Risk:
  - We over-design obscure cases before first operator use.
  - Mitigation:
    - Cover only 4-5 fake scenarios first, then review real pain from operator use.
- Risk:
  - Product_DB authority confusion blocks useful work.
  - Mitigation:
    - Lock a v1 boundary: read Product_DB preview as interim input only, with no sheet changes and no canonical rewrite in this ticket.

## Proof rules
- What counts as code fix applied:
  - Planning files, runbook, and mock scenario definitions are written in a new active plan folder.
- What counts as isolated verification passed:
  - Mock scenarios clearly cover simple units, supplier case multiples, repack/sell-pack logic, and bundle logic.
- What counts as live loop verification confirmed:
  - Not applicable in this ticket. This task is planning-only and uses mock data first.

## Batch list
- Batch 001:
  - Lock pack quantity vocabulary, mock scenarios, and v1 data boundary.
- Batch 002:
  - Implement mock-data quantity model into O source/UI path without touching real Product_DB.
- Batch 003:
  - Add pack-aware readiness checks and operator walkthrough proof on mock rows.
- Batch 004:
  - Introduce a very small approved real-SKU sample after mock approval, still without sheet changes.

## Archive rule
- When this plan can move to archive:
  - After the mock-data-first pack task is implemented, reviewed by the user, and either promoted to a new real-data ticket or completed with an approved follow-on task.
