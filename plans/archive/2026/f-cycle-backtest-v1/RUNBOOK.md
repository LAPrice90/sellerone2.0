# Runbook

## Purpose
- What this plan or system does:
  - replay historical F market data under one active policy profile
  - summarise likely viability and risk for restock decisions
  - expose the result and policy controls safely through O

## Standard run order
```powershell
# Bootstrap active policy only when needed
python -m scripts.flows.F.F070_build_backtest_policy_snapshot

# Normal controlled policy refresh path
python -m scripts.flows.F.F075_apply_backtest_policy_updates
python scripts/one_off/F003_refresh_backtest_after_policy_change.py

# Full manual rebuild path
python -m scripts.flows.F.F070_build_backtest_policy_snapshot
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F002_build_backtest_calibration_set.py
python scripts/one_off/F004_build_bbp_sales_sample_audit.py
```

## Validation steps
- Step 1:
  - confirm the live outputs exist:
    - `feeder_backtest_policy_live.csv`
    - `feeder_backtest_input_view_live.csv`
    - `feeder_backtest_replay_daily_live.csv`
    - `feeder_backtest_summary_live.csv`
    - `feeder_backtest_health.csv`
- Step 2:
  - read `feeder_backtest_health.csv` and confirm all checks are `ok`
- Step 3:
  - read `f_backtest_calibration_set_latest.csv` or `.md` and confirm the review pack rebuilt
- Step 4:
  - read `f_backtest_bbp_sales_sample_audit_latest.csv` and confirm:
    - all sampled ASIN rows are present
    - Amazon links are populated
    - mismatch rows are explicitly flagged

## Expected outputs
- Output:
  - active policy
  - Path:
    - `out/systems/F/live/feeder_backtest_policy_live.csv`
  - What good looks like:
    - exactly one active row
- Output:
  - summary
  - Path:
    - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - What good looks like:
    - one row per seller_sku + asin + policy_id with recommendation fields present
- Output:
  - health
  - Path:
    - `out/systems/F/live/feeder_backtest_health.csv`
  - What good looks like:
    - all checks `ok`
- Output:
  - calibration pack
  - Path:
    - `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - What good looks like:
    - latest review sample exists and flagged rows are visible when present
- Output:
  - sampled-ASIN BBP sales audit
  - Path:
    - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
  - What good looks like:
    - one row per sampled ASIN with BBP chart fields, replay demand basis fields, and mismatch flags

## Health checks
- Check:
  - `f_backtest_policy_single_active_row`
  - Pass condition:
    - value = 1
  - Warning condition:
    - none expected in steady state
  - Fail condition:
    - zero or multiple active rows
- Check:
  - `f_backtest_join_resolution`
  - Pass condition:
    - `ok` and value = 0
  - Warning condition:
    - unresolved multi-SKU ASIN matches
  - Fail condition:
    - ambiguous join state breaks deterministic summary
- Check:
  - `f_backtest_summary_row_coverage` and `f_backtest_replay_row_coverage`
  - Pass condition:
    - summary and replay cover ready keys correctly
  - Warning condition:
    - missing or duplicate ready keys
  - Fail condition:
    - structural mismatch between summary and replay outputs
- Check:
  - `f_backtest_demand_basis_integrity`
  - Pass condition:
    - `ok` with no ready-row basis drift
  - Warning condition:
    - ready rows rely on fallback demand basis because trusted completed-month data is missing
  - Fail condition:
    - ready rows do not use last completed month when it is available
    - helper chosen units leak into demand basis
    - demand basis units do not match trusted completed-month units
- Check:
  - `f_backtest_sales_share_validity`
  - Pass condition:
    - `ok`
  - Warning condition:
    - missing share values or suspiciously high Amazon-scenario shares
  - Fail condition:
    - share values are non-numeric or outside 0 to 100
- Check:
  - `f_backtest_share_prior_dependency`
  - Pass condition:
    - `ok`
  - Warning condition:
    - high share of replay rows depends on sparse ASIN prior-blend sourcing
  - Fail condition:
    - replay schema failure blocks prior-dependency check
- Check:
  - `f_backtest_attribution_confidence_share`
  - Pass condition:
    - `ok`
  - Warning condition:
    - high share of ready rows with severe attribution-risk tags
  - Fail condition:
    - input view schema failure blocks attribution check

## Failure recovery
- If input is stale:
  - rerun the controlled refresh chain or the full manual rebuild path
- If output is missing:
  - start from F070 only if the live policy file is missing or needs reset, otherwise use F075 then F003
- If tests fail:
  - run the scoped pytest pack from the relevant batch before widening the investigation
- If runtime ownership is unclear:
  - not applicable here because this backtest is not a scheduler-owned live loop

## Archive note
- What to preserve when this plan is finished:
  - source coding plan
  - execution batches and replies
  - guidebook
  - latest proof snapshot and any approved follow-on batch docs
