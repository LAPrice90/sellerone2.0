# Coding Plan

Date: `2026-04-20`
Scope: turn current B/E sales truth into the automatic actuals source for F learning, starting with a one-off foundation pass.
Execution mode: `one-off foundation before any loop promotion`

## 1) Non-negotiable rules
- No Google Sheets writes.
- No local DB rewrites.
- No ad-hoc A runs.
- Do not run overlapping B scripts.
- Do not hide stale truth with downstream smoothing.
- Do not treat provisional rows as finalized truth.
- Do not assume F `seller_sku` matches B/E `sku`.

## Current Addendum - 2026-04-22 token receipt and allocation recovery

### Current phase
- Phase A: recover missing token receipt intake for rows that exist in `Orders` or operator intake sources but are not yet represented in `Tokens` intake / `Token_Ledger`
- Phase B: rerun local token allocation and COGS chain and re-measure missing token coverage
- Phase C: if gaps remain after intake recovery, investigate token state drift separately from intake gaps

### Remaining gap split - 2026-04-22 remaining 18 missing-token rows
- Phase D: receipt-intake prevention
- Goal:
- stop future gaps where an eligible `Orders` row exists with receipt-ready quantity and `OrderKey`, but no token intake row is ever created.
- Scope:
- `scripts/tools/process_stock_receipts_sheet.py`
- targeted tests for receipt reconciliation if changed
- Proof target:
- explicit visibility or automatic staging for eligible `Orders` rows that are absent from `Tokens` intake, without treating blank `Delivered` or blank `Sent to FBA` as receipted stock.

- Phase E: token drift handling
- Goal:
- stop inventory-positive / token-zero drift when B stock events report positive sellable movement but token availability does not recover.
- Scope:
- `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`
- targeted tests for positive stock-event handling if changed
- Proof target:
- positive sellable stock events no longer disappear into repeated `insufficient_returned_pending` partials without an explicit recoverable action path.

- Phase F: shortage diagnostics
- Goal:
- ensure zero-available SKUs still appear in token shortage outputs and are not hidden from operator checks.
- Scope:
- `scripts/flows/B/B007_allocate_tokens_live.py`
- targeted tests for shortage reporting if changed
- Proof target:
- `token_shortages_by_sku.csv` includes SKUs with missing token demand even when no available token rows exist for that SKU.

### Files currently in scope
- `scripts/tools/process_stock_receipts_sheet.py`
- token intake guard or reconciliation code only if needed for earliest-stage recovery
- `scripts/flows/B/B007_allocate_tokens_live.py` only if runtime allocation behavior is genuinely wrong after intake is corrected
- `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py` only if positive stock-event drift is confirmed as a separate root cause
- `scripts/flows/B/B025_build_token_cogs_ledger.py` only if rebuild or proof support is needed
- `scripts/flows/B/B004_build_order_master.py` only if proof regeneration requires it
- this active plan folder

### Current proof targets
- missing-token rows for the newly logged 2026-04-13 receipt SKUs are cleared
- `orders_missing_tokens.csv` decreases only because upstream receipt/intake truth improved, not because rows were masked
- remaining missing-token rows are explicitly classified into:
- missing receipt intake
- true token shortage
- token state drift
- zero-available shortage SKUs are visible in diagnostics instead of silently omitted

### Current isolated proof sequence
- run guarded stock receipt intake:
  - `RECEIPTS_RUN=YES python scripts/tools/process_stock_receipts_sheet.py`
- rerun token allocation:
  - `python scripts/flows/B/B007_allocate_tokens_live.py`
- rebuild token COGS ledger:
  - `python scripts/flows/B/B025_build_token_cogs_ledger.py`
- rebuild local order master without sheet write:
  - `ORDER_MASTER_SKIP_SHEETS=1 ORDER_MASTER_L1_STABLE_SECONDS=0 python scripts/flows/B/B004_build_order_master.py`
- compare:
  - `out/orders_missing_tokens.csv`
  - `out/order_master.csv`
  - `out/token_cogs_ledger.csv`
  - `out/stock_receipt_summary.csv`

### Current live/runtime caution
- Do not run overlapping `B` owner processes.
- Keep `A` health verification as artifact-based unless the user explicitly asks for an `A` run.
- Treat token intake recovery and token state repair as separate root causes.
- Do not auto-promote historical `Orders` rows into receipt truth unless the eligibility rule is explicit and idempotent.

## Current Addendum - 2026-04-22 placeholder COGS fallback planning

### Planning intent
- allow missing-token sold orders to stay visible with a provisional placeholder COGS basis instead of blank COGS or dropped profit visibility
- keep the real root cause visible:
  - missing token creation
  - missing receipt intake
  - token shortage
  - token drift
- do not create fake tokens
- do not write placeholder COGS back into token truth

### Design rules
- order presence truth and token truth stay separate
- `order_master` may carry placeholder COGS for operator and downstream provisional reporting
- `token_cogs_ledger` must remain actual-token truth only
- any placeholder COGS row must stay explicitly marked as provisional and unresolved
- if there is no safe prior cost basis, keep COGS blank and log the miss rather than inventing a number

### Planned phase P1 - placeholder basis source
- Goal:
- define one safe fallback cost basis per `seller_sku` when token COGS are missing.
- Proposed fallback order:
- `1.` most recent actual token cost for the same `seller_sku`
- `2.` most recent receipted `Tokens` intake cost for the same `seller_sku`
- `3.` most recent delivered / sent purchase cost from `Orders` only if the receipt eligibility rule is already satisfied
- `4.` otherwise no placeholder is applied
- Required metadata on every placeholder row:
- `cogs_basis_type=placeholder_last_cost`
- `cogs_basis_source` with exact source table
- `cogs_basis_date`
- `cogs_truth_status=placeholder`
- `missing_token_flag=1`
- `missing_token_reason`

### Planned phase P2 - earliest-stage application
- Goal:
- apply placeholder COGS at the earliest safe sold-order stage without contaminating token truth.
- Primary implementation target:
- `scripts/flows/B/B004_build_order_master.py`
- Method:
- when a positive-qty row has no token COGS, keep the row in `order_master`
- attempt to fill `COGS_Total`, `COGS_VAT`, and `COGS_ExVAT` from the placeholder basis
- write explicit placeholder fields onto the row so downstream logic can distinguish:
- actual token COGS
- placeholder COGS
- still-missing COGS
- Non-goal:
- no placeholder rows written into `token_cogs_ledger.csv`

### Planned phase P3 - operator evidence and future UI feed
- Goal:
- turn missing-token cases into a clean operator-visible queue instead of a hidden accounting hole.
- Primary implementation targets:
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/flows/B/B007_allocate_tokens_live.py`
- Proposed output behavior:
- keep `out/orders_missing_tokens.csv` as the canonical unresolved queue
- enrich it with:
- `placeholder_applied_flag`
- `placeholder_cost_per_unit`
- `placeholder_total_cogs`
- `placeholder_basis_source`
- `placeholder_basis_date`
- `missing_token_reason_class`
- `receipt_state_class`
- `token_shortage_units`
- target one line per order row in the evidence file, and one line per SKU per run in `token_shortages_by_sku.csv`

### Planned phase P4 - downstream provisional handling
- Goal:
- let E and F use the placeholder profit signal without pretending it is finalized truth.
- Primary implementation targets:
- `scripts/flows/E/e_sales_truth_common.py`
- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- Expected behavior:
- rows using placeholder COGS remain `source_state=provisional_order_master`
- confidence should become explicit, for example:
- `provisional_cogs_placeholder`
- notes should carry:
- placeholder basis source
- placeholder basis date
- missing token reason class
- downstream packs may include these rows in units and revenue truth, and may include placeholder profit only when the confidence state remains explicit

### Planned phase P5 - health and guardrails
- Goal:
- stop placeholder COGS from becoming silent truth.
- Primary implementation targets:
- `scripts/flows/A/A015_build_system_health_check.py`
- targeted B and E flow tests
- Required health/reporting additions:
- count of placeholder COGS rows
- count of rows still missing any COGS basis
- count of SKUs with repeated placeholder use beyond threshold
- FAIL/WARN rule proposal:
- missing-token rows with no placeholder basis remain visible as current problem
- placeholder-backed rows are WARN, not PASS
- repeated or aging placeholder rows escalate by age bucket

### Files expected to be in scope when coding starts
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/flows/B/B007_allocate_tokens_live.py`
- `scripts/flows/B/B025_build_token_cogs_ledger.py` only if read-only basis lookup helpers are needed
- `scripts/flows/E/e_sales_truth_common.py`
- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- targeted tests for the above
- this active plan folder

### Coding sequence
- `1.` lock the placeholder basis rule and metadata columns
- `2.` implement placeholder application in `B004`
- `3.` enrich missing-token evidence outputs
- `4.` propagate placeholder confidence states through E
- `5.` add A015 health items and alert thresholds
- `6.` rerun the B/E proof chain and compare placeholder counts against unresolved true shortages

### Isolated proof target when coding starts
- a sold order with missing token COGS remains present in `order_master`
- placeholder COGS is applied only when a valid prior cost basis exists
- the row is still explicitly marked unresolved / provisional
- `orders_missing_tokens.csv` shows the row and the placeholder details
- `token_cogs_ledger.csv` still contains actual allocations only
- `sku_daily_sales_truth` carries the row with placeholder confidence, not finalized confidence
- health outputs show placeholder usage as an explicit warning class

### Runtime proof target when coding starts
- run a boundary-safe local B rebuild:
- `python scripts/flows/B/B007_allocate_tokens_live.py`
- `python scripts/flows/B/B025_build_token_cogs_ledger.py`
- `ORDER_MASTER_SKIP_SHEETS=1 ORDER_MASTER_L1_STABLE_SECONDS=0 python scripts/flows/B/B004_build_order_master.py`
- run the affected E builders:
- `python scripts/flows/E/E002_build_roi_snapshot.py`
- `python scripts/flows/E/E006_build_sales_truth_reconciliation.py`
- `python scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- compare:
- `out/order_master.csv`
- `out/orders_missing_tokens.csv`
- `out/token_cogs_ledger.csv`
- `out/sku_daily_sales_truth_latest.csv`
- existing health artifacts only unless the user explicitly asks for owned A proof

### Open design decision to hold during coding
- placeholder COGS must improve provisional profit visibility, but must never suppress:
- the missing-token queue
- the shortage queue
- the age / recurrence of unresolved placeholder rows

### Placeholder implementation snapshot - 2026-04-22T12:40:48Z
- code fix applied
- isolated verification passed
- live loop verification not yet proven

- implemented files:
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/flows/E/e_sales_truth_common.py`
- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `tests/test_b004_level_gate.py`
- `tests/test_e007_build_sku_daily_sales_truth.py`

- key implementation outcomes:
- `B004` now applies per-SKU placeholder COGS on rows that are still missing token allocation keys.
- placeholder basis priority now uses:
- `token_cogs_ledger_last_actual`
- `stock_receipts_latest`
- `orders_sheet_receipted`
- `order_master` now carries explicit metadata:
- `COGS_Placeholder_Applied`
- `COGS_Basis_Type`
- `COGS_Basis_Source`
- `COGS_Basis_Date`
- `Missing_Token_Flag`
- `Missing_Token_Reason`
- `orders_missing_tokens.csv` is now enriched with:
- `placeholder_applied_flag`
- `placeholder_cost_per_unit`
- `placeholder_total_cogs`
- `placeholder_basis_source`
- `placeholder_basis_date`
- `missing_token_reason_class`
- `receipt_state_class`
- `token_shortage_units`
- E truth logic now recognizes placeholder-backed provisional rows and supports:
- `provisional_cogs_placeholder`
- `provisional_fx_and_cogs_placeholder`
- notes now carry placeholder units/source/date plus missing-token context.

- isolated verification:
- `python -m py_compile scripts/flows/B/B004_build_order_master.py scripts/flows/E/e_sales_truth_common.py scripts/flows/E/E007_build_sku_daily_sales_truth.py tests/test_b004_level_gate.py tests/test_e007_build_sku_daily_sales_truth.py` -> pass
- `PYTHONPATH=. pytest tests/test_b004_level_gate.py tests/test_e007_build_sku_daily_sales_truth.py -q` -> pass (`12`)
- `PYTHONPATH=. pytest tests/test_e002_build_roi_snapshot.py tests/test_e006_build_sales_truth_reconciliation.py -q` -> pass (`8`)

- local runtime proof chain:
- `python scripts/flows/B/B007_allocate_tokens_live.py`
- `python scripts/flows/B/B025_build_token_cogs_ledger.py`
- `ORDER_MASTER_SKIP_SHEETS=1 ORDER_MASTER_L1_STABLE_SECONDS=0 python scripts/flows/B/B004_build_order_master.py`
- `python scripts/flows/E/E002_build_roi_snapshot.py`
- `python scripts/flows/E/E006_build_sales_truth_reconciliation.py`
- `python scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `python scripts/one_off/BEF000_build_sales_truth_foundation.py`
- `python scripts/one_off/BEF001_build_operational_feedback_seed.py`
- `python scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `python scripts/one_off/F013_build_live_test_readiness_pack.py`
- `python scripts/one_off/F016_build_stocked_sku_vetting_report.py`
- `python scripts/one_off/BEF007_build_sellerboard_window_alignment_audit.py`

- post-fix evidence:
- `order_master` rows: `9783`
- `order_master` rows with `COGS_Placeholder_Applied=1`: `8`
- `orders_missing_tokens.csv` rows: `8`
- rows with placeholder in missing-token queue: `8/8`
- unresolved SKUs after placeholder: `0R-GRRH-W0Z9`, `Q1-00D7-5IQF`, `R4-0AXZ-ZZ9D`, `SE-UITZ-7CPY`
- `token_shortages_by_sku.csv` still present and non-empty (`5` SKU rows; `missing_qty_total=10`)
- focus SKU `2X-8XI7-C9T5` (`B07L6H9GZ2`) remains not missing-token (`0` rows in `orders_missing_tokens.csv`)
- fixed-window alignment audit refreshed:
- `focus_units=20.0`
- `focus_class=units_aligned_value_basis_gap`

- note on provisional placeholder confidence in latest daily file:
- latest `sku_daily_sales_truth` currently shows `0` rows with placeholder confidence status.
- this is expected in the current 30-day snapshot because those placeholder-flagged orders are not the active provisional source rows in the E window (finalized precedence and window composition).

### Placeholder health-gate addendum - 2026-04-22T12:58:21Z
- code fix applied
- isolated verification passed
- live loop verification confirmed for B-owned finalize evidence

- additional files changed:
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_a015_health_check_runtime.py`

- health-gate behavior added:
- `order_master_placeholder_cogs_rows`
- status is `warn` when placeholder-backed rows exist, with repeat-SKU context in notes
- `order_master_missing_token_no_placeholder_rows`
- status is `fail` when a missing-token row exists without placeholder basis
- detail artifacts:
- `out/health_order_master_placeholder_cogs.csv`
- `out/health_order_master_missing_token_no_placeholder.csv`

- isolated verification:
- `python -m py_compile scripts/flows/A/A015_build_system_health_check.py tests/test_a015_health_check_runtime.py` -> pass
- `PYTHONPATH=. pytest tests/test_a015_health_check_runtime.py -q -k "order_master_placeholder_stats or order_master_l1_coverage_stats_does_not_ignore_sidecar_missing_keys"` -> pass (`3`)

- runtime proof:
- `python scripts/flows/A/A015_build_system_health_check.py --profile b --no-toast`
- output snapshot: `out/cycle_alerts/checklist_B_split.csv`
- observed checks:
- `order_master_placeholder_cogs_rows = warn / 8`
- `order_master_missing_token_no_placeholder_rows = ok / 0`
- `l1_keys_missing_in_master = ok / 0` with `observed_missing_token_keys=8`

- B-owned finalize evidence after patch:
- `out/systems/B/live/B_cycle.log`
- latest marker:
- `2026-04-22T12:58:06Z ... B_FINALIZE ran rc=0 wrote_health=true reason=cycle_complete`

- residual known blocker remains separate:
- `token_shortages_by_sku = fail / 5`

## 2) Phase summary

| Phase | Goal | Main proof target | Status |
|---|---|---|---|
| Phase 0 | build freshness and bridge foundation | explicit stale/trust fields and operational replay seed | complete |
| Phase 1 | auto-build F actuals from B/E truth | `f_sales_history_learning_actuals_latest.csv` filled automatically | complete |
| Phase 2 | build operator example pack | explainable example rows with outcome classes | complete |
| Phase 3 | guarded automation path | scheduled one-off ownership plus health gates | complete (ready_with_warnings) |
| Phase 4 | B-owned ledger refresh alignment | `order_ledger_fx` refreshes in-cycle before guarded rerun | complete |
| Phase 5 | overlap recovery through operational replay | nonzero replay-mapped rows for current no-overlap F universe | complete (ready_with_warnings) |
| Phase 6 | operational-truth review lane | nonzero review/example rows with operational truth coverage | complete (ready_with_warnings) |
| Phase 7 | operational expected-baseline enrichment | non-pending outcomes for operational-truth rows where expected baseline exists | complete (ready_with_warnings) |
| Phase 8 | native overlap expansion via alignment map | nonzero native overlap rows (non-replay) with explicit basis | complete (ready_with_warnings) |
| Phase 9 | direct identity bridge overlap | nonzero direct summary-native overlap with strict supplier+ASIN identity mapping | implemented (parked pending identity resolution feed expansion) |
| Phase 10 | sold-product truth-first accuracy pack | measure estimator accuracy on products we actually sold before trusting price-list ordering | complete (ready_with_warnings; parked pending sold-truth replay coverage expansion) |
| Phase 11 | sold-truth replay capture queue and guard wiring | convert missing sold-model evidence into explicit automated capture action | complete (ready_with_warnings; parked pending sold-truth replay capture execution) |
| Phase 12 | execute sold-truth replay capture path | clear sold-truth replay queue through live capture and rebuild chain, then re-score | complete (ready_with_warnings) |
| Phase 13 | execute scope-expansion capture window | run guarded scope-expansion capture path and measure alignment/no-source improvement | complete (ready_with_warnings) |
| Phase 14 | direct-bridge feasibility guard correction | stop routing to scope capture when direct bridge is structurally infeasible | complete (ready_with_warnings) |
| Phase 15 gate | commercial readiness data sufficiency and 15-SKU validation panel | explicit sufficiency pass/fail by data family plus fixed review panel for obvious pass, obvious fail, and edge cases | complete (ready_with_warnings) |
| Phase 16 | sold-universe decision replay and commercial bridge | recover sold-row decision coverage and commercial guidance fields so sold truth can drive banded scoring | complete (ready_with_warnings) |
| Phase 17 | commercial decision bands and live-test readiness | judge worth-testing, starter qty, and negative-mode risk without forcing exact prediction | complete (ready_with_warnings; sold rank-window source recovered via full-capture evidence) |

## 3) Phase 0 - truth freshness and bridge foundation

### Goal
- create the first trustworthy foundation for self-feeding learning

### Files allowed to change
- `scripts/one_off/BEF000_build_sales_truth_foundation.py`
- `scripts/one_off/BEF001_build_operational_feedback_seed.py`
- `tests/test_bef000_build_sales_truth_foundation.py`
- `tests/test_bef001_build_operational_feedback_seed.py`
- this active plan folder

### Implementation tasks
- emit a foundation CSV with:
  - operational SKU
  - operational ASIN when available
  - latest finalized date
  - latest provisional date
  - `order_master` freshness timestamp
  - `order_ledger_fx` freshness timestamp
  - lag minutes
  - trust state
- emit an operational replay seed with:
  - ASIN
  - operational SKU
  - recent sales presence
  - bridge status
  - ambiguity flag
- emit a health CSV with:
  - stale lag checks
  - bridge coverage checks
  - unresolved counts

### Isolated verification
- `python -m py_compile scripts/one_off/BEF000_build_sales_truth_foundation.py scripts/one_off/BEF001_build_operational_feedback_seed.py tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py`
- `pytest tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py -q`
- one-off builder runs:
  - `python scripts/one_off/BEF000_build_sales_truth_foundation.py`
  - `python scripts/one_off/BEF001_build_operational_feedback_seed.py`

### Pass checks
- foundation output exists
- health output exists
- operational replay seed exists
- stale lag fields are populated
- unresolved and ambiguous bridge counts are explicit
- no file outside allowed scope is changed

### Sign-off language
- `code fix applied`
- `isolated verification passed`
- `live loop verification not applicable yet`

### Automatic next step
- start Phase 1

### Phase 0 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/BEF000_build_sales_truth_foundation.py scripts/one_off/BEF001_build_operational_feedback_seed.py tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py` -> pass
- tests:
  - `pytest tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py -q` -> pass (`4`)
- one-off runs:
  - `python scripts/one_off/BEF000_build_sales_truth_foundation.py` -> pass
  - `python scripts/one_off/BEF001_build_operational_feedback_seed.py` -> pass
- output counts:
  - `out/analysis_reports/bef_sales_truth_foundation_latest.csv` -> `161`
  - `out/analysis_reports/bef_sales_feedback_health_latest.csv` -> `11`
  - `out/analysis_reports/bef_operational_feedback_seed_latest.csv` -> `161`
- key truth:
  - freshness status is `fail` due ledger lag:
    - `order_master_to_ledger_lag_minutes=838.53`
  - bridge counts:
    - `resolved=95`
    - `ambiguous=0`
    - `unresolved=66`

## 4) Phase 1 - automatic actuals for F learning

### Goal
- replace the manual actuals path with an automated builder

### Files allowed to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- this active plan folder

### Implementation tasks
- build automatic 30d, 60d, and 90d actuals from the foundation layer
- keep finalized and provisional basis explicit
- let `F012` read automated actuals by default for normal learning use

### Isolated verification
- targeted compile
- targeted pytest
- one-off actuals build
- one-off `F012` rebuild

### Pass checks
- nonzero automatic actual rows for bridged operational items
- manual template no longer required for normal run path
- pending rows stay explicit when windows are not mature

### Phase 1 proof snapshot
- code edits:
  - `scripts/one_off/BEF002_build_sales_feedback_actuals.py` added
  - `tests/test_bef002_build_sales_feedback_actuals.py` added
- compile:
  - `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_f012_build_sales_history_learning_pack.py` -> pass
- tests:
  - `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_f012_build_sales_history_learning_pack.py -q` -> pass (`5`)
- one-off runs:
  - `python scripts/one_off/BEF002_build_sales_feedback_actuals.py` -> pass
  - `python scripts/one_off/F012_build_sales_history_learning_pack.py` -> pass
- output counts:
  - `f_sales_history_learning_actuals_latest.csv` -> `58`
  - `f_sales_history_learning_review_latest.csv` -> `266`
  - `f_sales_history_learning_health_latest.csv` -> `14`
- key runtime truth:
  - automated actuals file is produced and refreshed
  - live summary overlap remains zero:
    - `summary_rows_total=2358`
    - `summary_rows_matched=0`
    - `operational_baseline_rows=58`

## 5) Phase 2 - operator example pack

### Goal
- reduce the user role to checking logic examples

### Files allowed to change
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- this active plan folder

### Implementation tasks
- group learning rows into clear example classes
- emit a review pack with plain-English prompts

### Isolated verification
- targeted compile
- targeted pytest
- one-off example build

### Pass checks
- example pack exists
- each example has:
  - expected result
  - actual result
  - outcome class
  - supporting notes

### Phase 2 proof snapshot
- code edits:
  - `scripts/one_off/BEF003_build_sales_feedback_examples.py` updated
  - `tests/test_bef003_build_sales_feedback_examples.py` added
- compile:
  - `python -m py_compile scripts/one_off/BEF003_build_sales_feedback_examples.py tests/test_bef003_build_sales_feedback_examples.py` -> pass
- tests:
  - `pytest tests/test_bef003_build_sales_feedback_examples.py -q` -> pass (`2`)
- one-off run:
  - `python scripts/one_off/BEF003_build_sales_feedback_examples.py` -> pass
- output counts:
  - `bef_sales_feedback_examples_latest.csv` -> `266`
  - `example_class::no_operational_truth_coverage=266`
- key runtime truth:
  - overlap-aware example logic is active and emits explainable rows
  - current sample is fully coverage-gap limited, not model-outcome limited

## 6) Phase 3 - guarded automation

### Goal
- move from manual one-off execution to safe scheduled automation

### Files allowed to change
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `scripts/one_off/BEF000_build_sales_truth_foundation.py`
- `tests/test_bef000_build_sales_truth_foundation.py`
- this active plan folder

### Preconditions
- foundation is stable
- automatic actuals are stable
- example pack is stable
- health checks exist

### Pass checks
- scheduled path is documented
- stale truth is blocked or surfaced cleanly
- user no longer needs to populate actual sales by hand

### Phase 3 proof snapshot
- code edits:
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` added
  - `tests/test_bef004_run_sales_feedback_guarded_once.py` added
  - `scripts/one_off/BEF000_build_sales_truth_foundation.py` updated (ledger timestamp source fix)
  - `tests/test_bef000_build_sales_truth_foundation.py` updated
- compile:
  - `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`3`)
  - `pytest tests/test_bef000_build_sales_truth_foundation.py -q` -> pass (`3`)
- one-off run:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` -> pass (guard report emitted)
- output evidence:
  - `bef_sales_feedback_guarded_run_latest.json` exists and includes:
    - `guard_status=blocked`
    - `hard_block_reasons=["freshness_fail_active"]`
    - `next_action=refresh_ledger_then_rerun_guarded_once`
    - `freshness_lag_minutes=873.93` (post-fix)
- key runtime truth:
  - deterministic guarded decision path now exists
  - B resumed full cycle finalization after maintenance-marker cleanup
  - schedule promotion is intentionally blocked until freshness root cause is cleared

### Phase 3 live verification status
- `Verification status: Confirmed`
- `Changed at: 2026-04-20T16:38:31Z`
- `Latest health snapshot at: 2026-04-20T16:38:31Z`
- `Verifier: completed B finalized cycle at 2026-04-20T16:37:16Z plus guarded rerun at 2026-04-20T16:38:31Z`
- guarded result:
  - `guard_status=ready`
  - `freshness_lag_minutes=0.00`
  - warnings remain overlap-related only

## 7) Phase 4 - B-owned ledger refresh alignment

### Goal
- remove the upstream freshness hole by rebuilding `order_ledger_fx.csv` inside the B cycle path before BEF guarded reruns.

### Files allowed to change
- `scripts/cycles/run_B_cycle.py`
- `tests/test_flow_health_gate.py`
- this active plan folder

### Implementation tasks
- add `B006_build_fx_ledgers.py` to B `RUN_ORDER` after `B004_build_order_master.py`.
- add B006 timeout and artifacts mapping to B cycle metadata.
- in quiet publish mode, rerun B006 immediately after the second B004 publish step and before D001 publish so P&L and BEF read the same-cycle ledger.
- keep no-overlap ownership behavior unchanged.

### Isolated verification
- `python -m py_compile scripts/cycles/run_B_cycle.py tests/test_flow_health_gate.py`
- `pytest tests/test_flow_health_gate.py tests/test_b_cycle_signal_policy.py tests/test_b_split_health_modes.py -q`

### Live monitoring target
- `out/B_cycle.log`
- `out/order_master.csv`
- `out/order_ledger_fx.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- `+5 minutes`
- `+10 minutes`
- then every `+15 minutes` until `+60 minutes`

### Success threshold
- at least one new `B_FINALIZE ... reason=cycle_complete` after patch start
- `order_ledger_fx max Date` advances in a post-patch finalized cycle window
- rerun of `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` is not blocked by `freshness_fail_active`

### Timeout rule
- if `+60 minutes` expires without ledger movement:
  - classify status as `parked pending next proof window`
  - capture exact missing threshold and next required ownership-safe window

### Automatic next step
- if threshold is met:
  - rerun BEF guarded once and refresh `PLAN_STATUS.md`

### Phase 4 proof snapshot
- compile:
  - `python -m py_compile scripts/cycles/run_B_cycle.py tests/test_flow_health_gate.py` -> pass
- tests:
  - `pytest tests/test_flow_health_gate.py tests/test_b_cycle_signal_policy.py tests/test_b_split_health_modes.py -q` -> pass (`13`)
- runtime activation:
  - B worker restart on patched code:
    - `B_cycle.lock pid 9456 -> 25448`
- live cycle evidence:
  - `run B006_build_fx_ledgers.py` -> `ok`
  - `publish Order_Ledger_FX`
  - second `run B006_build_fx_ledgers.py` -> `ok`
  - `B_FINALIZE ran rc=0 wrote_health=true reason=cycle_complete` at `2026-04-20T16:37:16Z`
- freshness alignment:
  - `order_master max Date = 2026-04-20T16:07:29Z`
  - `order_ledger_fx max Date = 2026-04-20T16:07:29Z`
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` -> pass
  - `guard_status=ready`
  - `freshness_fail_count=0`
  - `freshness_lag_minutes=0.00`

## 8) Phase 5 - overlap recovery through operational replay

### Goal
- recover learning continuity when direct F-summary ASIN overlap is zero, without pretending native overlap exists.

### Files allowed to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- add seed replay source in BEF002 from `bef_operational_feedback_seed_latest.csv`.
- emit replay rows with explicit basis token (`operational_seed_replay`) so they are not mislabeled as native summary overlap.
- update BEF004 warning logic:
  - keep warning when both native summary overlap and seed replay are zero.
  - treat seed replay presence as recovered overlap path.
- keep all coverage signals explicit in metrics and guard output.

### Isolated verification
- `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `actuals_basis=operational_seed_replay` rows are present when native summary overlap is zero.
- guard remains `ready`.
- overlap warning is no longer the hard next action blocker.

### Timeout rule
- if replay rows remain zero with native overlap zero:
  - keep status as `parked pending overlap source expansion`
  - preserve explicit no-overlap truth in guard warnings.

### Automatic next step
- rerun `BEF004` and refresh plan status with recovered overlap-path metrics.

### Phase 5 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`7`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-20T16:59:02Z` -> pass
  - metrics unchanged from immediate post-run check
- output truth:
  - `summary_rows_matched=0` (native summary overlap still zero)
  - `seed_replay_rows_matched=57`
  - `actuals_rows_total=115`
  - `actuals_basis_counts={"operational_baseline":58,"operational_seed_replay":57}`
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `warnings` now:
    - `summary_asin_overlap_recovered_by_seed_replay`
    - `all_review_rows_pending_outcome`
    - `all_examples_no_operational_truth_coverage`
  - `next_action=monitor_seed_replay_and_expand_true_overlap`

## 9) Phase 6 - operational-truth review lane

### Goal
- stop treating the full review pack as no-truth coverage when operational truth exists but summary identity overlap is zero.
- add an explicit operational-truth lane in learning review outputs without claiming native summary overlap.

### Files allowed to change
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- in `F012`, append operational-truth review rows from `actuals_basis=operational_baseline` when they are not present in summary snapshot keys.
- preserve explicit identity truth:
  - no fake `summary_asin_map` labels
  - no fake expected units/profit for operational-only rows
- keep pending outcome explicit when expected units are missing even if actuals exist.
- ensure example classification moves operational-truth rows into overlap-gap class instead of no-coverage class.

### Isolated verification
- `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_learning_review_latest.csv`
- `out/analysis_reports/bef_sales_feedback_examples_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `review_rows_total` increases with operational-truth rows while native summary overlap remains explicit.
- `example_class::overlap_gap_no_summary_match` is nonzero.
- `all_examples_no_operational_truth_coverage` warning is removed.
- `guard_status` stays `ready`.

### Timeout rule
- if operational-truth review rows remain zero:
  - keep status as `parked pending F012 coverage fix`
  - retain explicit warnings without masking.

### Automatic next step
- rerun guarded one-off and refresh `PLAN_STATUS.md` / batch evidence with Phase 6 metrics.

### Phase 6 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`10`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-20T20:43:46Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-20T20:49:22Z` -> pass
  - metrics unchanged from immediate post-run check
- output truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `review_rows_total=324` (`+58` operational-truth-only rows)
  - `review_pending_outcome_rows=324`
  - `rows_operational_truth_only=58`
  - `example_class_counts={"no_operational_truth_coverage":266,"overlap_gap_no_summary_match":58}`
  - warning removed:
    - `all_examples_no_operational_truth_coverage`
  - warnings remaining:
    - `summary_asin_overlap_recovered_by_seed_replay`
    - `all_review_rows_pending_outcome`
  - `next_action=monitor_seed_replay_and_expand_true_overlap`

## 10) Phase 7 - operational expected-baseline enrichment

### Goal
- reduce `all_review_rows_pending_outcome` by supplying expected baseline values for operational-truth rows where a trusted expected source already exists.
- keep identity truth explicit (still no fake summary overlap).

### Files allowed to change
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- read `out/analysis_reports/hf_learning_alignment_30d_latest.csv` as optional expected-baseline source.
- map expected units/profit by operational ASIN for operational-truth-only review rows.
- preserve pending outcome when expected baseline is still missing.
- keep all metrics and warnings truthful.

### Isolated verification
- `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_learning_review_latest.csv`
- `out/analysis_reports/f_sales_history_learning_health_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- operational-truth rows with expected baselines produce non-pending outcomes.
- `review_pending_outcome_rows` drops below `review_rows_total`.
- guard remains `ready`.

### Timeout rule
- if no non-pending rows are produced:
  - keep status as `parked pending broader expected-baseline source`
  - keep warning state explicit without masking.

### Automatic next step
- rerun guarded one-off, then refresh `PLAN_STATUS.md` and batch evidence with Phase 7 metrics.

### Phase 7 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`10`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T08:49:02Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T08:54:23Z` -> pass
  - metrics unchanged from immediate post-run check
- output truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `review_rows_total=323`
  - `review_pending_outcome_rows=304`
  - `rows_with_outcome=19`
  - `rows_operational_truth_only=57`
  - `rows_operational_truth_with_expected=19`
  - `example_class_counts={"no_operational_truth_coverage":266,"overlap_gap_no_summary_match":38,"model_error_demand_too_high":19}`
  - warning removed:
    - `all_review_rows_pending_outcome`
  - warnings remaining:
    - `summary_asin_overlap_recovered_by_seed_replay`
  - `next_action=monitor_seed_replay_and_expand_true_overlap`

## 11) Phase 8 - native overlap expansion via alignment map

### Goal
- increase non-replay overlap rows above zero without pretending live summary ASIN overlap exists.
- keep overlap-source truth explicit so operators can separate:
  - live summary overlap
  - alignment-map overlap
  - seed replay overlap

### Files allowed to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- add optional alignment-native row source in `BEF002` from:
  - `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
- emit explicit basis:
  - `actuals_basis=alignment_asin_map`
  - `purchased_flag=auto_alignment_asin_match`
- update `BEF004` metrics and warnings to track:
  - `actuals_alignment_map_rows`
  - `actuals_native_overlap_rows` (summary + alignment)
- keep warning text explicit when summary overlap is still zero but native overlap is recovered by alignment.

### Isolated verification
- `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `actuals_alignment_map_rows > 0`
- `actuals_native_overlap_rows > 0`
- `guard_status` remains `ready`
- overlap warning becomes explicit alignment-recovery state, not zero-overlap state

### Timeout rule
- if alignment rows stay zero:
  - keep status as `parked pending broader alignment feed`
  - preserve explicit overlap warning state.

### Automatic next step
- rerun guarded one-off and refresh `PLAN_STATUS.md` and batch evidence with Phase 8 metrics.

### Phase 8 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`9`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:01:45Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:07:06Z` -> pass
  - metrics unchanged from immediate post-run check
- output truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `actuals_summary_asin_rows=0`
  - `actuals_alignment_map_rows=19`
  - `actuals_native_overlap_rows=19`
  - `actuals_seed_replay_rows=38`
  - `actuals_recovered_overlap_rows=57`
  - warnings now:
    - `summary_asin_overlap_recovered_by_alignment_map`
  - warnings removed:
    - `summary_asin_overlap_recovered_by_seed_replay`
  - `next_action=monitor_alignment_map_and_expand_true_overlap`

## 12) Phase 9 - direct identity bridge overlap

### Goal
- promote overlap from fallback-only recovery to direct native linkage between F decision rows and operational truth rows.
- keep strict identity matching so direct overlap is trustworthy and auditable.

### Files allowed to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- in `BEF002`, add strict direct bridge consumption from:
  - `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
- direct bridge match keys must be:
  - `feeder_backtest_summary_live.seller_sku -> identity_bridge.supplier_sku`
  - `feeder_backtest_summary_live.asin -> identity_bridge.asin`
- emit direct basis explicitly:
  - `actuals_basis=summary_direct_bridge`
- preserve fallback continuity:
  - `alignment_asin_map`
  - `operational_seed_replay`
- in `BEF004`, add explicit direct overlap metrics and warning clarity.

### Isolated verification
- `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `actuals_summary_direct_bridge_rows > 0`
- `actuals_native_overlap_rows` remains nonzero
- `guard_status=ready`
- no freshness regression

### Timeout rule
- if direct bridge overlap remains zero:
  - keep status as `parked pending identity resolution feed expansion`
  - preserve fallback overlap metrics and explicit warning state.

### Automatic next step
- execute `EXECUTION_BATCH_006` implementation and write proof snapshot into plan artifacts.

### Phase 9 proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`10`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:35:46Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:41:06Z` -> pass
  - metrics unchanged from immediate post-run check
- output truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `actuals_summary_direct_bridge_rows=0`
  - `actuals_summary_asin_rows=0`
  - `actuals_alignment_map_rows=19`
  - `actuals_native_overlap_rows=19`
  - `actuals_seed_replay_rows=38`
  - `actuals_recovered_overlap_rows=57`
  - warnings now:
    - `summary_asin_overlap_recovered_by_alignment_map`
    - `summary_direct_bridge_overlap_zero`
  - phase threshold status:
    - `not yet proven` (`actuals_summary_direct_bridge_rows > 0` still unmet)

### Phase 9 follow-through - automated scope expansion trigger
- goal:
  - convert direct-bridge stall into an automated actionable feed, not a manual investigation loop.
- code updates:
  - `BEF004` now builds and reports:
    - `hf_scope_expansion_candidates_latest.csv`
    - `hf_scope_expansion_summary_latest.csv`
  - guarded warnings now include:
    - `scope_expansion_candidates_ready` when direct bridge remains zero and outside-H-scope candidates exist.
  - guarded next action now upgrades to:
    - `run_scope_expansion_capture_path`
- isolated verification:
  - `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
  - `pytest tests/test_bef004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py -q` -> pass (`12`)
- live verification:
  - guarded rerun at `2026-04-21T10:27:18Z` -> pass
  - monitored follow-up rerun at `2026-04-21T10:32:32Z` -> pass
  - runtime truth:
    - `guard_status=ready`
    - `actuals_summary_direct_bridge_rows=0`
    - `scope_expansion_candidate_rows=52362`
    - `scope_expansion_outside_h_scope_rows=6979`
    - `scope_expansion_no_asin_rows=35831`
    - `scope_expansion_stale_source_rows=9552`
    - warnings now:
      - `summary_asin_overlap_recovered_by_alignment_map`
      - `summary_direct_bridge_overlap_zero`
    - `scope_expansion_candidates_ready`
    - `next_action=run_scope_expansion_capture_path`

## 13) Phase 10 - sold-product truth-first accuracy pack

### Goal
- stop using unsold scanned products as the primary proof of estimator quality.
- make sold-product truth the main dataset for judging whether the model is safe enough to drive ordering decisions.

### Files allowed to change
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- rebuild `F011` so the normal accuracy path is driven by products we actually sold.
- source actual units and profit from B/E truth outputs, not manual operator entry.
- keep model-side estimate coverage explicit:
  - expected units
  - expected profit
  - decision state
  - decision confidence
- emit a business-readable accuracy summary with:
  - false pass rows
  - false fail rows
  - demand overestimate rows
  - demand underestimate rows
  - profit overestimate rows
  - profit underestimate rows
- keep unsold scan evidence as supporting context only, not the main pass/fail proof.

### Isolated verification
- `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
- `out/analysis_reports/bef_sales_feedback_examples_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- sold-product accuracy rows are nonzero.
- judged rows with enough model-side evidence are nonzero.
- false pass and false fail counts are explicit.
- no manual actual-sales entry is needed for the normal path.

### Timeout rule
- if sold-product truth rows exist but model-side replay coverage is still thin:
  - keep status as `parked pending sold-truth replay coverage expansion`
  - retain sold-product truth as the main accuracy artifact
  - do not fall back to unsold scan volume as the primary proof.

### Automatic next step
- execute `EXECUTION_BATCH_007` and write proof snapshot into plan artifacts.

### Phase 10 proof snapshot
- code edits:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py` rebuilt to sold-truth-first flow using:
    - `f_sales_history_learning_actuals_latest.csv` as primary sold-truth input
    - `feeder_backtest_summary_live.csv` and `hf_learning_alignment_30d_latest.csv` as model-side evidence sources
  - `tests/test_f011_build_sales_history_accuracy_pack.py` rewritten for:
    - missing model-side evidence
    - false pass detection
    - summary plus alignment estimate fill
- compile:
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/F012_build_sales_history_learning_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_f012_build_sales_history_learning_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`18`)
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` at `2026-04-21T12:24:43Z` -> pass
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T12:24:51Z` -> pass (`guard_status=ready`, `readiness_label=ready_with_warnings`)
- sold-truth accuracy truth:
  - `sold_rows_total=57`
  - `sold_rows_with_model_side_evidence=19`
  - `sold_rows_missing_model_side_evidence=38`
  - `judged_accuracy_rows=19`
  - `false_pass_rows=0`
  - `false_fail_rows=0`
  - `demand_overestimate_rows=13`
  - `demand_underestimate_rows=3`
  - `profit_overestimate_rows=1`
  - `profit_underestimate_rows=16`
  - top buckets:
    - `missing_model_decision:57`
    - `missing_model_estimate:38`
    - `missing_model_side_evidence:38`
    - `profit_underestimate:16`
    - `profit_underestimate_severe:15`
- phase threshold status:
  - success threshold met for sold-truth-first reporting and explicit error metrics
  - parked per timeout rule due thin model-side coverage on sold rows (`38/57` missing model-side evidence)

## 14) Phase 11 - sold-truth replay capture queue and guard wiring

### Goal
- treat missing sold-row model evidence as an upstream capture task, not a downstream reporting patch.
- make guarded outputs surface this as the primary next action when present.

### Files allowed to change
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- emit `f_sold_truth_replay_capture_queue_latest.csv` from `F011` for sold ASINs missing model-side evidence.
- include queue count in `f_sales_history_accuracy_summary_latest.csv`.
- add guard metrics and warning in `BEF004`:
  - `sold_truth_replay_queue_rows`
  - warning: `sold_truth_replay_capture_required`
  - next action: `run_sold_truth_replay_capture_path` when queue rows > 0.

### Isolated verification
- `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
- `out/analysis_reports/f_sold_truth_replay_capture_queue_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- queue file exists with explicit rows for sold ASINs missing model evidence.
- guard warning and next action move to sold-truth capture when queue is nonzero.
- no freshness or overlap regression.

### Timeout rule
- if queue remains nonzero after one capture window:
  - keep status as `parked pending sold-truth replay capture execution`
  - do not collapse back into decision-quality claims.

### Automatic next step
- execute capture path for queued sold ASINs, then rerun `F011` and `BEF004` to re-score coverage.

### Phase 11 proof snapshot
- code edits:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
    - writes `f_sold_truth_replay_capture_queue_latest.csv`
    - writes summary metric `sold_truth_replay_queue_rows`
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
    - reads sold-truth replay queue
    - emits metric `sold_truth_replay_queue_rows`
    - emits warning `sold_truth_replay_capture_required`
    - routes `next_action=run_sold_truth_replay_capture_path`
  - tests:
    - `tests/test_f011_build_sales_history_accuracy_pack.py`
    - `tests/test_bef004_run_sales_feedback_guarded_once.py`
- compile:
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`11`)
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` at `2026-04-21T12:43:24Z` -> pass
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T12:43:30Z` -> pass
- output truth:
  - `sold_rows_total=57`
  - `sold_rows_missing_model_side_evidence=38`
  - `sold_truth_replay_queue_rows=38`
  - `guard_status=ready`
  - `warnings` include:
    - `sold_truth_replay_capture_required`
  - `next_action=run_sold_truth_replay_capture_path`
- phase status:
  - queue and guard routing implemented and proven
  - parked pending execution of sold-truth capture path

## 15) Phase 12 - sold-truth replay capture execution

### Goal
- execute the queued sold-truth capture action end-to-end.
- prove the sold-truth replay queue clears and sold-row model-side evidence updates.

### Files allowed to change
- `scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py`
- `tests/test_bef005_run_sold_truth_replay_capture_path.py`
- this active plan folder

### Implementation tasks
- add a concrete runner for `run_sold_truth_replay_capture_path`.
- read `f_sold_truth_replay_capture_queue_latest.csv` and build a deduped capture pack.
- run live BBP capture for queued ASINs.
- rebuild post-capture chain:
  - `F009` consistency facts
  - `HF001` baseline
  - `HF002` alignment
  - `HF003` health
  - `HF005` operator report
- rerun:
  - `F011` sold-truth accuracy pack
  - `BEF004` guarded decision

### Isolated verification
- `python -m py_compile scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py tests/test_bef005_run_sold_truth_replay_capture_path.py`
- `pytest tests/test_bef005_run_sold_truth_replay_capture_path.py -q`

### Live monitoring target
- `out/analysis_reports/bef_sold_truth_replay_capture_latest.json`
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
- `out/analysis_reports/f_sold_truth_replay_capture_queue_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- queue is reduced from pre-run nonzero to post-run `0`.
- sold rows with model-side evidence equals sold rows total.
- guard no longer warns `sold_truth_replay_capture_required`.

### Timeout rule
- if queue remains nonzero after full queued capture:
  - keep status as `parked pending additional sold-truth replay capture window`
  - retain explicit queue metrics as blocker evidence.

### Automatic next step
- continue with guard-routed action:
  - `run_scope_expansion_capture_path`

### Phase 12 proof snapshot
- code edits:
  - `scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py` added
  - `tests/test_bef005_run_sold_truth_replay_capture_path.py` added
- compile:
  - `python -m py_compile scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py tests/test_bef005_run_sold_truth_replay_capture_path.py` -> pass
- tests:
  - `pytest tests/test_bef005_run_sold_truth_replay_capture_path.py -q` -> pass (`2`)
- runtime proof:
  - `python scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py --passes 1` at `2026-04-21T12:53:18Z` -> pass
- output truth:
  - queued capture:
    - `queue_rows_before=38`
    - `capture_pack_rows=38`
    - `capture_success_rows=38`
    - `capture_failed_rows=0`
  - post-rescore:
    - `queue_rows_after=0`
    - `queue_rows_reduced=38`
    - `queue_reduction_rate=1.0`
    - `sold_rows_total=57`
    - `sold_rows_with_model_side_evidence=57`
    - `sold_rows_missing_model_side_evidence=0`
    - `sold_truth_replay_queue_rows=0`
  - guard state:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - warning removed:
      - `sold_truth_replay_capture_required`
    - `next_action=run_scope_expansion_capture_path`
- phase status:
  - success threshold met and confirmed
  - phase complete (`ready_with_warnings`)

## 16) Phase 13 - scope-expansion capture execution window

### Goal
- execute the current guard action `run_scope_expansion_capture_path`.
- improve alignment expected coverage and reduce `no_source` rows with a bounded capture round.

### Files allowed to change
- this active plan folder

### Implementation tasks
- isolate and run one bounded scope-expansion capture round via:
  - `HF007` (`HF006 -> F008 -> F009 -> HF001 -> HF002 -> HF003 -> HF005`)
- rerun guard/accuracy scoring after the capture round.

### Isolated verification
- runtime-only phase (no code edits)

### Live monitoring target
- `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- one successful capture round with no capture failures.
- measurable drop in `no_source_rows`.
- guard remains `ready` with no sold-truth replay queue regression.

### Timeout rule
- if direct bridge overlap remains zero after round:
  - keep status as `ready_with_warnings`
  - retain next action `run_scope_expansion_capture_path` or escalate to identity-bridge expansion in next batch.

### Automatic next step
- design/execute identity-bridge resolution expansion to unblock:
  - `actuals_summary_direct_bridge_rows > 0`

### Phase 13 proof snapshot
- runtime proof:
  - `python scripts/one_off/HF007_run_alignment_coverage_recovery.py --max-rounds 1 --batch-size 20 --passes 1 --webscrape-mode data --skip-date-scraping --only-not-in-scrape --target-coverage 0.95 --target-no-source 0` -> pass
  - round truth:
    - `pack_rows=20`
    - `capture_success_rows=20`
    - `capture_failed_rows=0`
    - `alignment_total_rows=95`
    - `no_source_rows: 27 -> 7`
    - `expected_coverage_rate: 0.7158 -> 0.9263`
- post-round rescore:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` -> pass
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass
  - guard truth:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - `actuals_summary_direct_bridge_rows=0` (still zero)
    - `sold_truth_replay_queue_rows=0`
    - `next_action=run_scope_expansion_capture_path`
- phase status:
  - threshold met for bounded capture improvement
  - phase complete (`ready_with_warnings`)

## 17) Phase 14 - direct-bridge feasibility guard correction

### Goal
- prevent repeated scope-capture routing when direct bridge cannot improve with current identity and sold-truth overlap.
- surface explicit root-cause warning and route to identity resolution instead.

### Files allowed to change
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- add direct-bridge feasibility metrics in `BEF004`:
  - baseline sold ASIN row count
  - summary-identity pair overlap row count
  - direct-bridge feasible pair row count
- add warning `summary_direct_bridge_no_feasible_overlap` when:
  - direct bridge rows are zero
  - summary+identity overlap exists
  - feasible overlap to sold baseline is zero
- route next action to `expand_identity_bridge_resolution` for that state.

### Isolated verification
- `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check

### Success threshold
- guarded output includes the new feasibility metrics.
- when feasibility is zero, guard warning includes `summary_direct_bridge_no_feasible_overlap`.
- guard next action moves to `expand_identity_bridge_resolution`.

### Timeout rule
- if feasibility remains zero:
  - keep status as `ready_with_warnings`
  - run identity resolution expansion phase instead of repeated scope-capture cycles.

### Automatic next step
- execute Phase 15 gate (`EXECUTION_BATCH_014`) commercial readiness data sufficiency and 15-SKU validation panel.

### Phase 14 proof snapshot
- code edits:
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
  - `tests/test_bef004_run_sales_feedback_guarded_once.py`
- compile:
  - `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`9`)
- runtime proof:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` at `2026-04-21T14:15:03Z` -> pass
- output truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `actuals_summary_direct_bridge_rows=0`
  - `direct_bridge_baseline_asin_rows=57`
  - `direct_bridge_summary_identity_pair_overlap_rows=2358`
  - `direct_bridge_feasible_pair_rows=0`
  - warnings include:
    - `summary_direct_bridge_no_feasible_overlap`
  - `next_action=expand_identity_bridge_resolution`
- phase status:
  - threshold met and proven
  - phase complete (`ready_with_warnings`)

## 18) Phase 15 gate - commercial readiness data sufficiency and 15-SKU validation panel

### Goal
- decide, with evidence, whether we have enough data to build the commercial scorer now.
- separate:
  - data that is already strong enough to use
  - data that is still missing and must be collected first
- lock a fixed 15-SKU review panel covering big pass, big fail, and on-the-line cases.

### Why this gate exists
- the business target is tolerant decision quality, not exact prediction.
- before writing the scorer, we need to know whether each required data family is ready:
  - sold truth
  - model-side evidence
  - model decision replay
  - demand band inputs
  - starter test qty inputs
  - rank-window inputs
- latest evidence already shows a mixed picture:
  - `sold_rows_total=57`
  - `sold_rows_with_model_side_evidence=57`
  - `pass_rows=10`
  - `fail_rows=47`
  - `near_floor_rows=5`
  - `sold_capture_rows=38`
  - `sold_capture_success_rows=38`
  - `sold_rows_with_full_model_evidence=0`
  - `decision_judged_rows=0`
  - `sold_asin_bsr_window_overlap_rows=0`
- interpretation:
  - enough data exists to proceed with sold replay bridge coding and sales-band calibration.
  - not enough data exists yet to claim a proper sold-universe rank band.

### Files allowed to change
- `scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` (new)
- `scripts/one_off/F015_build_commercial_validation_panel.py` (new)
- `tests/test_f014_build_live_test_data_sufficiency_gate.py` (new)
- `tests/test_f015_build_commercial_validation_panel.py` (new)
- this active plan folder

### Implementation tasks
- build `F014` sufficiency summary from:
  - sold accuracy pack
  - sold replay capture pack
  - sold replay capture report
  - feeder backtest input view
- classify each required family as one of:
  - `ready_now`
  - `ready_after_replay_bridge`
  - `needs_rank_window_capture`
  - `insufficient_sample_mix`
- write an explicit gap plan for any missing family.
- build `F015` fixed 15-SKU validation panel with:
  - `big_pass`
  - `big_fail`
  - `on_the_line`
- make the panel deterministic and anchored to current sold truth, not ad-hoc manual selection.
- when rank-window coverage is missing, record the acquisition path:
  - recover sold decision fields through replay bridge first
  - then extract or capture sold-universe BSR/rank history so best/worst rank can be scored conservatively

### Output artifacts
- `out/analysis_reports/f_live_test_data_sufficiency_summary_latest.csv`
- `out/analysis_reports/f_live_test_data_gap_plan_latest.csv`
- `out/analysis_reports/f_live_test_validation_panel_15_latest.csv`
- plan anchor:
  - `plans/active/b-e-f-sales-feedback-loop-v1/COMMERCIAL_VALIDATION_PANEL_15.csv`

### Fixed 15-SKU validation panel
- `big_pass`:
  - `B06WW79DX5`
  - `B08KFFY86W`
  - `B086ZD7MG6`
  - `B07QQDMJ6M`
  - `9188805646`
- `big_fail`:
  - `B07F1MFWV1`
  - `B0CG234KW1`
  - `B07H2WXMDJ`
  - `B07T9WVBZ2`
  - `B072K2PG11`
- `on_the_line`:
  - `B07L6H9GZ2`
  - `B0BNLWBLMV`
  - `B07CN7NRF7`
  - `B07W65T6VT`
  - `B0CS3VF4GK`

### Isolated verification
- `python -m py_compile scripts/one_off/F014_build_live_test_data_sufficiency_gate.py scripts/one_off/F015_build_commercial_validation_panel.py tests/test_f014_build_live_test_data_sufficiency_gate.py tests/test_f015_build_commercial_validation_panel.py`
- `pytest tests/test_f014_build_live_test_data_sufficiency_gate.py tests/test_f015_build_commercial_validation_panel.py -q`
- runtime proof:
  - `python scripts/one_off/F014_build_live_test_data_sufficiency_gate.py`
  - `python scripts/one_off/F015_build_commercial_validation_panel.py`

### Success threshold
- sufficiency summary explicitly reports:
  - `sales_band_data_state=ready_now`
  - `decision_replay_state=ready_after_replay_bridge`
  - `rank_window_state=needs_rank_window_capture`
- validation panel output contains:
  - `15` unique ASINs
  - `5` rows in `big_pass`
  - `5` rows in `big_fail`
  - `5` rows in `on_the_line`
- every validation-panel row exists in sold accuracy truth.

### Timeout rule
- if the gate finds a new hard blocker beyond decision replay and rank-window capture:
  - keep status as `ready_with_warnings`
  - set status to `parked pending unexpected data blocker resolution`
  - record the exact family and exact missing counts.

### Automatic next step
- if the gate outcome matches current theory:
  - execute Phase 16 (`EXECUTION_BATCH_012`) sold replay bridge.
  - keep rank-window acquisition as a required dependency for Phase 17.

### Non-goals
- no Google Sheets writes.
- no local DB alignment rewrites.
- no exact-unit predictor tuning.
- no claim that live-test readiness is proven before decision replay and rank-window gaps are closed.

### Phase 15 gate proof snapshot
- code edits:
  - `scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` added
  - `scripts/one_off/F015_build_commercial_validation_panel.py` added
  - `tests/test_f014_build_live_test_data_sufficiency_gate.py` added
  - `tests/test_f015_build_commercial_validation_panel.py` added
- compile:
  - `python -m py_compile scripts/one_off/F014_build_live_test_data_sufficiency_gate.py scripts/one_off/F015_build_commercial_validation_panel.py tests/test_f014_build_live_test_data_sufficiency_gate.py tests/test_f015_build_commercial_validation_panel.py` -> pass
- tests:
  - `pytest tests/test_f014_build_live_test_data_sufficiency_gate.py tests/test_f015_build_commercial_validation_panel.py -q` -> pass (`4`)
- runtime proof (`2026-04-21T15:27:50Z`):
  - `python scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` -> pass
  - `python scripts/one_off/F015_build_commercial_validation_panel.py` -> pass
- output truth:
  - sufficiency states:
    - `sold_truth_state=ready_now`
    - `model_side_evidence_state=ready_now`
    - `decision_replay_state=ready_after_replay_bridge`
    - `sales_band_data_state=ready_now`
    - `starter_qty_input_state=ready_after_replay_bridge`
    - `rank_window_state=needs_rank_window_capture`
    - `sample_mix_state=ready_now`
  - fixed panel:
    - `panel_rows_total=15`
    - `panel_missing_rows=0`
    - `big_pass_rows=5`
    - `big_fail_rows=5`
    - `on_the_line_rows=5`
  - gap plan:
    - `decision_replay_state -> EXECUTION_BATCH_012`
    - `starter_qty_input_state -> EXECUTION_BATCH_012`
    - `rank_window_state -> EXECUTION_BATCH_013`
- phase status:
  - threshold met and proven
  - phase complete (`ready_with_warnings`)

## 19) Phase 16 - sold-universe decision replay and commercial bridge

### Goal
- align measurement to sold products first, not unsold overlap volume.
- recover sold-row decision-state evidence and existing commercial guidance fields so the system can be judged on useful buy-test behavior.

### Why this phase is required
- Phase 15 gate confirms we already have enough sold truth and sales-side evidence to proceed.
- the missing family is decision-state evidence, not sold-truth coverage.
- latest sold accuracy snapshot shows:
  - `sold_rows_total=57`
  - `sold_rows_with_model_side_evidence=57`
  - `sold_rows_with_full_model_evidence=0`
  - `decision_judged_rows=0`
- latest guard snapshot shows:
  - `actuals_summary_direct_bridge_rows=0`
  - `direct_bridge_feasible_pair_rows=0`
- structural overlap check confirms:
  - sold ASIN overlap with live summary ASINs is `0`
  - sold ASIN overlap inside summary+identity pair universe is `0`
- this means repeated scope capture cannot recover sold decision coverage on its own.
- existing repo direction already favors commercial bands and starter sizing:
  - feeder already uses `estimated_demand` buckets and `recommended_test_qty`
  - restock blueprint already frames v1 as starter settings and banded recommendation logic
- this phase therefore exists to recover the sold-row fields those banded decisions depend on.

### Files allowed to change
- `scripts/one_off/BEF006_build_sold_decision_replay_bridge.py` (new)
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef006_build_sold_decision_replay_bridge.py` (new)
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- build sold decision replay bridge artifact keyed by sold `asin`:
  - include `model_decision_state`, `model_decision_confidence`, expected units/profit, and replay source.
  - carry `estimated_demand`, `recommended_test_qty`, and `recommendation_status` when available from existing learning assumptions.
- update `F011` precedence so sold rows resolve model fields from:
  - sold decision replay bridge first
  - live summary second
  - alignment estimate fallback third
- keep explicit coverage and commercial-carry metrics:
  - `sold_rows_with_full_model_evidence`
  - `decision_judged_rows`
  - `bucket::missing_model_decision`
  - `rows_with_recommended_test_qty`
  - `rows_with_demand_bucket`
- update `BEF004` routing so sold decision coverage shortfall points to replay coverage work, not generic scope-capture looping.

### Isolated verification
- `python -m py_compile scripts/one_off/BEF006_build_sold_decision_replay_bridge.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_sold_decision_replay_latest.csv`
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `sold_rows_with_full_model_evidence >= 40`
- `decision_judged_rows >= 40`
- `rows_with_recommended_test_qty >= 40`
- `bucket::missing_model_decision` reduced below `17`
- guard next action no longer routes to generic scope-capture for sold decision coverage.

### Timeout rule
- if threshold is not met after one full replay build:
  - keep status as `ready_with_warnings`
  - set status to `parked pending sold decision replay source expansion`
  - record exact missing rows and top missing-source reasons in plan status.

### Automatic next step
- after threshold is met:
  - execute Phase 17 (`EXECUTION_BATCH_013`) commercial decision bands and live-test readiness.

### Non-goals
- no Google Sheets writes.
- no local DB alignment rewrites.
- no broad unsold scraping as primary predictor-accuracy proof.
- no exact month-unit prediction as the main business sign-off target.

### Phase 16 proof snapshot
- code edits:
  - `scripts/one_off/BEF006_build_sold_decision_replay_bridge.py` added
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py` updated (replay-first precedence + commercial carry metrics)
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` updated (sold replay coverage routing)
  - `tests/test_bef006_build_sold_decision_replay_bridge.py` added
  - `tests/test_f011_build_sales_history_accuracy_pack.py` updated
  - `tests/test_bef004_run_sales_feedback_guarded_once.py` updated
- compile:
  - `python -m py_compile scripts/one_off/BEF006_build_sold_decision_replay_bridge.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`16`)
- runtime proof (`2026-04-21T15:45:45Z`):
  - `python scripts/one_off/BEF006_build_sold_decision_replay_bridge.py` -> pass
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` -> pass
- output truth:
  - replay bridge:
    - `sold_rows_total=57`
    - `sold_decision_replay_coverage_rows=57`
    - `sold_rows_with_full_model_evidence=57`
    - `rows_with_demand_bucket=57`
    - `rows_with_recommended_test_qty=57`
    - `rows_with_recommendation_status=57`
  - accuracy pack:
    - `sold_rows_with_model_side_evidence=57`
    - `sold_rows_missing_model_side_evidence=0`
    - `decision_judged_rows=57`
    - `bucket::missing_model_decision=0`
  - guard:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - `next_action=expand_identity_bridge_resolution`
- phase status:
  - threshold met and proven
  - phase complete (`ready_with_warnings`)

## 20) Phase 17 - commercial decision bands and live-test readiness

### Goal
- judge whether a product is worth testing, not whether the model guessed the exact monthly unit count.
- output a safe starter quantity, a sales range, a rank range, and a negative-mode risk view.

### Why this phase is required
- the business target is:
  - is demand consistent enough
  - is profit healthy enough
  - is the product drifting into a negative mode
  - is the rank normally stable enough, not just lucky on one snapshot
  - how much should we order to start testing
- the business target is not exact unit precision.
- Phase 15 gate plus Phase 16 execution established that:
  - sales-band data is ready
  - sold decision replay is now recovered (`57/57` coverage)
  - sold rank-window data still needs acquisition
- this phase must therefore fail closed if rank range is not yet trustworthy.

### Files allowed to change
- `scripts/one_off/F013_build_live_test_readiness_pack.py` (new)
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f013_build_live_test_readiness_pack.py` (new)
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- this active plan folder

### Implementation tasks
- build a live-test readiness pack from sold truth plus recovered commercial fields.
- classify each judged row into:
  - `demand_consistency_band`
  - `sales_lower_30d`
  - `sales_upper_30d`
  - `sales_rank_best_observed`
  - `sales_rank_worst_observed`
  - `sales_rank_stability_band`
  - `rank_snapshot_risk_state`
  - `profit_risk_band`
  - `negative_mode_truth_state`
  - `starter_test_qty_recommended`
  - `starter_order_band`
  - `commercial_decision_state`
  - `live_test_readiness_state`
- score business-useful mistakes, not just forecast misses:
  - `false_green_rows`
  - `false_red_rows`
  - `negative_mode_miss_rows`
  - `starter_qty_too_high_rows`
  - `starter_qty_too_low_rows`
- make first-test decisioning conservative:
  - use lower sales bound for starter quantity decisions
  - use worse observed rank side when stability is borderline
- require manual spot-check output against the fixed 15-SKU panel from Phase 15 gate.
- reuse existing repo logic direction where possible:
  - feeder demand buckets
  - feeder recommended test qty
  - restock starter-band rule style

### Isolated verification
- `python -m py_compile scripts/one_off/F013_build_live_test_readiness_pack.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`

### Live monitoring target
- `out/analysis_reports/f_live_test_readiness_pack_latest.csv`
- `out/analysis_reports/f_live_test_readiness_summary_latest.csv`
- `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`

### Poll cadence
- immediate post-run check
- one follow-up check at `+5 minutes`

### Success threshold
- `commercial_judged_rows >= 40`
- `false_green_rows` explicit
- `false_red_rows` explicit
- `negative_mode_miss_rows` explicit
- `live_test_ready_rows` explicit
- fixed 15-SKU panel receives explicit commercial state output.

### Timeout rule
- if enough sold rows still cannot be commercially judged:
  - keep status as `ready_with_warnings`
  - set status to `parked pending commercial-band source expansion`
  - record exact missing field families, not just generic coverage counts.

### Automatic next step
- after threshold is met:
  - if `rank_gap_rows > 0`, run sold rank-window capture and rerun `F013` before any live-test release.
  - if rank coverage is present and `live_test_ready_rows > 0`, move into bounded shadow live testing using the banded decision outputs.

### Non-goals
- no Google Sheets writes.
- no local DB alignment rewrites.
- no exact-unit prediction tuning as the main sign-off gate.

### Phase 17 proof snapshot
- code edits:
  - `scripts/one_off/F013_build_live_test_readiness_pack.py` added
  - `tests/test_f013_build_live_test_readiness_pack.py` added
  - `scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` updated (rank-window source includes full-capture manifests/raw JSON)
  - `tests/test_f014_build_live_test_data_sufficiency_gate.py` updated
- compile:
  - `python -m py_compile scripts/one_off/F013_build_live_test_readiness_pack.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
  - `python -m py_compile scripts/one_off/F014_build_live_test_data_sufficiency_gate.py tests/test_f014_build_live_test_data_sufficiency_gate.py` -> pass
- tests:
  - `pytest tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`19`)
  - `pytest tests/test_f014_build_live_test_data_sufficiency_gate.py -q` -> pass (`3`)
- runtime proof (`2026-04-21T20:49:30Z`):
  - `python scripts/one_off/F013_build_live_test_readiness_pack.py` -> pass
  - `python scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` at `2026-04-21T20:51:57Z` -> pass
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` at `2026-04-21T20:49:37Z` -> pass
- output truth:
  - commercial summary:
    - `commercial_rows_total=57`
    - `commercial_judged_rows=57`
    - `false_green_rows=0`
    - `false_red_rows=8`
    - `negative_mode_miss_rows=0`
    - `starter_qty_too_high_rows=0`
    - `starter_qty_too_low_rows=8`
    - `band_hit_rows=23`
    - `live_test_ready_rows=2`
    - `rank_gap_rows=0`
    - `rows_using_backtest_rank_window=0`
    - `rows_using_full_capture_rank_window=57`
    - `rows_missing_rank_window=0`
  - sufficiency gate states:
    - `sold_truth_state=ready_now`
    - `model_side_evidence_state=ready_now`
    - `decision_replay_state=ready_now`
    - `sales_band_data_state=ready_now`
    - `starter_qty_input_state=ready_now`
    - `rank_window_state=ready_now`
    - `sample_mix_state=ready_now`
  - fixed 15-SKU panel class outcomes:
    - `panel_rows_total=15`
    - `panel_rows_with_blank_commercial_state=0`
    - `panel_big_pass_test_buy_rows=1`
    - `panel_big_pass_watch_rows=0`
    - `panel_big_pass_reject_rows=4`
    - `panel_big_fail_test_buy_rows=0`
    - `panel_big_fail_watch_rows=0`
    - `panel_big_fail_reject_rows=5`
    - `panel_on_the_line_test_buy_rows=1`
    - `panel_on_the_line_watch_rows=0`
    - `panel_on_the_line_reject_rows=4`
  - guard:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - `next_action=expand_identity_bridge_resolution`
- phase status:
  - threshold met and proven for commercial banded scoring output
  - sold rank-window source recovery proven (`rank_gap_rows=0`)
  - phase complete (`ready_with_warnings`), bounded shadow live testing path now unblocked for `ready_for_live_test` rows

## 21) Phase 18 - stocked-SKU current vetting report

### Goal
- produce a direct commercial report from stocked sold SKUs:
  - what passes today
  - what fails today
  - what would have happened if we screened the same stocked rows 30 days ago
  - what the next 30 days actually delivered

### Why this phase is required
- the user asked for a business report, not more hidden scoring logic.
- the report must stay on stocked sold SKUs because that is where actual outcome exists.
- the report must surface sample weakness plainly instead of pretending the 30-days-ago side is stronger than it is.

### Files allowed to change
- `scripts/one_off/F016_build_stocked_sku_vetting_report.py` (new)
- `tests/test_f016_build_stocked_sku_vetting_report.py` (new)
- this active plan folder
- `WORK_LOG.md`

### Implementation tasks
- build a one-off stocked-SKU report from:
  - `f_live_test_readiness_pack_latest.csv`
  - `f_sales_history_learning_actuals_latest.csv`
  - full-capture BBP rank series
- emit:
  - current commercial decision state
  - current live-test readiness state
  - reconstructed 30-days-ago decision state
  - next-30-day outcome
  - decision-vs-outcome label
- emit a summary file and markdown note so the report can be reused without shell work.

### Isolated verification
- `python -m py_compile scripts/one_off/F016_build_stocked_sku_vetting_report.py tests/test_f016_build_stocked_sku_vetting_report.py`
- `pytest tests/test_f016_build_stocked_sku_vetting_report.py -q`

### Live monitoring target
- `out/analysis_reports/f_stocked_sku_vetting_report_latest.csv`
- `out/analysis_reports/f_stocked_sku_vetting_summary_latest.csv`
- `out/analysis_reports/f_stocked_sku_vetting_report_latest.md`

### Success threshold
- row-by-row report exists for the stocked sold set.
- current pass/watch/reject split is explicit.
- 30-days-ago report side is explicit, including any data-thin limitation.

### Automatic next step
- if prior-window coverage is still blank across the sold set:
  - keep using current commercial pack for live-test selection
  - treat older-window learning as sample-limited until a wider sold history slice is brought in

### Phase 18 proof snapshot
- code edits:
  - `scripts/one_off/F016_build_stocked_sku_vetting_report.py` added
  - `tests/test_f016_build_stocked_sku_vetting_report.py` added
- compile:
  - `python -m py_compile scripts/one_off/F016_build_stocked_sku_vetting_report.py tests/test_f016_build_stocked_sku_vetting_report.py` -> pass
- tests:
  - `pytest tests/test_f016_build_stocked_sku_vetting_report.py -q` -> pass (`1`)
- runtime proof (`2026-04-22T07:51:47Z`):
  - `python scripts/one_off/F016_build_stocked_sku_vetting_report.py` -> pass
- output truth:
  - `rows_total=57`
  - `current_test_buy_rows=2`
  - `current_watch_rows=1`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=2`
  - `prior_test_buy_rows=0`
  - `prior_watch_rows=0`
  - `prior_reject_rows=57`
  - `prior_nonzero_units_rows=0`
  - `prior_nonzero_profit_rows=0`
  - `prior_missed_winner_rows=10`
  - `prior_avoided_loser_rows=47`
- phase status:
  - complete (`ready_with_warnings`)
  - current live-test selection is usable
  - 30-days-ago learning remains sample-limited because the prior 30-day window is blank across this sold set

## 22) Phase 19 - Sellerboard order-alignment investigation

### Goal
- align our local sold-truth layers to Sellerboard order-item truth for sales values and unit counts.
- fix missing-order issues before trusting refreshed pass/watch/reject outputs.

### Why this phase is required
- current commercial decisions are being fed by at least some wrong sales truth.
- proof case already established:
  - `B07L6H9GZ2` has `20` units in Sellerboard order items for `2026-03-23` to `2026-04-21`
  - our sold-truth pack shows `4`
  - our daily truth layer shows `4`
- this is a root-cause data problem, not a threshold problem.

### Files allowed to change
- upstream sales-truth builders and tests only
- this active plan folder
- `WORK_LOG.md`

### Implementation tasks
- compare Sellerboard order items against local truth for the same date window.
- classify mismatches by order presence, units, sales values, mapping, filters, and refund handling.
- separate expected fee/COG tolerances from real sales-truth misses.
- identify the earliest broken pipeline stage.
- implement the smallest upstream fix.
- rerun the affected builder chain and the stocked-SKU vetting report.

### Isolated verification
- targeted compile on changed scripts/tests
- targeted pytest on changed scripts/tests

### Live monitoring target
- alignment-audit output for the comparison window
- `out/sku_daily_sales_truth_latest.csv`
- `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- `out/analysis_reports/f_stocked_sku_vetting_report_latest.csv`

### Success threshold
- Sellerboard and local order presence align materially for the comparison window.
- Sellerboard and local unit counts align materially for the comparison window.
- remaining differences are mainly fee or COG timing classes, not missing orders.
- `B07L6H9GZ2` no longer shows the current obvious undercount.

### Automatic next step
- once order alignment is corrected:
  - rerun the stocked-SKU vetting report
  - recheck current pass/watch/reject counts against corrected truth

## 23) Phase 20 - pass-gate decomposition and false-red recovery planning

### Goal
- reset the pass structure using the refreshed rerun state.
- plan explicit next-phase pass checks that separate true commercial fails from legacy-model rejects.

### Why this phase is required
- after the refreshed rerun, the current structure is:
  - `rows_total=58`
  - `current_test_buy_rows=1`
  - `current_watch_rows=3`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=1`
- the biggest problem is now visible:
  - profitable rows are still being blocked by inherited `recommendation_status=reject` plus `starter_test_qty_recommended=0`
  - this is creating `hold` outcomes on rows that are not negative-mode failures
- the next work should therefore be staged pass checks, not another generic rerun.

### Files allowed to change
- this active plan folder
- `WORK_LOG.md`

### Planning tasks
- define a pass-gate decomposition phase.
- define a false-red recovery phase.
- define an expanded validation-panel phase.
- define staged shadow-live pass checks.

### Refreshed rerun proof snapshot
- rerun commands:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass (`2026-04-22T13:33:05Z`)
  - `python scripts/one_off/F013_build_live_test_readiness_pack.py` -> pass (`2026-04-22T13:33:06Z`)
  - `python scripts/one_off/F016_build_stocked_sku_vetting_report.py` -> pass (`2026-04-22T13:33:09Z`)
- latest pass structure:
  - `current_test_buy_rows=1`
  - `current_watch_rows=3`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=1`
- latest commercial scoring:
  - `false_green_rows=0`
  - `false_red_rows=12`
  - `starter_qty_too_high_rows=3`
  - `starter_qty_too_low_rows=12`
- profitable rejects above `GBP20` remain material:
  - `12` rows
  - common block pattern is `recommendation_status=reject` and `starter_order_band=hold`

### Files allowed to change
- `scripts/one_off/F017_build_pass_gate_review_pack.py` (new)
- `tests/test_f017_build_pass_gate_review_pack.py` (new)
- this active plan folder
- `WORK_LOG.md`

### Implementation tasks
- join the current live-test readiness pack to the sold-truth accuracy pack.
- emit an explicit first blocker for every non-pass row.
- classify profitable rejects into:
  - `promote_to_test_buy`
  - `promote_to_watch`
  - `review_only_profitable_reject`
  - `keep_reject`
- emit an expanded pass panel covering:
  - current `test_buy`
  - current `watch`
  - profitable rejects above `GBP20`
  - near-floor review rows

### Isolated verification
- `python -m py_compile scripts/one_off/F017_build_pass_gate_review_pack.py tests/test_f017_build_pass_gate_review_pack.py`
- `pytest tests/test_f017_build_pass_gate_review_pack.py -q`

### Live monitoring target
- `out/analysis_reports/f_pass_gate_review_pack_latest.csv`
- `out/analysis_reports/f_pass_gate_review_summary_latest.csv`
- `out/analysis_reports/f_pass_gate_review_panel_latest.csv`

### Phase 20 proof snapshot
- code edits:
  - `scripts/one_off/F017_build_pass_gate_review_pack.py` added
  - `tests/test_f017_build_pass_gate_review_pack.py` added
- compile:
  - `python -m py_compile scripts/one_off/F017_build_pass_gate_review_pack.py tests/test_f017_build_pass_gate_review_pack.py` -> pass
- tests:
  - `pytest tests/test_f017_build_pass_gate_review_pack.py -q` -> pass (`1`)
- runtime proof (`2026-04-22T13:41:57Z`):
  - `python scripts/one_off/F017_build_pass_gate_review_pack.py` -> pass
- output truth:
  - `rows_total=58`
  - `profitable_reject_rows=12`
  - `false_red_candidate_rows=6`
  - `promote_to_test_buy_rows=2`
  - `promote_to_watch_rows=4`
  - `review_only_profitable_reject_rows=6`
  - `tier_a_rows=3`
  - `tier_b_rows=7`
  - `tier_c_rows=6`
  - `expanded_panel_rows_total=18`
- phase status:
  - complete (`ready_with_warnings`)
  - false-red recovery is now measurable and staged without mutating the original commercial pack

### Phase 19 execution snapshot
- current phase:
  - rebase E sold-truth builders on `financial_events_level2` sales rows before the B004 token-COGS holdback.
- files allowed in this pass:
  - `scripts/flows/E/e_sales_truth_common.py`
  - `scripts/flows/E/E002_build_roi_snapshot.py`
  - `scripts/flows/E/E006_build_sales_truth_reconciliation.py`
  - `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
  - `tests/test_e002_build_roi_snapshot.py`
  - `tests/test_e006_build_sales_truth_reconciliation.py`
  - `tests/test_e007_build_sku_daily_sales_truth.py`
  - this active plan folder
- isolated verification:
  - `python -m py_compile scripts/flows/E/e_sales_truth_common.py scripts/flows/E/E002_build_roi_snapshot.py scripts/flows/E/E006_build_sales_truth_reconciliation.py scripts/flows/E/E007_build_sku_daily_sales_truth.py tests/test_e002_build_roi_snapshot.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py`
  - `pytest tests/test_e002_build_roi_snapshot.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py -q`
- live rebuild chain after isolated verification:
  - `python scripts/flows/E/E002_build_roi_snapshot.py`
  - `python scripts/flows/E/E006_build_sales_truth_reconciliation.py`
  - `python scripts/flows/E/E007_build_sku_daily_sales_truth.py`
  - `python scripts/one_off/BEF000_build_sales_truth_foundation.py`
  - `python scripts/one_off/BEF001_build_operational_feedback_seed.py`
  - `python scripts/one_off/BEF002_build_sales_feedback_actuals.py`
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `python scripts/one_off/F013_build_live_test_readiness_pack.py`
  - `python scripts/one_off/F016_build_stocked_sku_vetting_report.py`

### Phase 19 proof snapshot
- code edits:
  - `scripts/flows/E/e_sales_truth_common.py` added
  - `scripts/flows/E/E002_build_roi_snapshot.py` updated
  - `scripts/flows/E/E006_build_sales_truth_reconciliation.py` updated
  - `scripts/flows/E/E007_build_sku_daily_sales_truth.py` updated
  - `tests/test_e002_build_roi_snapshot.py` updated
  - `tests/test_e006_build_sales_truth_reconciliation.py` updated
  - `tests/test_e007_build_sku_daily_sales_truth.py` updated
- compile:
  - `python -m py_compile scripts/flows/E/e_sales_truth_common.py scripts/flows/E/E002_build_roi_snapshot.py scripts/flows/E/E006_build_sales_truth_reconciliation.py scripts/flows/E/E007_build_sku_daily_sales_truth.py tests/test_e002_build_roi_snapshot.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py` -> pass
- tests:
  - `pytest tests/test_e002_build_roi_snapshot.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py -q` -> pass (`12`)
- rebuild chain:
  - `E002` -> `rows=61`
  - `E006` -> `rows=61`, `mismatch_rows=0`
  - `E007` -> `rows=443`, `finalized_rows=406`, `provisional_rows=37`
  - `BEF000` -> `foundation_rows=162`
  - `BEF001` -> `rows=162`
  - `BEF002` -> `rows_total=118`, `operational_baseline_rows=59`
  - `F011` -> `sold_rows_total=59`, `decision_judged_rows=56`
  - `F013` -> `commercial_rows_total=59`, `live_test_ready_rows=2`
  - `F016` -> `report_rows=59`
- main proof case `B07L6H9GZ2`:
  - Sellerboard order items in `2026-03-23` to `2026-04-21`: `20` units
  - pre-fix local sold truth: `4` units
  - post-fix `sales_truth_sku_30d_latest.csv`: `20` units, `181.82` revenue GBP, `19.84` profit GBP
  - post-fix `f_stocked_sku_vetting_report_latest.csv`: `current_actual_units_30d=20`
- current residual audit note:
  - the B004 token-COGS leak is corrected in E for missing-order recovery
  - exact fixed-window parity is still limited on some SKUs because `sku_daily_sales_truth_latest.csv` remains a rolling 30-day snapshot anchored to the latest local day, not a dedicated `2026-03-23` to `2026-04-21` audit artifact

### Phase 19 completion addendum - fixed-window alignment proof refresh (`2026-04-22T10:17:25Z`)
- additional code edits:
  - `scripts/one_off/BEF007_build_sellerboard_window_alignment_audit.py` added
  - `tests/test_bef007_build_sellerboard_window_alignment_audit.py` added
- compile:
  - `python -m py_compile scripts/one_off/BEF007_build_sellerboard_window_alignment_audit.py tests/test_bef007_build_sellerboard_window_alignment_audit.py` -> pass
- tests:
  - `pytest tests/test_bef007_build_sellerboard_window_alignment_audit.py -q` -> pass (`1`)
- rerun chain:
  - `E002` -> `rows=60`
  - `E006` -> `rows=60`, `mismatch_rows=0`
  - `E007` -> `rows=442`, `finalized_rows=406`, `provisional_rows=36`
  - `BEF000` -> `foundation_rows=162`
  - `BEF001` -> `rows=162`
  - `BEF002` -> `rows_total=116`, `alignment_rows_matched=58`, `operational_baseline_rows=58`
  - `F011` -> `sold_rows_total=58`, `decision_judged_rows=55`
  - `F013` -> `commercial_rows_total=58`, `live_test_ready_rows=2`
  - `F016` -> `report_rows=58`
- fixed-window audit summary (`BEF007`):
  - Sellerboard units total: `1968.0`
  - local level2 units total: `1932.0`
  - local order_master units total: `1911.0`
  - local daily truth units total: `1899.0`
  - discrepancy class counts:
    - `units_aligned_value_basis_gap=36`
    - `no_window_sales=34`
    - `upstream_level2_vs_sellerboard_mismatch=10`
    - `daily_truth_window_or_filter_gap=7`
    - `post_level2_truth_shortfall=5`
    - `recovered_from_level2_gap=5`
- focus row-level proof `B07L6H9GZ2` / `2X-8XI7-C9T5`:
  - Sellerboard item rows in window: `20`
  - present in `financial_events_level2`: `20/20`
  - present in `financial_events_level3_official`: `7/20`
  - present in `order_master`: `4/20`
  - present in `order_ledger_fx`: `4/20`
  - units:
    - Sellerboard order items: `20.0`
    - local level2: `20.0`
    - local order_master: `4.0`
    - local daily truth: `20.0`
  - sales values:
    - Sellerboard order-item gross: `208.54`
    - local daily-truth revenue GBP: `181.82`
  - class: `recovered_from_level2_gap`
- updated current vetting counts (`f_stocked_sku_vetting_summary_latest.csv`):
  - `current_test_buy_rows=2`
  - `current_watch_rows=2`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=2`
- phase status:
  - `complete` for scoped order-alignment investigation and rerun proof
  - residual gaps now explicitly classified; focus undercount is corrected in sold truth

### Phase 19B completion addendum - order-master holdback root cause (`2026-04-22T10:42:57Z`)
- root cause:
  - `scripts/flows/B/B004_build_order_master.py` was intentionally deleting positive-qty rows when no token COGS key existed.
  - this violated the local rule that anything present in `level1` must still appear in `order_master` as provisional truth.
  - `scripts/flows/A/A015_build_system_health_check.py` was also normalizing that behavior by treating missing-token omissions as acceptable coverage exceptions.
- code edits:
  - `scripts/flows/B/B004_build_order_master.py` updated:
    - keep provisional rows in `order_master` even when token COGS is missing
    - keep `orders_missing_tokens.csv` and `l1_missing_fee_keys.csv` as observability sidecars only
  - `scripts/flows/A/A015_build_system_health_check.py` updated:
    - stop subtracting missing-token and missing-fee sidecars from `l1_keys_missing_in_master`
    - stop using token-eligible-only recency as the `order_master` date-gap baseline
  - `tests/test_b004_level_gate.py` updated
  - `tests/test_a015_health_check_runtime.py` updated
- isolated verification:
  - `python -m py_compile scripts/flows/B/B004_build_order_master.py scripts/flows/A/A015_build_system_health_check.py tests/test_b004_level_gate.py tests/test_a015_health_check_runtime.py` -> pass
  - `PYTHONPATH=. pytest tests/test_b004_level_gate.py -q` -> pass (`6`)
  - `PYTHONPATH=. pytest tests/test_a015_health_check_runtime.py -q -k "order_master_l1_coverage_stats_does_not_ignore_sidecar_missing_keys"` -> pass (`1`)
  - note:
    - broader `tests/test_a015_health_check_runtime.py` has unrelated pre-existing failures in the current worktree; not caused by this patch
- local B proof:
  - manual local-only rebuild:
    - `ORDER_MASTER_SKIP_SHEETS=1 ORDER_MASTER_L1_STABLE_SECONDS=0 python scripts/flows/B/B004_build_order_master.py` -> pass
  - builder evidence:
    - `l1_missing_fees_observed=1`
    - `missing_token_cogs_observed=73`
    - rows written: `9775`
- fixed-window proof after rebuild (`2026-03-23` to `2026-04-21`):
  - before patch:
    - Sellerboard rows missing from `order_master`: `65`
    - Sellerboard units missing from `order_master`: `68.0`
  - after patch:
    - Sellerboard rows missing from `order_master`: `0`
    - Sellerboard units missing from `order_master`: `0.0`
  - focus proof `B07L6H9GZ2` / `2X-8XI7-C9T5`:
    - Sellerboard units: `20.0`
    - `order_master` units: `20.0`
    - `sku_daily_sales_truth` units: `20.0`
    - Sellerboard order-item rows present in `order_master`: `20/20`
- remaining residual gap:
  - Sellerboard rows still missing from `level2`: `33`
  - units still missing from `level2`: `35.0`
  - class is unchanged:
    - all are Sellerboard `Unshipped`
  - this is a separate upstream collection gap, not an `order_master` drop anymore
- verification status:
  - B-side local proof complete
  - A-side live health verification not run in this ticket because repo policy forbids ad-hoc A runs without explicit user request

### Phase 20 planning addendum - canceled-order token release (`2026-04-22T13:25:00Z`)
- planning intent:
  - fix the upstream token-state bug where tokens stay allocated after the linked Amazon order is later canceled
  - release those tokens back into live availability inside the normal B token allocation path
  - let the same B run immediately reuse the released tokens for current real sold demand
  - keep a clear audit trail of what was released and why
  - do not use one-off reset/reallocate scripts as the daily fix
- researched root cause:
  - `scripts/flows/B/B007_allocate_tokens_live.py` allocates new tokens but has no symmetrical release path for stale allocations
  - `scripts/flows/B/B004_build_order_master.py` removes keys that disappear from current L1, including canceled orders, so the sold-order side moves on
  - `scripts/flows/B/B008_apply_refunds_to_tokens.py` handles refund returns
  - `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py` handles stock-event movement
  - there is no equivalent runtime path for explicit order cancellation release
- current evidence baseline:
  - `62` allocated token units are still tied to orders now marked `Canceled` in `out/orders_all.csv`
  - all `62` stuck units are absent from current `order_master`
  - proof SKU `Q1-00D7-5IQF`:
    - token allocations live: `50`
    - current sold orders in `order_master`: `49`
    - current missing-token orders: `5`
    - stuck canceled allocations: `6`
  - conclusion:
    - the apparent arithmetic contradiction is caused by canceled-order allocations not being released
- smallest upstream fix:
  - primary implementation target stays `scripts/flows/B/B007_allocate_tokens_live.py`
  - add a pre-allocation release pass inside B007, before new allocation starts
  - release only when cancellation is explicit, not inferred from absence alone
- planned release rule:
  - release an allocated token when all of these are true:
    - token is currently marked `allocated`
    - it has an allocation row in `token_allocations_live.csv`
    - linked `order_id` is explicitly `Canceled` in current `out/orders_all.csv`
    - linked `(order_id, sku)` is not part of current positive sold demand for this run
- planned release action:
  - in `token_ledger_live.csv`:
    - change token `status` from `allocated` to `available`
    - clear `allocated_order_id`
    - clear `allocated_date`
    - append a release note with reason `canceled_order_release`
  - in `token_allocations_live.csv`:
    - remove the released allocation rows so downstream COGS no longer counts them
  - then continue normal B007 allocation so freed tokens can satisfy current missing sold orders in the same run
- audit and operator evidence:
  - add a dedicated local evidence file:
    - `out/token_cancel_release_events.csv`
  - one row per released token with:
    - `release_ts`
    - `order_id`
    - `seller_sku`
    - `token_id`
    - `order_status`
    - `release_reason`
    - `previous_allocation_date`
    - `notes`
  - local only in this phase
  - no Google Sheets write for this evidence file
- health and alert additions:
  - add a new B-scoped health item in `scripts/flows/A/A015_build_system_health_check.py`:
    - `allocated_tokens_on_canceled_orders`
  - rule:
    - `fail` when count > `0` after the B run
  - write a detail file with the stuck rows if any remain
  - optional informational count:
    - `token_cancel_release_events_rows`
  - releases themselves are not the fault condition; unreleased canceled allocations are the fault condition
- files in scope for coding:
  - `scripts/flows/B/B007_allocate_tokens_live.py`
  - `scripts/flows/B/B025_build_token_cogs_ledger.py` only if release cleanup needs compatibility support
  - `scripts/flows/A/A015_build_system_health_check.py`
  - `tests/test_b007_allocate_tokens_live.py`
  - `tests/test_a015_health_check_runtime.py`
  - this active plan folder
- non-goals:
  - no Google Sheets changes
  - no use of `scripts/flows/B/B033_reset_allocations_and_reallocate.py` as the daily fix
  - no local DB rewrite
  - no placeholder-COGS masking change except where real token release naturally reduces placeholder demand
  - do not release tokens merely because an order is temporarily absent from one file
- coding sequence:
  - `1.` add a helper in B007 to identify canceled allocations safely from current `out/orders_all.csv` plus current positive sold demand
  - `2.` release those allocations in memory before allocation begins
  - `3.` persist cleaned `token_ledger_live.csv` and `token_allocations_live.csv`
  - `4.` write `out/token_cancel_release_events.csv`
  - `5.` continue normal allocation in the same B007 run
  - `6.` add the B-scoped A015 check for unreleased canceled allocations
  - `7.` rerun `B007`, `B025`, and `B004` locally and confirm shortage reduction comes from released canceled tokens rather than masking
- required isolated tests:
  - B007 releases tokens for orders explicitly marked `Canceled`
  - B007 does not release allocations for non-canceled orders
  - B007 does not release purely from missing-order absence without explicit cancel truth
  - B007 can reallocate a released token in the same run to a current missing sold order
  - A015 reports `allocated_tokens_on_canceled_orders` as `fail` when residue remains and `ok` when cleared
- local proof target when coding starts:
  - canceled allocated rows decrease from current baseline of `62`
  - `Q1-00D7-5IQF` stuck canceled allocations decrease from `6`
  - `Q1-00D7-5IQF` missing-token demand decreases from `5`
  - `orders_missing_tokens.csv` only drops where a real token was truly freed and reallocated
  - `out/token_cancel_release_events.csv` shows the released rows
- runtime proof target when coding starts:
  - document the safe B-owned proof window first with:
    - `python scripts/one_off/P002_plan_forced_proof_window.py --flow b --format json`
  - if the proof window is safe, use a boundary-safe B-owned proof run rather than an ad-hoc mid-cycle check
  - required runtime proof:
    - B finalize marker for the proof run
    - refreshed B checklist showing `allocated_tokens_on_canceled_orders = ok / 0`
    - refreshed shortage evidence showing any remaining gaps are true shortage, not trapped canceled allocations
- success definition for this project:
  - canceled orders no longer trap token allocations
  - released tokens become available to current demand in the same B allocation run
  - shortage counts reduce where cancellation release was the real cause
  - any remaining shortages are truthful and attributable to actual receipt or supply gaps

### Phase 20 implementation snapshot - canceled-order token release (`2026-04-22T13:30:00Z`)
- code fix applied:
  - `scripts/flows/B/B007_allocate_tokens_live.py`
    - added explicit canceled-order allocation release pass before normal allocation
    - release source uses explicit `orders_all.order_status = Canceled`
    - release excludes keys still present in current positive sold demand
    - released rows are removed from `token_allocations_live.csv`
    - released tokens are set back to `available` in `token_ledger_live.csv`
    - added local evidence output `out/token_cancel_release_events.csv`
    - no Google Sheets write path added for release evidence
  - `scripts/flows/A/A015_build_system_health_check.py`
    - added check `token_allocated_on_canceled_orders`
    - added detail output `out/health_allocated_tokens_on_canceled_orders.csv`
    - status rule is `fail` when canceled allocated units remain > `0`
    - added schema check `b_schema_allocated_tokens_on_canceled_orders`
  - tests updated:
    - `tests/test_b007_allocate_tokens_live.py`
    - `tests/test_a015_health_check_runtime.py`
- isolated verification:
  - `python -m py_compile scripts/flows/B/B007_allocate_tokens_live.py scripts/flows/A/A015_build_system_health_check.py tests/test_b007_allocate_tokens_live.py tests/test_a015_health_check_runtime.py` -> pass
  - `pytest tests/test_b007_allocate_tokens_live.py -q` -> pass (`6`)
  - `pytest tests/test_a015_health_check_runtime.py -q -k "token_allocated_on_canceled_orders_stats or order_master_placeholder_stats"` -> pass (`4`)
- live-loop verification:
  - B owner was active, so no overlapping manual B scripts were run
  - forced-proof planner evidence captured:
    - `python scripts/one_off/P002_plan_forced_proof_window.py --flow b --format json`
    - result: boundary-safe path required, active owner present
  - post-change B-owned finalize observed:
    - `2026-04-22T13:28:57Z ... B_FINALIZE ran rc=0 wrote_health=true reason=cycle_complete`
  - post-finalize checklist evidence:
    - `token_allocated_on_canceled_orders = ok / 0`
    - `token_shortages_by_sku = fail / 4`
    - `order_master_placeholder_cogs_rows = warn / 3`
  - post-finalize detail evidence:
    - `out/health_allocated_tokens_on_canceled_orders.csv` exists with header and `0` rows
    - `out/token_cancel_release_events.csv` exists with header and `0` rows in this observed cycle
  - direct state cross-check:
    - stuck canceled allocations now `0` rows / `0` units
- status:
  - canceled-allocation trap fix is implemented and live-loop proven in B-owned runtime
  - remaining blocker is separate and unchanged in class:
    - true token shortage queue still present (`token_shortages_by_sku`)

### Phase 21 planning addendum - close-out plan for remaining token shortages (`2026-04-22T15:05:00Z`)
- purpose:
  - separate the last `4` shortage SKUs into fixable runtime bug, baseline-start ambiguity, and true shortage
  - avoid inventing tokens for legacy gaps while still closing the real process bug now
- current fail set from `out/token_shortages_by_sku.csv`:
  - `0R-GRRH-W0Z9` -> missing `1`
  - `MW-9K5M-VKW8` -> missing `2`
  - `R4-0AXZ-ZZ9D` -> missing `1`
  - `SE-UITZ-7CPY` -> missing `1`
- investigation findings:
  - `MW-9K5M-VKW8`
    - not a clean baseline-count issue
    - open order `S02-0884376-6363056` has `Quantity Ordered = 3` but only one token allocation record after repeated stock-adjustment retries
    - `out/stock_adjustment_token_events.csv` shows repeated `insufficient_returned_pending` partial retries for event `20016144516474`, then only a partial reapply succeeds
    - root-cause class: runtime adjustment and reapply bug
  - `0R-GRRH-W0Z9`
    - all current tokens are `live_stock_backdate`
    - purchase history exists: `12` delivered and `12` sent to FBA on `2025-05-07`, plus later `60` ordered on `2026-04-02` with no receipt yet
    - shortage is `1` unit against a baseline-start pool of `6`
    - root-cause class: legacy baseline-start ambiguity candidate, not proven runtime bug
  - `R4-0AXZ-ZZ9D`
    - purchase history exists: `15` delivered and `15` sent to FBA
    - `out/token_backdate_summary.csv` explicitly shows `required_qty = 16`, `built_qty = 15`, `note = partial`
    - all current tokens are `live_stock_backdate`
    - root-cause class: legacy baseline-start short by `1`, not a current allocator bug
  - `SE-UITZ-7CPY`
    - purchase history exists: `10` delivered and `10` sent to FBA
    - token ledger holds `10` stock-receipt tokens and all are allocated
    - one further sold order remains on placeholder only
    - root-cause class: true live shortage
- execution plan:
  - phase `21A` - fix the remaining runtime bug
    - target file: `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`
    - objective:
      - stop repeated partial reapply drift when positive sellable adjustments arrive and returned-pending coverage is short
      - ensure multi-unit demand can recover correctly instead of restoring only one token and leaving the rest stranded
    - proof target:
      - `MW-9K5M-VKW8` drops from missing `2` to `0`
      - order `S02-0884376-6363056` reaches full token coverage
      - no new shortage inflation appears on unrelated SKUs
  - phase `21B` - classify legacy baseline-start gaps without masking them
    - target files:
      - `scripts/flows/B/B007_allocate_tokens_live.py`
      - `scripts/flows/A/A015_build_system_health_check.py`
    - objective:
      - add explicit classification so a fail can say whether it is:
        - `runtime_drift`
        - `legacy_baseline_gap`
        - `true_shortage`
      - do not auto-create tokens for `0R-GRRH-W0Z9` or `R4-0AXZ-ZZ9D`
    - proof target:
      - both SKUs stay visible but are no longer mixed with runtime bugs
      - shortage reporting remains `1 line per SKU per run`
  - phase `21C` - keep the honest live short separate
    - `SE-UITZ-7CPY` remains a real shortage until new stock is receipted or an approved baseline correction exists
    - no code should try to hide or auto-fill this with fake tokens
- operator decision still required after phase `21A`:
  - choose policy for legacy baseline-start gaps:
    - approved one-time baseline correction with proof bundle
    - explicit exception-list monitoring
    - leave as permanent truthful shortages
- non-goals:
  - no Google Sheets write
  - no local DB alignment
  - no token fabrication for old stock without approved baseline evidence
  - no downstream masking of profit or pass/fail outputs

### Phase 22 planning addendum - duplicate stock-receipt token creation for `L5-PF3B-WHU4` (`2026-04-22T15:20:00Z`)
- purpose:
  - investigate and remove duplicate receipt-token creation caused by repeated application of the same 2-unit purchase
  - add an idempotent guard so the same purchase cannot mint tokens again on later runs
- proof baseline:
  - purchase-sheet row exists in `out/orders_sheet_orders.csv`:
    - `seller_sku = L5-PF3B-WHU4`
    - `order_date = 12/01/26`
    - `ordered = delivered = sent_to_fba = 2`
    - `order_key = 8ff292fa-c591-4691-ac11-fcf6ab01abbe`
  - token ledger currently shows eight separate receipt batch ids for that same 2-unit purchase:
    - `SR-20260112-001`
    - `SR-20260112-002`
    - `SR-20260112-003`
    - `SR-20260112-004`
    - `SR-20260112-005`
    - `SR-20260112-006`
    - `SR-20260112-007`
    - `SR-20260112-008`
  - each batch minted `2` tokens
  - current state therefore is:
    - expected receipt tokens from this purchase: `2`
    - actual receipt tokens from this purchase: `16`
    - excess duplicate receipt tokens: `14`
    - current usage split:
      - allocated duplicate receipt tokens: `4`
      - still-available duplicate receipt tokens: `12`
- root-cause theory:
  - the stock-receipt intake path is not idempotent for this purchase row
  - the same underlying purchase was accepted multiple times as new receipt work and generated fresh batch ids instead of being recognized as already applied
  - the failure is upstream in receipt-intake dedupe and cleanup, not in downstream reporting
- execution plan:
  - phase `22A` - trace duplicate creation path
    - target files to inspect when coding starts:
      - `scripts/tools/process_stock_receipts_sheet.py`
      - any helper used to derive `batch_id` / dedupe keys for stock receipts
      - any file that persists receipt-intake state before token creation
    - determine exactly why the same `order_key` and qty were allowed to apply eight times
  - phase `22B` - add hard idempotency guard
    - required behavior:
      - once a receipt row for a unique purchase key is applied, reruns must not create a new batch for the same effective receipt unless the quantity truly increased
      - dedupe key should use stable purchase identity, not just fresh run context
    - candidate identity fields:
      - `order_key`
      - `seller_sku`
      - receipt qty
      - receipt-ready state
  - phase `22C` - safe cleanup of bad duplicate tokens
    - remove only the excess duplicate receipt tokens tied to this bug
    - cleanup must preserve any tokens already legitimately consumed by real sold demand
    - if allocated duplicate tokens are unwound, reallocation must happen from the correct surviving receipt/baseline pool in the same controlled proof run
    - write a dedicated evidence file, for example:
      - `out/token_duplicate_receipt_cleanup_events.csv`
  - phase `22D` - health guard
    - add a B-scoped health check for duplicate receipt minting, for example:
      - `duplicate_receipt_tokens_detected`
    - the check should fail when the same receipt identity has more minted tokens than its applied qty
- required proof when coding starts:
  - duplicate receipt minting for `order_key = 8ff292fa-c591-4691-ac11-fcf6ab01abbe` reduces from `16` to `2`
  - excess available duplicate tokens reduce from `12` to `0`
  - any allocated duplicate tokens are reconciled safely and no sold order loses rightful coverage
  - rerunning the receipt-intake step does not recreate the duplicate tokens
- non-goals:
  - no Google Sheets edits
  - no masking by adjusting downstream profit outputs only
  - no broad token reset across unrelated SKUs

### Phase 21A implementation snapshot - adjustment fallback and retry suppression (`2026-04-22T16:05:00Z`)
- code fix applied:
  - `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`
    - added fallback token creation for positive adjustment/receipt events when `returned_pending` coverage is short
    - fallback cost basis now uses latest valid token cost for the same SKU
    - fallback token source is explicit: `stock_adjustment_fallback`
    - repeated duplicate base event ids in one run are now suppressed
    - applied event ids are tracked in-run to avoid duplicate processing inside the same invocation
- isolated verification:
  - `python -m py_compile scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py` -> pass
  - `PYTHONPATH=. pytest tests/test_b009_apply_stock_adjustments_to_tokens.py -q` -> pass
- expected runtime impact:
  - prevents endless `insufficient_returned_pending` retries for cases like `MW-9K5M-VKW8` where the event is a real positive stock adjustment but no return-pending token exists

### Phase 22 implementation snapshot - receipt idempotency and duplicate cleanup tooling (`2026-04-22T16:05:00Z`)
- code fix applied:
  - `scripts/tools/process_stock_receipts_sheet.py`
    - added `(source_order_key, seller_sku)` token summary index from existing ledger rows
    - intake rows now idempotently short-circuit when existing receipt tokens for the key already meet/exceed row qty
    - repeated rows for the same purchase key no longer mint fresh tokens on re-run
    - partial-gap behavior now only creates delta qty when existing key coverage is below target qty
  - `scripts/one_off/T029_cleanup_duplicate_receipt_tokens.py`
    - added one-off safe cleanup tool for duplicate receipt minting
    - supports dry-run and apply modes
    - removes excess duplicate tokens for one `order_key` (and optional SKU)
    - removes matching allocation rows for removed token ids
    - writes evidence log to `out/token_duplicate_receipt_cleanup_events.csv`
- isolated verification:
  - `python -m py_compile scripts/tools/process_stock_receipts_sheet.py scripts/one_off/T029_cleanup_duplicate_receipt_tokens.py` -> pass
  - `PYTHONPATH=. pytest tests/test_process_stock_receipts_sheet.py tests/test_t029_cleanup_duplicate_receipt_tokens.py -q` -> pass
- dry-run proof for target duplicate:
  - command:
    - `python scripts/one_off/T029_cleanup_duplicate_receipt_tokens.py --order-key 8ff292fa-c591-4691-ac11-fcf6ab01abbe --expected-qty 2 --seller-sku L5-PF3B-WHU4`
  - result:
    - `actual_qty=16`
    - `excess_qty=14`
    - `remove_qty=14`

### Phase 22 close-out sequence to unblock price list scanner (`2026-04-22T16:05:00Z`)
- objective:
  - finish the duplicate cleanup and reallocation in one bounded maintenance window, then confirm B health state for pricing work
- boundary-safe run sequence:
  - `1.` obtain B maintenance boundary (no overlapping owner writes)
  - `2.` run duplicate cleanup apply:
    - `python scripts/one_off/T029_cleanup_duplicate_receipt_tokens.py --order-key 8ff292fa-c591-4691-ac11-fcf6ab01abbe --expected-qty 2 --seller-sku L5-PF3B-WHU4 --apply`
  - `3.` run B token rebuild chain:
    - `B007_allocate_tokens_live.py`
    - `B025_build_token_cogs_ledger.py`
    - `B004_build_order_master.py`
  - `4.` confirm post-fix evidence:
    - `L5-PF3B-WHU4` receipt tokens for that order key reduced from `16` to `2`
    - `token_shortages_by_sku` contains only true unresolved shortages
    - no new `l1_keys_missing_in_master`
  - `5.` release maintenance and confirm owner resumes
- done threshold for scanner handoff:
  - no known token inflation from duplicate receipts
  - shortage queue only contains truthful supply gaps
  - placeholder rows are stable and explicitly visible
  - B checklist has no new regression FAIL beyond known true shortages

### Phase 22 runtime execution snapshot - duplicate receipt cleanup applied (`2026-04-22T16:15:00Z`)
- maintenance safety:
  - requested maintenance marker: `out/locks/maintenance.requested`
  - B log confirmed boundary handoff:
    - `maintenance ready (after cycle end); current cycle finished`
    - `maintenance pause (after cycle end)`
  - maintenance released after work:
    - removed `maintenance.requested`
    - B log confirmed `maintenance clear (after cycle end); resuming cycle`
- cleanup action run:
  - `python scripts/one_off/T029_cleanup_duplicate_receipt_tokens.py --order-key 8ff292fa-c591-4691-ac11-fcf6ab01abbe --expected-qty 2 --seller-sku L5-PF3B-WHU4 --apply`
  - result:
    - `actual_qty=16`
    - `remove_qty=14`
    - `status=applied`
- bounded rebuild run during maintenance:
  - `B007_allocate_tokens_live.py` (local-only mode for this manual run)
  - `B025_build_token_cogs_ledger.py`
  - `B004_build_order_master.py` with local write only (`ORDER_MASTER_SKIP_SHEETS=1`)
- post-apply proof:
  - order key `8ff292fa-c591-4691-ac11-fcf6ab01abbe` in `token_ledger_live.csv` now has exactly `2` receipt tokens
  - surviving tokens:
    - `SR-20260112-001-0001`
    - `SR-20260112-001-0002`
  - status split for that key:
    - `allocated=2`
    - `available=0`
  - duplicate inflation for this key is removed
- current known residuals after cleanup:
  - `token_shortages_by_sku` remains `4` SKUs (`0R-GRRH-W0Z9`, `MW-9K5M-VKW8`, `R4-0AXZ-ZZ9D`, `SE-UITZ-7CPY`)
  - `MW-9K5M-VKW8` still short `2`; runtime fix code is in `B009` but flow input `out/stock_events_raw.csv` was not present during this maintenance window, so runtime reproof for that path is pending
