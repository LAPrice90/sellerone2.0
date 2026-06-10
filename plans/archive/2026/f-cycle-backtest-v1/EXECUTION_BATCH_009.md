# Execution Batch 009

## Purpose
- Clean up the BBP monthly sales demand pipeline so F uses the trusted past-month sales signal from `estSalesMonthlyChart` and stops inflating replay demand with fallback chosen units or future chart bars.
- Produce a full sampled-ASIN audit list so the user can check the scraped chart history and replay demand basis across the whole review pack, not just one ASIN.

## Why this batch exists
- Batch 008 review exposed a root-cause issue:
  - BBP chart data is already being scraped from `//*[@id="estSalesMonthlyChart"]`
  - the chart can show future-looking bars that must not feed backtest demand
  - the current month can be partial or unstable and must not be treated as a trusted completed month
  - `bbp_monthly_units_chosen` is currently overriding the lower chart current value in replay demand selection
  - this can materially overstate `estimated_listing_units`, `estimated_units_ours`, and `estimated_profit_gbp`
- Example evidence from current outputs:
  - scrape evidence can show `bbp_monthly_sales_current = 10`
  - the same row can still carry `bbp_monthly_units_chosen = 50`
  - replay then uses the larger value as base demand input
- Operator risk:
  - a one-ASIN fix is not enough proof
  - the sampled ASIN pack needs a full audit list so broader extraction or basis-selection errors are visible in one place

## Scope guardrails
- Only do:
  - extract and persist BBP monthly sales chart history more truthfully
  - separate past completed months from current partial month and future months
  - define one trusted demand basis for replay and backtest
  - keep turnover-gate helper logic separate from replay demand logic
  - add health and proof so future/predicted bars cannot silently leak into replay
  - build a checkable sampled-ASIN audit list from the reviewed pack so the operator can compare the scraper output with BBP
  - add a durable debug path so Codex can inspect scraper-produced chart evidence without relying on ad-hoc visual guessing
- Do not change:
  - Google Sheets or local DB state
  - H runtime logic
  - raw evidence files by hand
  - product-level results by manual CSV edits instead of rerun
- Do not add:
  - a live-desktop dependency as the source of truth for demand
  - a system where Codex must manually read the browser every time to verify sales data
  - future-month demand as an input to pass/fail or replay profit

## Files allowed to change
- `plans/active/f-cycle-backtest-v1/EXECUTION_BATCH_009.md`
- `plans/active/f-cycle-backtest-v1/PLAN.md`
- `plans/active/f-cycle-backtest-v1/PLAN_STATUS.md`
- `plans/active/f-cycle-backtest-v1/RUNBOOK.md`
- `plans/active/f-cycle-backtest-v1/DATA_CONTRACTS.md`
- `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f004_build_bbp_sales_sample_audit.py`
- `tests/test_f071_build_backtest_input_view.py`
- `tests/test_f072_run_backtest_replay.py`
- `tests/test_f074_build_backtest_health.py`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `plans/active/f-cycle-backtest-v1/PLAN.md`
- `plans/active/f-cycle-backtest-v1/EXECUTION_BATCH_008.md`
- `plans/active/f-cycle-backtest-v1/USER_ALIGNMENT_NOTES.md`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv`
- `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`

## Design rules to lock before coding
- Trusted demand source for replay:
  - use last completed month from BBP sales history chart
  - do not use future months
  - do not use the current partial month as the primary replay basis
- Current partial month:
  - keep as observability-only unless a later rule explicitly approves it
- Turnover gate helper:
  - may still use a guarded helper value if needed
  - must not silently become replay demand basis
- Visual verification:
  - the scraper should persist structured chart evidence so Codex can inspect the extracted values from files
  - direct browser viewing can help debug, but it must not be the only proof path
- Sample audit:
  - the Batch 008 sample ASIN set must be exportable as one review list
  - each sample row must show the scraped chart basis and whether replay matched the trusted month rule
  - the operator should be able to open the ASIN link and compare it against the exported row without extra spreadsheet work

## Tasks
### Task 1
- Goal:
  - define a clean BBP monthly sales chart contract that separates past, current, and future bars
- Files:
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - `scripts/flows/F/_schemas.py`
  - `scripts/flows/F/_source_contracts.py`
  - `plans/active/f-cycle-backtest-v1/DATA_CONTRACTS.md`
- Notes:
  - persist chart month labels and values in a structured way
  - record which month is current partial
  - record how many future bars were present and ignored
  - add explicit fields for:
    - last completed month label
    - last completed month units
    - current month label
    - current month units
    - future month count ignored
    - demand basis selected for replay

### Task 2
- Goal:
  - stop replay demand from prioritising `bbp_monthly_units_chosen` over trusted chart history
- Files:
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `scripts/flows/F/F072_run_backtest_replay.py`
  - related tests in `tests/`
- Notes:
  - introduce an explicit replay-demand field based on the last completed month
  - keep turnover-gate helper fields available, but separate
  - if trusted chart history is missing, fallback order must be explicit and health-visible

### Task 3
- Goal:
  - make the first-check turnover logic truthful without polluting replay demand
- Files:
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - related tests in `tests/`
- Notes:
  - turnover summary can still show:
    - current month sales
    - recent average
    - guarded helper/chosen units
  - but each field must state what it means
  - operator-facing/debug-facing text should make it obvious which value is used for replay

### Task 4
- Goal:
  - add health checks that catch demand-basis drift and future-bar leakage
- Files:
  - `scripts/flows/F/F074_build_backtest_health.py`
  - related tests in `tests/`
- Notes:
  - add checks for:
    - future months ignored flag present when needed
    - replay demand basis not using future months
    - replay demand basis not silently using `bbp_monthly_units_chosen` when trusted past-month data exists
    - schema presence for the new demand-basis fields

### Task 5
- Goal:
  - add a durable debug workflow so Codex can verify chart extraction from files rather than memory or screenshots alone
- Files:
  - `plans/active/f-cycle-backtest-v1/RUNBOOK.md`
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - any code files above if a debug field/output is needed
- Notes:
  - preferred workflow:
    - scraper runs on the PC as normal
    - scraper writes structured monthly chart fields
    - Codex reads those fields and compares them with user screenshots only when needed
  - avoid making Codex depend on live browser control for normal operation

### Task 6
- Goal:
  - build a sampled-ASIN audit export for the current review pack so the user can check the whole set for chart extraction or demand-basis errors
- Files:
  - `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
  - `tests/test_f004_build_bbp_sales_sample_audit.py`
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - `plans/active/f-cycle-backtest-v1/RUNBOOK.md`
- Notes:
  - use the Batch 008 sample pack as the audit source list
  - each audit row should include at minimum:
    - `seller_sku`
    - `asin`
    - Amazon link
    - chart month labels and units
    - last completed month label and units
    - current month label and units
    - future month count ignored
    - `bbp_monthly_units_chosen`
    - replay demand basis selected
    - mismatch flag / mismatch reason
  - output should be easy for the operator to review in CSV form
  - the audit builder must stay one-off and must not run inside daily loops

## Tests
- Command:

```powershell
pytest tests/test_f004_build_bbp_sales_sample_audit.py tests/test_f061_run_legacy_first_checks_local.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f074_build_backtest_health.py
```

- Expected result:
  - scoped demand-cleanup pack passes

## Proof required
- Field proof:
  - at least one known ASIN proves that:
    - chart history fields were extracted with month labels
    - future bars were ignored
    - current partial month was not used as the replay basis
    - last completed month became the replay demand input
- Replay proof:
  - at least one controlled fixture proves replay demand drops when current chart value is `10` but helper chosen units are higher
  - at least one real-row comparison shows before/after `estimated_listing_units`, `estimated_units_ours`, and `estimated_profit_gbp`
- Audit proof:
  - one sampled-ASIN audit export exists for the full review pack
  - the export includes every sampled ASIN, not just the one currently being discussed
  - at least one known-bad row shows a mismatch flag before the fix and clears after the fix
  - the operator can use the exported Amazon links to compare BBP against the scraped values row by row
- Health proof:
  - new demand-basis health row is present and current
  - any future-bar or helper-value misuse is surfaced truthfully
- Output files:
  - updated `feeder_legacy_scrape_evidence_live.csv` schema evidence
  - updated `feeder_backtest_input_view_live.csv`
  - updated `feeder_backtest_replay_daily_live.csv`
  - updated `feeder_backtest_summary_live.csv`
  - updated `feeder_backtest_health.csv`
  - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
- Notes:
  - keep the explanation plain-English and root-cause first
  - do not call this solved unless the replay demand basis matches the agreed trusted month rule

## Completion checklist
- [ ] Trusted month rule locked
- [ ] Future bars excluded from replay demand
- [ ] Current partial month is observability-only
- [ ] Replay no longer uses `bbp_monthly_units_chosen` when trusted past-month data exists
- [ ] Health check added for demand basis / future leakage
- [ ] Sampled-ASIN audit export built for the full review pack
- [ ] Scoped tests passed
- [ ] Before/after proof captured
