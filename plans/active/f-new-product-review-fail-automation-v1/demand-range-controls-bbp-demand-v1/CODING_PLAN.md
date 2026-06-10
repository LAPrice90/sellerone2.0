# Coding Plan

## Ticket
- Name: `f-demand-range-controls-bbp-demand-v1`
- Scope: demand range audit and later root-cause pass-gate correction
- Owner flow: F

## Goal
- Build a read-only audit first.
- Count where BBP demand exceeds the Amazon visible demand range.
- Decide hard fail versus manual review before changing the upstream pass gate.

## Core Rule
- Amazon defines the demand range.
- BBP estimates inside the Amazon range.
- If BBP exceeds the Amazon-supported range materially, treat it as likely parent, variation, or non-UK contamination.

## Inputs
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/inbox/feeder_review_events.csv`

## Input Fields
- `monthly_sold`
- `expected_units_next_30d`
- `bbp_sales_replay_demand_basis_units`
- `demand_confidence_note`
- `historical_uk_reviews`
- `variant_reviews`
- `review_pack_type`
- `backtest_decision_state`
- `recommendation`
- `decision_confidence`

## Planned Output
- Path: `out/analysis_reports/f_demand_range_bbp_conflict_audit_latest.csv`

Required columns:
- `asin`
- `candidate_id`
- `supplier_sku`
- `review_pack_type`
- `amazon_demand_signal`
- `amazon_demand_floor`
- `amazon_demand_ceiling`
- `bbp_units`
- `expected_units_next_30d`
- `demand_conflict_code`
- `uk_reviews`
- `variant_reviews`
- `confidence_adjustment`
- `recommended_action`
- `evidence_source`

## Rule Codes
- `amazon_blank_bbp_high`
  - Amazon signal blank.
  - BBP or expected units above `49`.
  - Recommended action: `remove_from_clean_pass`.
- `amazon_blank_bbp_low`
  - Amazon signal blank.
  - BBP and expected units are `0-49`.
  - Recommended action: `allow_if_other_checks_pass`.
- `amazon_50_bbp_reasonable`
  - Amazon signal `50+`.
  - BBP units between `50` and `100`.
  - Recommended action: `allow_if_other_checks_pass`.
- `amazon_50_bbp_warn`
  - Amazon signal `50+`.
  - BBP units between `101` and `250`.
  - Recommended action: `manual_review`.
- `amazon_50_bbp_inflated`
  - Amazon signal `50+`.
  - BBP units above `250`.
  - Recommended action: `remove_from_clean_pass`.
- `weak_uk_review_confirms_demand_risk`
  - UK reviews are below threshold, initially `<6`.
  - Demand is high or BBP exceeds Amazon range.
  - Recommended action: strengthen existing fail or manual-review decision.
- `seller_stock_missing_for_demand_check`
  - Seller stock count would help verify demand but is not stored.
  - Recommended action: `targeted_rescan_needed`.

## Implementation Phases
- Phase 1: Audit only.
  - Create `scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`.
  - Create `tests/test_f023_build_demand_range_bbp_conflict_audit.py`.
  - Write output CSV only.
- Phase 2: Threshold review.
  - Produce counts by rule code.
  - Produce sample rows per rule code.
  - User decides hard fail versus manual review.
- Phase 3: Triage integration.
  - Feed accepted rule codes into F021 output.
  - Keep row-level evidence visible.
- Phase 4: Upstream root fix.
  - Move accepted rules into the earliest correct pass/backtest owner path.
  - Prevent affected rows from entering clean Pass.
- Phase 5: Optional rescan enhancement.
  - Capture seller stock count only if an approved scoped rescan path exists.

## Tests
- Test 1: Amazon blank plus BBP 813 creates `amazon_blank_bbp_high`.
- Test 2: Amazon blank plus BBP 30 does not create high-demand conflict.
- Test 3: Amazon `50+` plus BBP 67 creates `amazon_50_bbp_reasonable`.
- Test 4: Amazon `50+` plus BBP 180 creates `amazon_50_bbp_warn`.
- Test 5: Amazon `50+` plus BBP 1000 creates `amazon_50_bbp_inflated`.
- Test 6: UK reviews `<6` strengthens demand-risk action.
- Test 7: Seller stock count is reported missing when needed, not invented.
- Test 8: Output has no unclassified rows.

## Commands For Later Execution
```powershell
python -m py_compile scripts\one_off\F023_build_demand_range_bbp_conflict_audit.py tests\test_f023_build_demand_range_bbp_conflict_audit.py
pytest tests\test_f023_build_demand_range_bbp_conflict_audit.py -q
python scripts\one_off\F023_build_demand_range_bbp_conflict_audit.py
```

## Proof Required
- Total rows audited.
- Count by `demand_conflict_code`.
- Count by `recommended_action`.
- All ASINs in `amazon_blank_bbp_high`.
- Sample rows for each rule.
- Whether `B0C8C3JF9X` is correctly flagged.
- Whether any rule requires new data before enforcement.

## Do Not Do Yet
- Do not change the live pass gate yet.
- Do not run a full scraper rescan.
- Do not auto-fail all matching rows until samples are reviewed.
- Do not use seller stock count unless it is actually stored.

