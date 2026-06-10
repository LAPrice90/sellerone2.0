# Coding Plan

## Ticket
- Name: `f-weak-uk-variant-review-signal-v1`
- Scope: UK review signal audit, triage integration, and F019 upstream routing
- Owner flow: F

## Goal
- Route weak UK review evidence out of clean Pass using stored evidence.
- Keep existing demand and history routing intact.
- Stop only if required review fields are missing.

## Inputs
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`

## Input Fields
- `historical_uk_reviews`
- `variant_reviews`
- `expected_units_next_30d`
- `expected_profit_next_30d_gbp`
- `demand_conflict_code`
- `history_risk_code`
- identity fields from pass and near-miss packs

## Planned Audit Output
- Path: `out/analysis_reports/f_uk_review_signal_audit_latest.csv`

Required columns:
- `asin`
- `candidate_id`
- `supplier_sku`
- `review_pack_type`
- `uk_review_code`
- `uk_review_recommended_action`
- `uk_review_supporting_codes`
- `uk_reviews`
- `variant_reviews`
- `expected_units_next_30d`
- `expected_profit_next_30d_gbp`
- `evidence_source`

## Rule Codes
- `uk_reviews_lt3`
  - UK reviews are 0, 1, or 2.
  - Action: `remove_from_clean_pass`.
- `uk_reviews_3_to_5`
  - UK reviews are 3, 4, or 5.
  - Action: `manual_review`.
- `uk_reviews_6_to_9`
  - UK reviews are 6 to 9.
  - Action: `supporting_evidence_only`.
- `uk_reviews_10_plus`
  - UK reviews are 10 or more.
  - Action: `allow_if_other_checks_pass`.
- `uk_reviews_missing`
  - UK review evidence missing or not numeric.
  - Action: `targeted_rescan_needed`.

## Implementation Sequence
1. Build `scripts/one_off/F026_build_uk_review_signal_audit.py`.
2. Add `tests/test_f026_build_uk_review_signal_audit.py`.
3. Run audit and record counts.
4. Integrate UK review columns into F021 triage.
5. Add/update F021 tests.
6. Move accepted routing into F019 so weak UK review rows leave clean Pass.
7. Add/update F019 tests.
8. Rebuild F019 outputs.
9. Rerun F021 against rebuilt outputs.
10. Update RESPONSE.md, EVIDENCE_BASELINE.md, FIX_LIST.md, and PLAN_STATUS.md.

## Tests Required
- `uk_reviews_lt3` routes out of clean Pass.
- `uk_reviews_3_to_5` routes to manual review.
- `uk_reviews_6_to_9` remains supporting evidence only.
- `uk_reviews_10_plus` preserves existing behavior.
- Missing UK reviews become targeted rescan needed, not invented.
- Demand routing still works.
- History routing still works.
- Manual review-memory fail still wins in F021.
- No unclassified rows.

## Proof Required
- Audit counts by `uk_review_code`.
- Clean Pass count before and after F019 rebuild.
- Rows removed by UK review rule.
- Rows routed to manual review by UK review rule.
- Demand and history routing still present.
- B0C8C3JF9X remains correctly classified.

