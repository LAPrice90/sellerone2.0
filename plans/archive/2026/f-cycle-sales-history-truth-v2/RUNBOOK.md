# Runbook

## Purpose
- What this plan or system does:
  - turn scraped sales history and price history into a business decision:
    - how many sales are likely available to us now
    - what monthly profit that implies
    - whether the listing is seasonal, stable, drifting, or too new
    - whether the correct output is `pass`, `fail`, or `manual_review`

## Current operating mode
- As of `2026-04-20`, the weekend scrape is treated as the working evidence baseline for this ticket.
- Broad supplier scraping is not the active task now.
- Default mode is:
  1. build and test decision logic on the frozen weekend dataset
  2. keep scrape cleanup separate through the targeted subset report
  3. only resume targeted recovery if a known coverage gap blocks a specific proof point
- Current retry subset artifact:
  - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`

## Standard run order
```powershell
# Current evidence rebuild path
python -m scripts.flows.F.F070_build_backtest_policy_snapshot
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F004_build_bbp_sales_sample_audit.py
python scripts/one_off/F005_build_sales_history_validation_audit.py
python scripts/one_off/F011_build_sales_history_accuracy_pack.py
python scripts/one_off/F012_build_sales_history_learning_pack.py
```

## Immediate recovery path
- Use this order when demand truth is healthy but scrape coverage is thin:
  1. build a mixed live validation pack:
     - `python scripts/one_off/F006_build_live_asin_validation_pack.py --completed-count 4 --zero-history-count 2 --missing-basis-count 6`
  2. build targeted subset from missing-basis rows:
     - dry run:
       - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --include-alignment-missing --output-dir out/analysis_reports`
     - apply:
       - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --include-alignment-missing --apply --output-dir out/analysis_reports`
  3. run targeted rescrape on the supplier subset queue
  4. rerun the standard evidence rebuild path
  5. restore the full supplier queue from `canonical_current`:
     - `python scripts/flows/F/F062_reset_supplier_test_mode.py --supplier-id stocklist_supplier --no-clear-review-live`
  6. start the normal overnight supplier scan:
     - `run_F_supplier_full_legacy_scan.bat stocklist_supplier`

## Validation steps
- Step 1:
  - confirm BBP monthly chart evidence still separates:
    - last completed month
    - current partial month
    - future predicted months ignored
- Step 2:
  - confirm the current F summary and health were rebuilt after the latest input/replay outputs
- Step 3:
  - confirm sampled-ASIN audit exists and can be checked row by row
- Step 4:
  - confirm raw observed monthly units and price-qualified monthly units are both present and not conflated
  - confirm qualification component fields are explicit in input view:
    - `qualification_market_gate_state`
    - `qualification_market_gate_factor`
    - `qualification_amazon_pressure_factor`
    - `qualification_buy_box_coverage_factor`
    - `qualification_maturity_factor`
    - `qualification_final_factor`
    - `qualification_zero_or_block_reason`
  - confirm READY rows use trusted demand basis only:
    - `bbp_last_completed_month`
    - `bbp_zero_history`
- Step 5:
  - confirm the decision output states:
    - expected monthly units now
    - expected monthly profit now
    - expected units and profit source tags
    - confidence
    - reason codes
- Step 6:
  - if coverage recovery is the goal, compare against the current `2026-04-20` baseline instead of the old April prompt numbers:
    - latest successful ASIN captures greater than `2342`
    - targeted retry subset rows less than `2207`
    - missing-basis / missing-core-price-history reasons trend downward in `f_targeted_rescrape_subset_latest.csv`
- Step 7:
  - run one-off accuracy pack for sampled ASINs:
    - ensure `f_sales_history_accuracy_pack_latest.csv` is refreshed
    - ensure `f_sales_history_accuracy_summary_latest.csv` reports mismatch and missing-input counts
    - use `f_operator_sales_checks_template_latest.csv` as the operator input sheet for sold-30d and operator decision checks
- Step 8:
  - run one-off learning pack:
    - ensure `feeder_sales_history_learning_live.csv` is refreshed
    - ensure review, health, and actuals-template latest outputs exist
    - confirm pending-outcome rows are explicit until actuals are filled

## Expected outputs
- Output:
  - BBP raw sales history evidence
- Path:
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- What good looks like:
  - completed month, current month, and ignored future month fields are populated truthfully

- Output:
  - sales history feature view
- Path:
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
- What good looks like:
  - one row per `seller_sku + asin + policy_id`
  - includes trusted sales-history basis and price-qualified demand fields

- Output:
  - decision summary
- Path:
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
- What good looks like:
  - one row per listing with decision fields and plain-English reasons

- Output:
  - health
- Path:
  - `out/systems/F/live/feeder_backtest_health.csv`
- What good looks like:
  - health file is at least as new as input/replay/summary
  - no stale-proof ambiguity

- Output:
  - validation audit
- Path:
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- What good looks like:
  - sampled ASIN rows show raw monthly units, qualified monthly units, and operator-check mismatch flags

- Output:
  - accuracy pack and summary
- Paths:
  - `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
  - `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
  - `out/analysis_reports/f_operator_sales_checks_template_latest.csv`
- What good looks like:
  - row-level model vs operator comparison has explicit bucket codes
  - missing operator checks remain visible as missing-input buckets
  - mismatch counts are explicit and not masked

- Output:
  - post-purchase learning outputs
- Paths:
  - `out/systems/F/live/feeder_sales_history_learning_live.csv`
  - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`
- What good looks like:
  - buy-time assumptions are preserved by snapshot key
  - outcome rows are classified into explicit controlled outcomes
  - missing outcomes remain visible as `pending_outcome` until operator actuals are provided

## Health checks
- Check:
  - `f_backtest_demand_basis_integrity`
- Pass condition:
  - READY rows use trusted completed-month basis or explicit zero-history basis
- Warning condition:
  - no fallback in READY rows, but manual-review share is elevated because trusted basis is missing on many rows
- Fail condition:
  - current or predicted month leaks into replay demand

- Check:
  - `f_backtest_join_resolution`
- Pass condition:
  - no unresolved join flags remain on ready rows
- Warning condition:
  - known ambiguous rows still exist and are held out truthfully
- Fail condition:
  - ambiguous join state leaks into trusted decision output

- Check:
  - `f_backtest_price_qualified_demand_integrity`
- Pass condition:
  - raw observed demand and qualified demand are both present and reconcile to the defined rule
  - qualification component factors and reason path are non-blank and internally consistent on READY rows
- Warning condition:
  - fallback or low-confidence qualification is used
- Fail condition:
  - pass/fail uses raw observed demand as if it were qualified demand

- Check:
  - `f_backtest_qualification_source_alignment`
- Pass condition:
  - READY summary rows use `input_qualified` source path
  - source tags match actual units/profit calculation path
  - READY rows have non-blank qualification reason path
- Warning condition:
  - zero-qualified READY rows exist without clear zero/block reason in summary
- Fail condition:
  - READY summary rows silently rely on replay fallback path

- Check:
  - planned `f_sales_history_recent_vs_baseline_integrity`
- Pass condition:
  - recent-performance labels match the written decision model
- Warning condition:
  - recent-performance classification falls back due to limited history
- Fail condition:
  - seasonality or recent state is produced without enough history

- Check:
  - planned validation accuracy check
- Pass condition:
  - sampled ASIN validation mismatch rate stays within agreed tolerance
- Warning condition:
  - mismatch rate is noticeable but explainable
- Fail condition:
  - sampled validation shows the decision model is materially misleading

## Failure recovery
- If input is stale:
  - rerun the current evidence rebuild path
- If output is missing:
  - confirm owner script first, then rebuild from the earliest missing dependency
- If tests fail:
  - run the batch-scoped pytest pack and fix root cause before touching downstream output wording
- If runtime ownership is unclear:
  - not applicable for this planning ticket
  - one-off audit scripts must stay outside daily loops until a later approved promotion

## Archive note
- What to preserve when this plan is finished:
  - the decision model
  - commercial rules such as the monthly profit floor
  - validation samples and mismatch evidence
  - post-purchase learning rules and outcome classifications
