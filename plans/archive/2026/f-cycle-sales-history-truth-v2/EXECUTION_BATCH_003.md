# Execution Batch 003

## Purpose
- Harden the price-qualified demand engine on top of the improved Phase 2B coverage state.
- Make qualification logic explicit, auditable, and source-aligned before any seasonality or recent-performance work starts.

## Why this batch exists
- Batch 002 improved evidence coverage enough to move forward:
  - completed-month rows: `2241 -> 2264`
  - replay-basis rows: `2354 -> 2379`
  - missing full-chart rows with ASIN: `2244 -> 2219`
- Batch 002 also removed the immediate manual-review blocker:
  - `f_backtest_manual_review_share = ok` (`0.086477`)
- The next root cause is no longer missing demand truth for READY rows.
- The next root cause is that price qualification is still too blunt and not explicit enough to trust for broader model expansion.
- Current code already splits:
  - raw observed demand
  - price-qualified demand
- But the qualification engine still needs a tighter contract before later batches add:
  - seasonality
  - recent-vs-baseline classification
  - confidence

## Scope guardrails
- Only do:
  - harden the F-owned price-qualified demand path
  - make qualification components explicit in input, replay, summary, and validation proof where needed
  - add or tighten F-scoped tests and health checks
  - run a bounded proof rebuild on a controlled proof window
- Do not change:
  - Google Sheets
  - local DB state
  - H runtime
  - scrape owner path
  - seasonality business rules
  - recent-performance classifier
  - confidence model
- Do not add:
  - downstream masking to make weak qualification look stronger
  - manual CSV edits as truth
  - broad rescrape work as a substitute for qualification hardening

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_003.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/HOMETIME_PROMPT.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- related tests under `tests/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DECISION_MODEL.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_002_REPLY.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/live/feeder_backtest_health.csv`
- `out/analysis_reports/f_sales_history_validation_latest.csv`
- `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`

## Phase 2B gate facts to carry forward
- Coverage is improved but still incomplete:
  - scrape evidence rows: `4598`
  - completed-month coverage rows: `2264`
  - missing full-chart rows with ASIN: `2219`
- F proof is strong enough to harden qualification without reopening scrape routing first:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_manual_review_share = ok`
  - sampled audit mismatch rows: `2`
- One warning remains visible:
  - `f_backtest_health_staleness = warn`
  - current note: `stale_sources:input_view|replay_daily|summary`
- This batch must use a controlled proof window so qualification proof is not blurred by moving live inputs.

## Tasks

### Task 1
- Goal:
  - make the price-qualification components explicit at the earliest owner stage
- Notes:
  - the root-cause fix belongs in `F071`, not by adjusting summary outputs later
  - add explicit component fields or equivalent contract truth for:
    - market gate
    - Amazon pressure factor
    - buy-box coverage factor
    - maturity factor
    - final qualification factor
    - zero or block reason
  - keep `raw` and `qualified` demand as separate truths

### Task 2
- Goal:
  - make replay and summary consume qualification truth consistently
- Notes:
  - READY rows must not silently fall back to replay-derived expected units or profit when explicit qualified input exists
  - reason codes should make the source path clear:
    - qualified input source
    - replay fallback when truly needed
    - qualification-limited states
  - keep pass/fail behavior rooted in qualified demand, not raw observed demand

### Task 3
- Goal:
  - extend F-scoped health and validation so the qualification engine can be proven, not assumed
- Notes:
  - `F074` should fail or warn when component truth is missing or inconsistent on READY rows
  - `F005` should expose raw vs qualified delta and qualification reasons clearly enough for operator review
  - do not create a health check that belongs to another flow

### Task 4
- Goal:
  - run a bounded Phase 3 proof rebuild on a controlled proof window
- Notes:
  - current live scrape evidence keeps moving, which can make `f_backtest_health_staleness` warn even when the code path is correct
  - use one truthful proof boundary:
    - either a frozen unchanged-input window
    - or a safe owner pause or boundary if needed to avoid stale-proof ambiguity
  - do not claim completion from mixed-time outputs

### Task 5
- Goal:
  - leave the overnight owner path in a truthful state after proof
- Notes:
  - if ownership was paused for proof, resume it and confirm:
    - full queue target remains correct
    - loop owner is active on `stocklist_supplier`

## Tests
- Minimum command:

```powershell
pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py
```

- Plus:
  - tests for any new qualification component columns
  - tests for any new qualification-source alignment logic
  - `python -m py_compile` for every changed F file and changed test file

## Proof required
- Qualification component proof:
  - fixture coverage shows at least:
    - market below break-even -> qualified demand = `0` with explicit reason
    - Amazon-heavy or dominant case -> explicit factor reduction and reason
    - low buy-box coverage case -> explicit factor reduction and reason
    - limited maturity case -> explicit factor reduction and reason
- Source alignment proof:
  - READY summary rows use qualified input source when that truth exists
  - replay and summary source tags match the actual calculation path
  - no READY row has blank qualification reason or blank qualification components
- Health proof:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - controlled Phase 3 proof should aim for `f_backtest_health_staleness = ok`
  - if that is impossible because live owner movement cannot be held safely, park with the exact blocker and exact proof boundary still needed
- Validation proof:
  - `f_sales_history_validation_latest.csv` exposes raw vs qualified delta and reason path on sampled rows
  - sampled mismatch count must not worsen without an explicit root-cause explanation
- Output files:
  - updated `feeder_backtest_input_view_live.csv`
  - updated `feeder_backtest_replay_daily_live.csv`
  - updated `feeder_backtest_summary_live.csv`
  - updated `feeder_backtest_health.csv`
  - updated `f_sales_history_validation_latest.csv`

## Completion checklist
- [x] Qualification component contract written into the F path
- [x] Replay and summary source alignment updated
- [x] F health and validation proof extended
- [x] Scoped pytest and `py_compile` pass
- [x] Controlled Phase 3 proof rebuild completed
- [x] Output and health proof captured
- [x] Overnight owner state confirmed after proof

## Execution evidence (`2026-04-19`)
- Isolated verification:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - result: `43 passed`
  - `python -m py_compile` ran for all changed F scripts and changed tests
- Controlled proof boundary:
  - live owner paused before rebuild (`run_F_supplier_full_legacy_scan.bat stocklist_supplier` + loop child stopped)
  - `feeder_legacy_scrape_evidence_live.csv` hash held unchanged across proof window:
    - `E38EE98FC4EA278CF41F4CCEAED7C6C737FA8D1DFB2ACA2CB20CCD429EA3E481`
- Rebuild outputs:
  - `F070` active policy rows: `1`
  - `F071` rows: `2364` (`ready=2158`, `manual_review=206`)
  - `F072` rows: `772366`
  - `F073` rows: `2364` (`ready=2158`, `manual_review=206`, `decision_fail=1890`, `decision_pass=268`)
  - `F074` rows: `17` (`ok=17`, `warn=0`, `fail=0`)
  - `F004` rows: `18`, mismatch rows: `2`
  - `F005` rows: `28764`, trusted rows: `2270`, qualified-delta rows: `28540`
- Health proof:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - `f_backtest_qualification_source_alignment = ok`
  - `f_backtest_health_staleness = ok`
- Source alignment proof:
  - READY summary rows: `2158`
  - READY `expected_units_source=input_qualified`: `2158`
  - READY `expected_profit_source=input_qualified`: `2158`
  - READY rows with blank qualification components: `0`
- Owner-state proof after rebuild:
  - full queue canonical rows for `stocklist_supplier`: `42663`
  - loop owner restored on `stocklist_supplier`:
    - `python ... F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 5 --loop`
