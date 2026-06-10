# Coding Plan

Date: 2026-04-17
Scope: Product database browse page and separate edit workflow for O, using current local source truth and a new O-owned merged read model

## 0) Latest execution evidence

- Implementation completed on 2026-04-17 across:
  - `scripts/flows/O/O030_build_product_db_operator_view.py`
  - `scripts/flows/O/O410_product_database_ui.py`
  - `scripts/flows/O/O420_product_database_edit_ui.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - `scripts/cycles/run_O_cycle.py`
  - `scripts/flows/O/_schemas.py`
- Isolated verification command:
  - `pytest -q tests/test_o000_paths_and_schemas.py tests/test_o_cycle_runner.py tests/test_o_ui_operator_view.py tests/test_o030_build_product_db_operator_view.py tests/test_o410_product_database_ui.py tests/test_o420_product_database_edit_ui.py`
- Result:
  - `38 passed`

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Lock plan, UI blueprint, and data ownership model | `plans/active/o-product-db-view-edit-v1/*` | docs review | no | completed |
| Phase 1 | Build merged operator-view dataset | O flow read-model files + new tests only | targeted O tests | no | completed |
| Phase 2 | Build read-only browse page | O UI files + UI tests only | targeted O UI tests | no | completed |
| Phase 3 | Add detail expansion and status overlays | O UI files + UI tests only | targeted O UI tests | no | completed |
| Phase 4 | Build separate edit page and edit-event inbox | O UI files, O edit-event contracts, tests | targeted O tests + UI tests | no | completed |
| Phase 5 | Add edit validation, holds, and freshness checks | O apply/validation files and tests | targeted O tests | no | completed |

## 2) Phase details

### Phase 0 - Planning lock
Goal:
- Lock the browse page shape, edit-page boundary, and fixed-vs-derived field ownership before implementation.

Files allowed to change:
- `plans/active/o-product-db-view-edit-v1/*`

Implementation tasks:
- Write project brief, plan, coding plan, data contracts, runbook, and UI blueprint.
- Record active alert context from latest health snapshot.
- Define the target outputs and exact page behavior.

Isolated verification:
- command:
  - review plan folder contents and confirm they reflect the actual repo sources
- expected result:
  - one active plan folder exists with complete browse and edit architecture

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - planning files are complete and consistent with current repo boundaries
- timeout rule:
  - none
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - wait for user approval to start Batch 001 implementation
- notification mode:
  - milestone only
- user interruption threshold:
  - ask only if scope changes

Phase status:
- code fix applied:
  - yes, planning files written
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 1 - Build merged operator-view dataset
Goal:
- Build one read-friendly row per SKU for the database page, without making the page join raw source files live in the UI.

Files allowed to change:
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- new `scripts/flows/O/O030_build_product_db_operator_view.py`
- `tests/test_o000_paths_and_schemas.py`
- new `tests/test_o030_build_product_db_operator_view.py`

Implementation tasks:
- Define `product_db_operator_view` contract.
- Read from `out/product_db_preview.csv`, `out/sku_sales_velocity.csv`, `out/sku_performance_summary.csv`, `out/systems/O/live/restock_review_queue.csv`, and `out/systems/O/live/ordered_stock_state.csv`.
- Build a single `operational_status` field with clear precedence.
- Add pack completeness flags and data-issue flags.

Isolated verification:
- command:
  - targeted `pytest` for O schemas and new read-model tests
- expected result:
  - one row per SKU is built with stable status, pack, stock, ordered, demand, and economics fields

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - merged snapshot builds correctly from fixtures and sample local files
- timeout rule:
  - record the exact conflicting source field or missing source contract
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 2
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if source ownership becomes contradictory

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 2 - Build read-only browse page
Goal:
- Deliver the main product database page as a read-first operational surface.

Files allowed to change:
- new `scripts/flows/O/O410_product_database_ui.py`
- shared O UI helpers only where needed
- new `tests/test_o410_product_database_ui.py`

Implementation tasks:
- Add summary counts for Live, Snoozed, Discontinued, Dropped, and data issues.
- Add filters for search, supplier, status, pack mode, and issues-only.
- Render a dense browse list with glance fields only.
- Keep the main page read-only.

Isolated verification:
- command:
  - targeted `pytest` for browse-page helpers and display mapping
- expected result:
  - operator can browse the DB without being flooded by secondary fields

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - page reads clearly at glance level and handles empty/filter states cleanly
- timeout rule:
  - record which glance field still forces too much expansion
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 3
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if page density becomes contradictory

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 3 - Add detail expansion and status overlays
Goal:
- Show the rest of the product truth without turning the browse page into a data dump.

Files allowed to change:
- `scripts/flows/O/O410_product_database_ui.py`
- shared O UI helpers only where needed
- `tests/test_o410_product_database_ui.py`

Implementation tasks:
- Add row expansion or side-detail view.
- Group detail content into:
  - Identity
  - Supply and Packs
  - Economics and VAT
  - Stock and Demand
  - Operations and Notes
  - Audit
- Display the raw source statuses as supporting detail under the single displayed status.

Isolated verification:
- command:
  - targeted `pytest` for detail grouping and status mapping
- expected result:
  - the operator can open more detail without losing the main browse flow

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - no key detail field requires the user to leave the page for normal browsing
- timeout rule:
  - record which detail group still feels overloaded
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 4
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if row detail shape needs a user decision

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 4 - Build separate edit page and edit-event inbox
Goal:
- Keep all manual entry off the browse page and move it into a dedicated edit workflow.

Files allowed to change:
- `scripts/flows/O/_schemas.py`
- new `scripts/flows/O/O420_product_database_edit_ui.py`
- new O edit-event helpers
- new `tests/test_o420_product_database_edit_ui.py`
- new O edit contract tests

Implementation tasks:
- Define `product_db_edit_events.csv`.
- Build the edit page with field groups for:
  - Product and Supplier
  - Pack and Batch Rules
  - VAT and Commercial
  - Status and Notes
- Save one full editable snapshot per submit.
- Keep derived fields visible as read-only context alongside the form.

Isolated verification:
- command:
  - targeted `pytest` for edit form mapping and inbox row output
- expected result:
  - saved edits land as clean event rows without touching the source preview directly

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - operator can edit fixed fields in one place without disturbing the browse page
- timeout rule:
  - record the exact field group that still mixes fixed and derived truth
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 5
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if an edit field needs ownership approval

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 5 - Add edit validation, holds, and freshness checks
Goal:
- Make the system safe enough to trust before any apply path is approved.

Files allowed to change:
- new O edit validation/apply helpers
- O schema and test files
- O health/checklist additions

Implementation tasks:
- Validate submitted edits before they are considered apply-ready.
- Write holds for bad inputs such as invalid pack conversions or blank required supplier fields.
- Add freshness checks for the browse snapshot inputs.
- Add a simple operator-visible issues summary.

Isolated verification:
- command:
  - targeted `pytest` for edit validation and freshness rules
- expected result:
  - bad edits are held explicitly and stale snapshots are visible

Monitored validation:
- live proof needed:
  - later, but only when an apply path is explicitly approved
- forced proof window:
  - if an apply step is added later, use the O-owned isolated apply proof for that ticket
- artifacts to poll:
  - none in this planning ticket
- poll cadence:
  - none
- success threshold:
  - browse and edit workflows are safe even before local apply ownership is final
- timeout rule:
  - park with the exact validation gap still open
- fallback if forced proof is blocked:
  - keep the system read-only plus inbox-only
- next automatic step after success:
  - propose the follow-up ticket for canonical local ownership or controlled apply
- notification mode:
  - milestone only
- user interruption threshold:
  - approval required before any write-to-truth path is built

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- The browse page is not complete if it still acts like an edit sheet.
- The edit path is not complete if it writes directly to Product_DB preview or Sheets.
- The full ticket is not complete until the user can browse, expand, and edit fixed truth without needing reorder as a workaround.
