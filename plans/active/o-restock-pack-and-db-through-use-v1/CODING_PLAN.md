# Coding Plan

Date: 2026-04-16
Scope: O restock pack-aware quantity model and Product_DB tie-in, starting with mock data only

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Lock planning, mock scenarios, and user walkthrough | `plans/active/o-restock-pack-and-db-through-use-v1/*` | docs review | no | completed |
| Phase 1 | Add a mock quantity-profile layer for fake SKUs | O flow files + new mock fixture files only | targeted O tests + new mock-data tests | no | completed |
| Phase 2 | Add a sample-only test orders page from operator submissions | O UI files and O UI tests only | targeted O UI tests | no | in progress |
| Phase 3 | Add pack-aware readiness and blocker reporting | O flow files, O readiness tests | targeted O tests | no | planned |
| Phase 4 | Small approved real-data onboarding pass | approved O files only | targeted O tests + artifact review | yes | planned |

## 2) Phase details

### Phase 0 - Planning lock
Goal:
- Define the task in plain English.
- Lock the mock-data-first approach.
- Give the user a slow, simple walkthrough before any real-data work begins.

Files allowed to change:
- `plans/active/o-restock-pack-and-db-through-use-v1/PROJECT_BRIEF.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/CODING_PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN_STATUS.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/RUNBOOK.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/EXECUTION_BATCH_001.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/MOCK_SKU_SCENARIOS.csv`

Implementation tasks:
- Write the brief and plan from repo evidence.
- Record the current O gaps.
- Define mock scenarios that cover the main quantity cases.

Isolated verification:
- command:
  - review the plan folder contents and confirm they match the ticket scope
- expected result:
  - one active plan folder exists with a brief, plan, coding plan, runbook, batch file, and mock scenarios

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - planning files complete
- timeout rule:
  - none
- next automatic step after success:
  - wait for user approval to start implementation batch 001
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

### Phase 1 - Mock quantity-profile layer
Goal:
- Create a simple local quantity-profile shape using fake SKUs only.
- Cover the three main buying shapes:
  - simple unit
  - supplier case multiple
  - repack or bundle

Files allowed to change:
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `tests/test_o001_restock_source_view.py`
- `tests/test_o_ui_operator_view.py`
- new mock fixture files under `tests/fixtures/o_phase_packs/`

Implementation tasks:
- Add structured pack-aware fields for the mock path.
- Keep real Product_DB untouched.
- Make the mock path readable and operator-facing.

Isolated verification:
- command:
  - targeted `pytest` for O source view and O UI quantity behavior
- expected result:
  - pack-aware mock scenarios render predictable row fields and quantity conversions

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - tests pass and mock outputs read clearly
- timeout rule:
  - stop and document exact failing scenario
- next automatic step after success:
  - Phase 2
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if quantity model becomes contradictory

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 2 - Sample-only test orders page
Goal:
- Show the operator what they just submitted, using sample orders only.
- Keep this separate from the live PO draft pipeline until the mock flow feels right.

Files allowed to change:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`

Implementation tasks:
- Add a `Test Orders` page or tab built from the rows submitted in the operator UI.
- Use only sample submissions from the operator page, not live O100 outputs.
- Make the page readable by supplier and easy to scan without code knowledge.

Isolated verification:
- command:
  - targeted `pytest` for O UI behavior
- expected result:
  - submitted sample rows appear in the test orders view with stable grouping and totals

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - operator can submit sample rows and immediately review them in a clean test orders page
- timeout rule:
  - record the exact missing test-order detail that stops the walkthrough
- next automatic step after success:
  - Phase 3
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if the sample-order page stops being simple

Phase status:
- code fix applied:
  - yes
- isolated verification passed:
  - yes
- monitored validation:
  - not needed

### Phase 3 - Pack-aware readiness and blocker reporting
Goal:
- Make missing pack truth visible instead of silently defaulting.
- Add health/checklist behavior for unresolved quantity truth.

Files allowed to change:
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/O004_build_restock_diagnostics.py`
- `tests/test_o020_reorder_input_coverage.py`
- `tests/test_o004_restock_diagnostics.py`

Implementation tasks:
- Add blocker reasons such as:
  - missing_quantity_mode
  - missing_sell_pack_qty
  - missing_supplier_case_qty
  - invalid_pack_conversion
- Add a small summary view that is understandable without code knowledge.

Isolated verification:
- command:
  - targeted `pytest` for O readiness/diagnostic outputs
- expected result:
  - bad or missing pack truth becomes explicit in coverage and diagnostics

Monitored validation:
- live proof needed:
  - no
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - mock rows produce explicit pack-related blocker reasons
- timeout rule:
  - park with the exact blocker still missing
- next automatic step after success:
  - wait for user approval for real-data onboarding
- notification mode:
  - milestone only
- user interruption threshold:
  - interrupt only if a design decision is needed

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

### Phase 4 - Small approved real-data onboarding pass
Goal:
- Apply the proven mock-data model to a very small real-SKU sample.
- Keep the boundary safe: no sheet writes and no canonical DB claim.

Files allowed to change:
- approved O files only
- optionally one read-only local mapping file if needed

Implementation tasks:
- Map 3-5 approved real SKUs.
- Verify where Product_DB has enough fields and where it does not.
- Record which fields must later move into a normalized supplier or product layer.

Isolated verification:
- command:
  - targeted `pytest` plus artifact review of selected real SKUs
- expected result:
  - small real sample maps cleanly or blocks explicitly for missing pack truth

Monitored validation:
- live proof needed:
  - yes, but bounded and approval-based
- artifacts to poll:
  - selected O output files for the approved real-SKU sample
- poll cadence:
  - first check at +5 minutes, second at +10 minutes, then every +15 minutes up to +60 minutes if runtime proof is requested
- success threshold:
  - selected real rows show correct quantity-mode behavior and explicit blockers where data is missing
- timeout rule:
  - parked pending next proof window with exact missing evidence recorded
- next automatic step after success:
  - propose the next ticket for real-data expansion or supplier normalization
- notification mode:
  - passive monitoring unless interruption threshold is met
- user interruption threshold:
  - user approval needed before any real-data phase begins

Phase status:
- code fix applied:
  - no
- isolated verification passed:
  - no
- monitored validation:
  - not started

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
