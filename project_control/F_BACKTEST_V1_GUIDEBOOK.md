# F Backtest V1 Guidebook

## Purpose
This guidebook explains the F backtest process in plain language.

The goal is to answer one question:
- If we had used our current policy on past market history, would the listing have been workable and profitable enough?

## Core Scripts And Roles

1. Policy snapshot
- Script: `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
- Output: `out/systems/F/live/feeder_backtest_policy_live.csv`
- Role: writes the active policy values used by the replay.

2. Input view build
- Script: `scripts/flows/F/F071_build_backtest_input_view.py`
- Output: `out/systems/F/live/feeder_backtest_input_view_live.csv`
- Role: prepares one replay input row per `seller_sku + asin + policy_id`.

3. Daily replay
- Script: `scripts/flows/F/F072_run_backtest_replay.py`
- Output: `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- Role: simulates daily policy behavior over historical chart days.

4. Summary build
- Script: `scripts/flows/F/F073_build_backtest_summary.py`
- Output: `out/systems/F/live/feeder_backtest_summary_live.csv`
- Role: collapses daily replay rows into one decision row per listing.

5. Backtest health
- Script: `scripts/flows/F/F074_build_backtest_health.py`
- Output: `out/systems/F/live/feeder_backtest_health.csv`
- Role: validates schema, coverage, confidence mix, and join quality.

6. Calibration review pack
- Script: `scripts/one_off/F002_build_backtest_calibration_set.py`
- Outputs:
  - `out/analysis_reports/f_backtest_calibration_set_<timestamp>.csv`
  - `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - `out/analysis_reports/f_backtest_calibration_set_latest.md`
- Role: creates a review sample for threshold and recommendation sanity checks.

## Identity Resolution Rule

### Why it exists
Some ASINs can map to more than one SKU in source evidence.
This creates ambiguous replay rows and a health warning.

### Resolver file
- Path: `config/f_backtest_asin_resolution.csv`
- Required columns:
  - `asin`
  - `seller_sku`
  - `resolution_status`
  - `resolution_reason`
  - `resolution_source`
  - `approved_utc`

### Runtime behavior in F071
- If an ASIN has multiple candidate SKU matches:
  - F071 checks the resolver file first.
  - If a resolver row selects one SKU from the candidate set:
    - F071 keeps only that row.
    - `mapping_status` becomes `resolved_asin_match`.
  - If no resolver row exists:
    - F071 keeps normal fallback behavior.
    - `mapping_status` stays `multi_sku_asin_match`.
    - row stays manual review.

### Operator action when ambiguity appears again
1. Find ambiguous rows in `feeder_backtest_input_view_live.csv` where `mapping_status=multi_sku_asin_match`.
2. Decide the single SKU to keep per ASIN.
3. Add or update resolver rows in `config/f_backtest_asin_resolution.csv`.
4. Rerun F071, then F072, F073, and F074.
5. Confirm `f_backtest_join_resolution` is `ok` in `feeder_backtest_health.csv`.

## Calibration Review Rule

### New review fields in calibration output
- `calibration_review_flag`
- `calibration_review_reason`
- `critical_amazon_recommendation_mismatch_flag`

### First-pass mismatch rule
Set mismatch flag when both are true:
- `amazon_risk_level = critical`
- recommendation is `Normal fit` or `Managed fit`

When this happens:
- `critical_amazon_recommendation_mismatch_flag = 1`
- `calibration_review_flag = 1`
- `calibration_review_reason = critical_amazon_recommendation_mismatch`

## Measured Scenario Share Rule

### Why this changed
The original v1 replay used a provisional shared-sales default (`50%` for shared scenarios).
This is now replaced by measured scenario rates from observed chart history.

### Current replay behavior in F072
- Scenarios are still:
  - `solo_or_no_meaningful_competition`
  - `sharing_with_fba`
  - `sharing_with_amazon`
  - `sharing_with_amazon_and_fba`
- For each ASIN and scenario, F072 now measures historical share signal:
  - if Amazon is present, count days where Buy Box is not Amazon-owned
  - if Amazon is not present, count days where Buy Box is present
- F072 blends ASIN-level rate with a global scenario prior for sparse history.
- F072 applies scenario share caps for shared-market scenarios:
  - `sharing_with_amazon_and_fba` cap = `70`
  - `sharing_with_amazon` cap = `80`
  - `sharing_with_fba` cap = `90`
- `shared_sales_default_pct` remains a fallback when measured data is missing.
- Replay `reason_codes` now carry share-governance tags:
  - `share_source_sparse_asin_blend`
  - `share_sparse_asin_history`
  - `share_governance_cap_applied`

### Operational meaning
- Amazon-heavy scenarios can now produce materially lower share than 50%.
- FBA-only and solo scenarios can remain high when evidence supports it.
- This keeps v1 simple while removing the fixed placeholder behavior.

## Attribution Confidence Rule

### Why it exists
Some rows can be replay-ready while still carrying weaker attribution confidence.
This must be explicit, not hidden.

### Current behavior in F071
- F071 derives attribution confidence from:
  - mapping quality (unique, legacy, missing, ambiguous)
  - channel pairing depth
  - Buy Box coverage and Amazon dominance context
- F071 then combines history confidence and attribution confidence using the stricter level.
- Attribution reason tags are written into `input_reason_codes`.
- Low attribution confidence forces manual review.

### Current behavior in F073
- F073 carries attribution tags from input rows into summary reason codes for ready rows.
- This keeps recommendation output explainable without forcing all attribution caveats into hard fail.

## Share Validity Health Check

Backtest health now includes:
- `f_backtest_sales_share_validity`
- `f_backtest_share_prior_dependency`
- `f_backtest_attribution_confidence_share`

Check behavior:
- `fail` if replay share values are non-numeric or outside 0 to 100.
- `warn` if replay rows exist but share values are missing.
- `warn` if Amazon scenarios are dominated by very high share values.
- `ok` otherwise.

`f_backtest_attribution_confidence_share` behavior:
- `warn` when severe attribution tags are concentrated in ready rows.
- `ok` when severe attribution tags are within tolerance.
- non-severe attribution context remains visible in reason tags without forcing warning noise.

`f_backtest_share_prior_dependency` behavior:
- `warn` when a high share of replay rows use sparse prior-blend share sourcing.
- `ok` when prior dependency stays within tolerance.
- `fail` if replay schema is invalid and the check cannot run.

## BBP Monthly Sales Demand Basis Rule

### Why it exists
- BBP monthly chart can include future projected bars.
- BBP current month can be partial and unstable.
- replay demand was previously inflated when helper chosen units overrode lower chart evidence.

### Current rule
- Scraper captures monthly chart labels and units from `estSalesMonthlyChart`.
- Replay demand basis must use the last completed month when available.
- Current month is observability-only.
- Future bars are counted and ignored for replay demand.
- Helper chosen units remain available for turnover/debug, but are not the trusted replay basis when completed-month data exists.

### New health visibility
- `f_backtest_demand_basis_integrity`
- `fail` when ready rows drift away from last-completed-month basis or helper chosen demand leaks through.
- `warn` when rows fall back because trusted completed-month data is missing.

## Sampled-ASIN BBP Audit Export

### Script
- `scripts/one_off/F004_build_bbp_sales_sample_audit.py`

### Outputs
- `out/analysis_reports/f_backtest_bbp_sales_sample_audit_<timestamp>.csv`
- `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`

### Purpose
- Build one checkable row per sampled ASIN with:
  - scraper chart month labels and units
  - trusted completed/current/future month fields
  - replay demand basis source and units
  - mismatch flag and reason codes
- This avoids one-by-one spot checks and shows whether errors are isolated or widespread.

## When Model Looks Too Harsh Or Too Loose

1. Too harsh signs
- High `Avoid` share on listings that operator expects to be tradable.
- Many strong listings moved to manual review without data-quality reasons.

2. Too loose signs
- Frequent mismatch flags (`critical` Amazon risk but still `Normal fit` or `Managed fit`).
- High live concentration of listings that later require exit behavior.

3. Correction workflow
- Use the latest calibration CSV first.
- Review flagged mismatch rows first.
- Adjust one policy area at a time.
- Rerun full backtest chain and compare before/after outputs.
- Keep changes minimal and evidence-based.

## Standard Run Order

```powershell
python scripts/flows/F/F070_build_backtest_policy_snapshot.py
python scripts/flows/F/F071_build_backtest_input_view.py
python scripts/flows/F/F072_run_backtest_replay.py
python scripts/flows/F/F073_build_backtest_summary.py
python scripts/flows/F/F074_build_backtest_health.py
python scripts/one_off/F002_build_backtest_calibration_set.py
python scripts/one_off/F004_build_bbp_sales_sample_audit.py
```

## Proof Checklist Before Sign-Off
- `feeder_backtest_health.csv` exists and is current.
- `f_backtest_join_resolution` is `ok`.
- `f_backtest_sales_share_validity` is `ok`.
- `f_backtest_share_prior_dependency` is `ok` or explicitly accepted as non-blocking.
- `f_backtest_attribution_confidence_share` is `ok` or explicitly accepted as non-blocking.
- `f_backtest_demand_basis_integrity` is `ok` or explicitly accepted as non-blocking.
- `multi_sku_asin_match` count is `0` for resolved known conflicts.
- Calibration output exists and mismatch flags are visible.
- Sampled-ASIN BBP audit output exists and mismatch rows are explicitly listed.
- Required test pack passes.
