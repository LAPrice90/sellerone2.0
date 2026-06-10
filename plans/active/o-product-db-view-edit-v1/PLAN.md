# Plan

## Goal
- Final outcome:
  - a dedicated product database browse page and separate edit workflow that feel close to the finished operator system, using one merged O-owned read model over existing A/B/E/H/O sources

## Non-goals
- Do not do:
  - direct Google Sheets writes
  - inline editing on the browse page
  - rework reorder recommendation logic
  - treat `out/product_db_preview.csv` as a new canonical local DB without an explicit ownership ticket

## Current state
- What exists already:
  - `out/product_db_preview.csv` supplies product identity, supplier baseline, buy-cost baseline, sale status, and VAT rate
  - O already has live outputs for reorder queue and ordered stock state
  - E already has demand and economics outputs such as `out/sku_sales_velocity.csv` and `out/sku_performance_summary.csv`
  - `scripts/flows/O/O400_operator_ui.py` already proves the repo can support operator-facing O pages
- Known pain points:
  - no single read-friendly database view
  - fixed truth and live operating truth are not separated for the user
  - status language is split across Product_DB `sale_status` and O `queue_status`
  - pack and batch rules are visible in some places but not owned clearly in one maintenance surface
- Known alerts or reliability concerns:
  - latest global health snapshot at `2026-04-17T05:04:38.511598+00:00` is `FAIL fail=1 warn=3`
  - fail:
    - `h_ceiling_effective_floor_integrity`
  - warns:
    - `h_strategy_expired_share_multi_seller_ladder_cap`
    - `h_strategy_sample_size_single_rival_reset`
    - `h_spapi_lock_present`
  - these are H-flow alerts, not O-flow blockers for planning this page, but they remain active

## Target state
- What changes:
  - O gets a new read model:
    - `out/systems/O/live/product_db_operator_view.csv`
  - O gets a dedicated browse page:
    - `scripts/flows/O/O410_product_database_ui.py`
  - O gets a separate edit surface:
    - `scripts/flows/O/O420_product_database_edit_ui.py`
  - manual edits write to an O inbox event file rather than editing the browse view directly
- What stays the same:
  - Product_DB preview remains a source input, not a UI-owned write target
  - reorder stays a separate action page
  - A/B/E/H remain owners of their existing truth layers

## Systems touched
- Flow(s):
  - O browse and edit surfaces
- Shared dependencies:
  - A/B integration snapshot via `out/product_db_preview.csv`
  - E demand/economics outputs
  - O operational queue and ordered-stock outputs
  - optional H market context only where already present in existing summaries
- Runtime or scheduler ownership concerns:
  - none for planning and read-only UI work
  - future edit-apply path must stay isolated from runtime loops until ownership is defined

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Product_DB preview | A/B integration snapshot | input | `out/product_db_preview.csv` | current local preview of Product_DB truth |
| Sales velocity | E | input | `out/sku_sales_velocity.csv` | demand context |
| Performance summary | E | input | `out/sku_performance_summary.csv` | ROI and economics context |
| Restock review queue | O | input | `out/systems/O/live/restock_review_queue.csv` | current snooze/review overlay |
| Ordered stock state | O | input | `out/systems/O/live/ordered_stock_state.csv` | open ordered quantity overlay |
| Product DB operator view | O030 proposed | output | `out/systems/O/live/product_db_operator_view.csv` | one row per SKU for browse UI |
| Product DB edit events | O proposed | output | `out/systems/O/inbox/product_db_edit_events.csv` | separate edit submission path |
| Product DB edit holds | O proposed | output | `out/systems/O/live/product_db_edit_holds.csv` | validation failures for edit submissions |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `out/product_db_preview.csv` | add in this ticket | add in this ticket | proposed new O check | page should not silently show stale DB preview |
| `out/sku_sales_velocity.csv` | existing E ownership | existing E ownership | existing E profile | use as read-only overlay |
| `out/sku_performance_summary.csv` | existing E ownership | existing E ownership | existing E profile | use as read-only overlay |
| `out/systems/O/live/restock_review_queue.csv` | existing O ownership | existing O ownership | add O-page freshness note | needed for snooze/status overlay |
| `out/systems/O/live/ordered_stock_state.csv` | existing O ownership | existing O ownership | add O-page freshness note | needed for open ordered quantity |

## Integration points
- APIs:
  - none directly in this ticket
- Sheets:
  - read-only boundary only through existing local preview file
- Local DB:
  - display uses local preview plus merged overlays
  - edit path should target a local event inbox first
- CSV or file handoffs:
  - O browse page reads merged snapshot
  - O edit page writes edit events
  - later apply script validates and updates approved local truth layer only after ownership is defined

## Risks and mitigations
- Risk:
  - page becomes a giant spreadsheet clone
  - Mitigation:
    - keep a strict glance layer and move the rest into expansion/detail views
- Risk:
  - status meaning becomes ambiguous
  - Mitigation:
    - define one displayed `operational_status` with fixed precedence over raw source statuses
- Risk:
  - browse page accidentally becomes an edit page
  - Mitigation:
    - no inline edits on the main list; only `View` and `Edit`
- Risk:
  - fixed vs derived truth gets mixed and creates trust issues
  - Mitigation:
    - every field group must be labeled as fixed editable, derived read-only, or status overlay
- Risk:
  - pack rules remain incomplete and degrade downstream ordering
  - Mitigation:
    - include pack completeness and blocker flags in the operator view from day one

## Proof rules
- What counts as code fix applied:
  - plan-approved scripts and contracts exist for browse view, edit events, and UI pages
- What counts as isolated verification passed:
  - targeted O tests prove row assembly, status mapping, expansion field grouping, and edit-event validation
- What counts as live loop verification confirmed:
  - not required for the read-only browse page
  - later edit apply path will require owned proof after an explicit approval ticket

## Batch list
- Batch 001:
  - build `product_db_operator_view.csv` contract and read model
- Batch 002:
  - build the read-only database browse page
- Batch 003:
  - add row detail expansion and status overlays
- Batch 004:
  - add separate edit page and edit-event inbox
- Batch 005:
  - add edit validation, holds, and freshness checks

## Archive rule
- When this plan can move to archive:
  - after the browse page and edit workflow are implemented, tested, and accepted as the working product database surface
