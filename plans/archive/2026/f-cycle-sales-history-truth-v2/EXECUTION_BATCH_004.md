# Execution Batch 004

## Purpose
- Add explicit seasonality, stability, and recent-performance classifier truth on top of the hardened Batch 003 qualification contract.
- Keep all new classifier outputs auditable and source-aligned before any confidence-engine work starts.

## Why this batch exists
- Batch 003 closed the qualification hardening gate:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - `f_backtest_qualification_source_alignment = ok`
  - `f_backtest_health_staleness = ok` in the controlled proof window
- Next root cause is no longer qualification ambiguity.
- Next root cause is missing explicit business classification for:
  - seasonality
  - stability/drift
  - recent vs baseline state
- Batch 004 must implement those states before Batch 005 decision-confidence expansion.

## Scope guardrails
- Only do:
  - implement seasonality, stability, and recent-performance classifier outputs in F-owned path
  - carry classifier truth through input, replay, summary, and health as needed
  - add/extend F-scoped tests and validation for classifier path
  - run bounded controlled proof rebuild
- Do not change:
  - Google Sheets
  - local DB state
  - H runtime
  - scrape owner path
  - confidence model logic
  - post-purchase learning loop
- Do not add:
  - downstream masking that hides weak classifier evidence
  - ad-hoc manual CSV truth patches
  - broad scrape recovery as substitute for classifier implementation
  - a new broad scrape loop as a prerequisite for classifier work

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_004.md`
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
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_003_REPLY.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/live/feeder_backtest_health.csv`
- `out/analysis_reports/f_sales_history_validation_latest.csv`

## Batch 003 gate facts to carry forward
- Input rows: `2364` (`ready=2158`, `manual_review=206`)
- Replay rows: `772366`
- Summary rows: `2364` (`ready=2158`, `manual_review=206`)
- Health rows: `17` (`ok=17`)
- Validation rows: `28764`, trusted rows: `2270`, qualified-delta rows: `28540`
- Source alignment truth:
  - READY `expected_units_source=input_qualified`: `2158`
  - READY `expected_profit_source=input_qualified`: `2158`

## Weekend evidence gate on 2026-04-20
- Broad scrape is no longer the blocker for Batch 004.
- Frozen working evidence now available:
  - scrape-evidence rows: `4580`
  - unique ASINs seen: `4556`
  - latest successful ASIN captures: `2342`
  - latest-success observed months:
    - `6+`: `1918`
    - `9+`: `1528`
    - `12+`: `1012`
- Fresh targeted retry subset exists for later cleanup, not as a Batch 004 prerequisite:
  - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
  - selected rows: `2207`
- Fresh rebuild on frozen evidence:
  - `F071`: `2358` (`ready=2149`, `manual_review=209`)
  - `F072`: `769366`
  - `F073`: `2358` (`fail=1883`, `manual_review=209`, `pass=266`)
  - `F074`: `17` (`ok=17`)
  - `F004`: rows `18`, mismatch rows `2`
  - `F005`: rows `28668`, trusted rows `2262`, qualified-delta rows `28418`

## Tasks

### Task 1
- Goal:
  - make seasonality state explicit and maturity-aware
- Notes:
  - seasonality claims must require sufficient completed-month maturity
  - classifier must distinguish:
    - `seasonal_confirmed`
    - `possible_seasonal`
    - `spiky_not_proven_seasonal`
    - `insufficient_history`
  - reason tags must explain why a state was chosen

### Task 2
- Goal:
  - make stability/drift state explicit
- Notes:
  - add plain states rooted in qualified demand history:
    - `stable`
    - `drifting_down`
    - `drifting_up`
    - `spiky`
    - `too_new`
  - avoid conflating stability with seasonality

### Task 3
- Goal:
  - add recent vs baseline state from qualified demand
- Notes:
  - compare last completed and trailing-3 against baseline context
  - explicit outputs:
    - `underperforming`
    - `stable`
    - `overperforming`
    - `insufficient_history`
  - include reason tags where possible:
    - `seasonal_window`
    - `amazon_below_floor`
    - `market_below_floor`
    - `recent_price_compression`
    - `high_volatility`
    - `insufficient_history`

### Task 4
- Goal:
  - propagate classifier truth through replay and summary without hidden fallback
- Notes:
  - summary reason path must carry classifier states/tags explicitly
  - READY rows must not have blank classifier state fields
  - no classifier state should silently default to a "good" label when required evidence is missing

### Task 5
- Goal:
  - extend F health and validation for classifier proof
- Notes:
  - add or update F074 checks for seasonality/stability/recent integrity in F scope
  - extend F005 validation output so sampled rows show classifier state + reason path
  - do not add checks owned by other flows

### Task 6
- Goal:
  - run bounded controlled proof rebuild and leave owner path truthful
- Notes:
  - use one truthful proof boundary to avoid mixed-time stale ambiguity
  - if ownership is paused, resume and confirm owner loop on `stocklist_supplier`

## Tests
- Minimum command:

```powershell
pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py
```

- Plus:
  - tests for any new seasonality/stability/recent classifier fields and reason tags
  - tests for summary classifier-source alignment on READY rows
  - `python -m py_compile` for every changed F file and changed test file

## Proof required
- Classifier component proof:
  - fixture coverage shows at least:
    - seasonality held as insufficient when maturity is too low
    - seasonal/spiky states separated by explicit rule
    - drift up/down states map to qualified-demand trend
    - recent vs baseline states map to explicit thresholds and reason tags
- Source alignment proof:
  - READY summary rows include non-blank seasonality/stability/recent states
  - READY classifier reason path is explicit and non-blank where required
  - no READY row silently falls back to a "good" classifier state
- Health proof:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - classifier integrity checks = `ok`
  - controlled proof should target `f_backtest_health_staleness = ok`
- Validation proof:
  - `f_sales_history_validation_latest.csv` exposes classifier states and reason path with raw vs qualified context
  - sampled mismatch count must not worsen without explicit root-cause explanation

## Completion checklist
- [x] Seasonality classifier contract written into F path
- [x] Stability/drift classifier contract written into F path
- [x] Recent vs baseline classifier contract written into F path
- [x] Replay/summary classifier source alignment updated
- [x] F health and validation classifier proof extended
- [x] Scoped pytest and `py_compile` pass
- [x] Controlled Phase 4 proof rebuild completed
- [x] Output and health proof captured
- [ ] Overnight owner state confirmed after proof

## Execution proof (2026-04-20)
- Isolated verification:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - result: `47 passed`
  - `python -m py_compile` passed for changed F and test files
- Controlled proof boundary:
  - `F071` (`2026-04-20T13:10:00Z`): rows `2358` (`ready=2149`, `manual_review=209`)
  - `F072` (`2026-04-20T13:11:00Z`): rows `769366`
  - `F073` (`2026-04-20T13:12:00Z`): rows `2358` (`ready=2149`, `manual_review=209`)
  - `F074` closeout (`2026-04-20T13:15:00Z`): rows `20` (`ok=20`)
  - `F005` (`2026-04-20T13:14:00Z`): rows `28668`, trusted rows `2262`, qualified-delta rows `28418`
- Health proof at closeout:
  - `f_backtest_health_staleness = ok`
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - `f_backtest_qualification_source_alignment = ok`
  - `f_backtest_seasonality_classifier_integrity = ok`
  - `f_backtest_stability_classifier_integrity = ok`
  - `f_backtest_recent_vs_baseline_integrity = ok`
- Source-alignment proof:
  - READY summary rows: `2149`
  - READY rows with blank classifier state: `0`
  - READY rows with blank classifier reason path: `0`
