# Response

## Phase 4 Implementation Request
- Ticket: `F demand range controls BBP demand - Phase 4 implementation`
- Move accepted demand-range routing upstream into F019 so future clean Pass review packs stop including obvious demand-conflict rows.
- Owner changed:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Scope guard:
  - F019 review-pack routing only.
  - No scraper behavior change.
  - No queue, Google Sheets, local DB, A script, full F061 rescan, or upstream scraper run changed or run.

## Phase 4 Implementation Files Changed
- Modified F019 review-pack builder:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Modified focused F019 tests:
  - `tests/test_f019_build_live_price_file_near_miss_pack.py`
- Updated ticket response record:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`
- Rebuilt F019 outputs:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

## Phase 4 Implementation Behavior Added
- F019 now classifies demand range before clean Pass rows are appended.
- Added demand output columns to pass and near-miss review outputs:
  - `demand_conflict_code`
  - `demand_recommended_action`
  - `demand_supporting_codes`
  - `demand_evidence_source`
- Accepted routing now applies in F019:
  - `amazon_blank_bbp_high` -> routed out of clean Pass as `remove_from_clean_pass`
  - `amazon_50_bbp_inflated` -> routed out of clean Pass as `remove_from_clean_pass`
  - `amazon_50_bbp_warn` -> routed out of clean Pass as `manual_review`
  - `weak_uk_review_confirms_demand_risk` -> supporting evidence only
  - `seller_stock_missing_for_demand_check` -> supporting evidence only, with no invented seller stock count
  - `amazon_50_bbp_reasonable` -> allowed if other checks pass
- Existing timeout near-miss behavior is preserved.
- Existing clean Pass rows without high demand conflict remain clean Pass.

## Phase 4 Implementation Test Results
- `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py`
  - Passed.
- `pytest tests/test_f019_build_live_price_file_near_miss_pack.py -q`
  - Passed: `10 passed in 1.03s`.
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - Passed and rebuilt latest F019 review outputs.

## Phase 4 Implementation Output Paths
- Latest pass review:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- Latest near-miss review:
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- Latest summary:
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- Timestamped pass review:
  - `out/analysis_reports/f_live_price_file_pass_review_20260423T133613Z.csv`
- Timestamped near-miss review:
  - `out/analysis_reports/f_live_price_file_near_miss_review_20260423T133613Z.csv`
- Timestamped summary:
  - `out/analysis_reports/f_live_price_file_review_summary_20260423T133613Z.csv`

## Phase 4 Implementation Counts
- Clean Pass count before F019 rebuild: `266`
- Clean Pass count after F019 rebuild: `226`
- Total rows routed out of clean Pass by demand rule: `40`
- Rows routed to `remove_from_clean_pass` by demand rule: `38`
- Rows routed to `manual_review` by demand rule: `2`
- Near-miss review rows after rebuild: `3096`

## Phase 4 Demand Action Counts
- Across rebuilt F019 pass and near-miss review outputs:
  - `allow_if_other_checks_pass`: `3218`
  - `manual_review`: `10`
  - `remove_from_clean_pass`: `94`
- In clean Pass output after rebuild:
  - `allow_if_other_checks_pass`: `226`
- In near-miss output after rebuild:
  - `allow_if_other_checks_pass`: `2992`
  - `manual_review`: `10`
  - `remove_from_clean_pass`: `94`
- Demand-routed clean Pass rows in near-miss output:
  - `demand_range_conflict, remove_from_clean_pass`: `38`
  - `demand_range_manual_review, manual_review`: `2`

## Phase 4 Supporting Demand Code Counts
- `amazon_50_bbp_inflated`: `10`
- `amazon_50_bbp_reasonable`: `16`
- `amazon_50_bbp_warn`: `10`
- `amazon_blank_bbp_high`: `84`
- `amazon_blank_bbp_low`: `3202`
- `seller_stock_missing_for_demand_check`: `104`
- `weak_uk_review_confirms_demand_risk`: `30`

## Phase 4 B0C8C3JF9X Proof
- Present in clean Pass output after rebuild: `no`
- Present in near-miss/routed output after rebuild: `yes`
- Routed classification:
  - `near_miss_type`: `demand_range_conflict`
  - `reviewability_state`: `remove_from_clean_pass`
  - `screening_fail_code`: `DEMAND_RANGE_BLOCK`
  - `screening_status_reason`: `amazon_blank_bbp_high`
  - `demand_conflict_code`: `amazon_blank_bbp_high`
  - `demand_recommended_action`: `remove_from_clean_pass`
  - `demand_supporting_codes`: `amazon_blank_bbp_high|weak_uk_review_confirms_demand_risk|seller_stock_missing_for_demand_check`

## Phase 4 Implementation Scope Guard
- F019 review-pack routing was changed.
- No scraper behavior was changed.
- No queue was changed.
- No Google Sheets write was made.
- No local DB change was made.
- No A script was run.
- No full F061 rescan was run.
- No upstream scraper run was made.
- `WORK_LOG.md` was not updated.

---

## Phase 4 Request
- Ticket: `F demand range controls BBP demand - Phase 4 upstream planning only`
- Study where accepted demand-range rules should move upstream so future clean Pass packs stop including obvious demand-conflict rows.
- Planning only. Do not implement code changes.
- Do not change pass gates, queues, Google Sheets, local DB, scraper runs, A scripts, full F061 rescan, or upstream enforcement.

## Phase 4 What Changed
- Created upstream planning doc:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/PHASE_4_UPSTREAM_PLAN.md`
- Updated ticket response record:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`

## Phase 4 Files Inspected
- `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/README.md`
- `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/CODING_PLAN.md`
- `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/PHASES.md`
- `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/DECISION_BRIEF.md`
- `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F030_build_shared_feeder_pass_logic.py`
- `scripts/one_off/F017_build_pass_gate_review_pack.py`
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`
- `scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_f021_build_new_product_review_fail_triage.py`
- `tests/test_f023_build_demand_range_bbp_conflict_audit.py`
- `tests/test_f030_build_shared_feeder_pass_logic.py`
- `tests/test_f073_build_backtest_summary.py`
- `tests/test_o_ui_operator_view.py`

## Phase 4 Owner Path Recommendation
- Recommended owner for a later implementation ticket:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Reason:
  - F019 is the first place where `out/analysis_reports/f_live_price_file_pass_review_latest.csv` is created.
  - F019 joins the row state, first checks, scrape evidence, and backtest summary before appending `row_status == "pass"` rows to the clean Pass output.
  - The current root cause is that this clean Pass append path does not consider accepted demand-range blockers.
- Recommended rule type:
  - Change pass-pack lane assignment, not the backtest decision.
  - Treat `amazon_blank_bbp_high` and `amazon_50_bbp_inflated` as hard clean-Pass blockers.
  - Treat `amazon_50_bbp_warn` as a manual-review blocker.
  - Treat `weak_uk_review_confirms_demand_risk` as supporting confidence evidence only.
  - Treat `seller_stock_missing_for_demand_check` as targeted-rescan evidence without inventing seller stock.
  - Keep `amazon_50_bbp_reasonable` allowed if other checks pass.

## Phase 4 Exact Proposed Code Touchpoints
- Later implementation should modify:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Proposed F019 changes:
  - Add a demand-range classifier before the current `row_status == "pass"` append path.
  - Add or preserve explicit demand output fields if approved:
    - `demand_conflict_code`
    - `demand_recommended_action`
    - `demand_evidence_source`
    - `demand_supporting_codes`
  - Route blocked clean Pass rows into a visible review/manual lane with explicit demand reason codes.
  - Reconcile summary counts for clean Pass rows removed and demand-review rows added.
- Later implementation may update:
  - `tests/test_f019_build_live_price_file_near_miss_pack.py`
  - `tests/test_o_ui_operator_view.py` if added columns affect UI readers.
  - A new focused helper test if demand-range logic is moved into a shared F helper.
- Not recommended as Phase 4 implementation touchpoints:
  - `scripts/flows/F/F073_build_backtest_summary.py`
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `scripts/flows/F/F030_build_shared_feeder_pass_logic.py`
  - `scripts/one_off/F017_build_pass_gate_review_pack.py`
  - `scripts/one_off/F021_build_new_product_review_fail_triage.py`

## Phase 4 Tests Required Later
- Amazon blank plus BBP or expected units over 49 is excluded from clean Pass and routed with `amazon_blank_bbp_high`.
- Amazon `50+` plus BBP over 250 is excluded from clean Pass and routed with `amazon_50_bbp_inflated`.
- Amazon `50+` plus BBP 101-250 is excluded from clean Pass and routed as manual review with `amazon_50_bbp_warn`.
- `weak_uk_review_confirms_demand_risk` is supporting evidence only and does not block clean Pass by itself.
- `seller_stock_missing_for_demand_check` reports missing evidence or targeted rescan without invented seller stock.
- `amazon_50_bbp_reasonable` remains allowed if other checks pass.
- Existing timeout and near-miss classifications still work.
- No demand-blocked row is silently unclassified.
- B0C8C3JF9X, if present, no longer remains in clean Pass after implementation and is visible in the routed review lane with supporting demand codes.
- Summary counts reconcile removed clean Pass rows and added demand-review rows.

## Phase 4 Proof Path For Later Implementation
- Use focused tests and existing artifacts only.
- Do not run A scripts.
- Do not run full F061 rescan.
- Suggested implementation commands:
  - `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py`
  - `pytest tests/test_f019_build_live_price_file_near_miss_pack.py -q`
  - `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Required proof after implementation:
  - clean Pass row count before and after demand routing.
  - count by demand action.
  - count by lane after demand routing.
  - B0C8C3JF9X clean Pass presence check.
  - B0C8C3JF9X routed classification if present.
  - reconciliation that removed clean Pass rows equal added demand-review rows.

## Phase 4 Risks And Non-Goals
- Risks:
  - Adding columns to F019 outputs may affect downstream readers, so O UI reader tests should be checked if columns are added.
  - Routing blocked rows into the current near-miss output needs clear codes so demand blockers are not confused with timeout-only near misses.
  - Moving this rule into F071 or F073 would change backtest model semantics and downstream consumers, which is broader than this accepted review-lane rule.
  - Seller stock is still missing from current evidence and cannot be invented.
- Non-goals:
  - No code implementation.
  - No pass gate change.
  - No queue change.
  - No Google Sheets change.
  - No local DB change.
  - No scraper run.
  - No A script run.
  - No full F061 rescan.
  - No upstream enforcement change.

## Phase 4 Scope Guard
- Planning docs only.
- No code files changed.
- No tests were run because this ticket was planning only.
- No output CSVs were regenerated.
- No pass gate, queue, Google Sheets, local DB, scraper run, A script, full F061 rescan, or upstream enforcement was changed or run.

---

## Phase 3 Request
- Ticket: `F demand range controls BBP demand - Phase 3 triage integration`
- Integrate approved demand-range rule outcomes into F021 New Product Review triage output.
- Keep this triage-only. Do not change upstream pass gates, queues, Google Sheets, local DB, scraper runs, A scripts, or F061.

## Phase 3 What Changed
- Modified triage builder:
  - `scripts/one_off/F021_build_new_product_review_fail_triage.py`
- Modified focused tests:
  - `tests/test_f021_build_new_product_review_fail_triage.py`
- Rebuilt triage output:
  - `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- Updated ticket response record:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`

## Phase 3 Behavior Added
- Added demand columns to F021 output:
  - `demand_conflict_code`
  - `demand_recommended_action`
  - `demand_evidence_source`
  - `demand_supporting_codes`
- Approved outcomes now map as:
  - `amazon_blank_bbp_high` -> `remove_from_clean_pass`
  - `amazon_50_bbp_inflated` -> `remove_from_clean_pass`
  - `amazon_50_bbp_warn` -> `manual_review`
  - `weak_uk_review_confirms_demand_risk` -> supporting confidence reducer
  - `seller_stock_missing_for_demand_check` -> `targeted_rescan_needed` when it is the primary demand outcome
  - `amazon_50_bbp_reasonable` -> no fail by itself
- Manual fail memory still wins as the primary `fail_type`.

## Phase 3 Test Results
- `python -m py_compile scripts/one_off/F021_build_new_product_review_fail_triage.py tests/test_f021_build_new_product_review_fail_triage.py`
  - Passed.
- `pytest tests/test_f021_build_new_product_review_fail_triage.py -q`
  - Passed: `8 passed in 0.87s`.
- `python scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - Passed and wrote latest triage CSV.

## Phase 3 Output Path
- `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`

## Phase 3 Row Counts
- Total triage output rows: `3248`
- Count by `fail_type`:
  - `type_1_data_or_calc`: `1094`
  - `type_2_known_policy_or_memory`: `1`
  - `type_3_missing_evidence_rescan_needed`: `2153`
- Unclassified rows: `0`

## Phase 3 Demand Action Counts
- Primary `demand_recommended_action` counts in triage output:
  - `allow_if_other_checks_pass`: `3144`
  - `manual_review`: `10`
  - `remove_from_clean_pass`: `94`
- Supporting demand evidence counts:
  - Rows supporting `seller_stock_missing_for_demand_check`: `104`
  - Rows supporting `weak_uk_review_confirms_demand_risk`: `30`

## Phase 3 B0C8C3JF9X
- Final primary triage classification:
  - `fail_type`: `type_2_known_policy_or_memory`
  - `fail_reason_code`: `review_memory_fail_decision`
- Demand primary:
  - `demand_conflict_code`: `amazon_blank_bbp_high`
  - `demand_recommended_action`: `remove_from_clean_pass`
- Demand supporting codes:
  - `amazon_blank_bbp_high`
  - `seller_stock_missing_for_demand_check`
  - `weak_uk_review_confirms_demand_risk`

## Phase 3 Scope Guard
- Triage-only integration.
- No upstream enforcement changed.
- No pass gate changed.
- No queue changed.
- No Google Sheets write made.
- No local DB change made.
- No scraper run made.
- No A script run made.
- No full F061 rescan run made.

---

## Phase 2 Request
- Ticket: `F demand range controls BBP demand - Phase 2 sample review pack`
- Build a human-review sample pack from the Phase 1 audit output so thresholds can be approved before any upstream pass-gate change.
- Do not change pass gates, queues, Google Sheets, local DB, scraper runs, A scripts, or F061.

## Phase 2 What Changed
- Created one-off sample pack script:
  - `scripts/one_off/F024_build_demand_range_review_sample_pack.py`
- Created focused test file:
  - `tests/test_f024_build_demand_range_review_sample_pack.py`
- Wrote latest sample pack output:
  - `out/analysis_reports/f_demand_range_review_sample_pack_latest.csv`
- Wrote latest sample summary output:
  - `out/analysis_reports/f_demand_range_review_sample_summary_latest.csv`
- Updated ticket response record:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`

## Phase 2 Scope Guard
- Review-pack only.
- No upstream enforcement changed.
- No pass gate changed.
- No queue changed.
- No Google Sheets write made.
- No local DB change made.
- No scraper run made.
- No A script run made.
- No full F061 rescan run made.
- One-off script remains in `scripts/one_off/` and is not imported by daily loops.

## Phase 2 Test Results
- `python -m py_compile scripts/one_off/F024_build_demand_range_review_sample_pack.py tests/test_f024_build_demand_range_review_sample_pack.py`
  - Passed.
- `pytest tests/test_f024_build_demand_range_review_sample_pack.py -q`
  - Passed: `8 passed in 0.77s`.
- `python scripts/one_off/F024_build_demand_range_review_sample_pack.py`
  - Passed and wrote latest sample and summary CSVs.

## Phase 2 Output Paths
- Sample pack:
  - `out/analysis_reports/f_demand_range_review_sample_pack_latest.csv`
- Summary:
  - `out/analysis_reports/f_demand_range_review_sample_summary_latest.csv`

## Phase 2 Summary Metrics
- `input_audit_rows`: `3456`
- `output_sample_rows`: `131`
- `rows_remove_from_clean_pass`: `92`
- `rows_manual_review`: `10`
- `rows_strengthen_demand_risk_action`: `10`
- `rows_targeted_rescan_needed`: `10`
- `rows_allow_if_other_checks_pass_sampled`: `9`
- `b0c8c3jf9x_included`: `yes`
- `unclassified_rows`: `0`

## Phase 2 B0C8C3JF9X
- Included: `yes`
- Included rows:
  - `amazon_blank_bbp_high` with `remove_from_clean_pass`
  - `weak_uk_review_confirms_demand_risk` with `strengthen_demand_risk_action`

## Phase 2 Evidence Note
- The Phase 1 audit input does not include a `title` column, so the Phase 2 output includes the required `title` column but leaves current title values blank instead of inventing data.
- Seller stock data was not invented or backfilled.
- User could not reasonably work from the raw CSV, so a plain-English decision brief was added:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/DECISION_BRIEF.md`

---

## Request
- Ticket: `F demand range controls BBP demand - Phase 1 audit only`
- Build a read-only audit comparing Amazon visible demand range against BBP/backtest demand.
- Do not change pass gates, queues, Google Sheets, local DB, scraper runs, A scripts, or F061.

## What Changed
- Created one-off audit script:
  - `scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`
- Created focused test file:
  - `tests/test_f023_build_demand_range_bbp_conflict_audit.py`
- Wrote latest audit output:
  - `out/analysis_reports/f_demand_range_bbp_conflict_audit_latest.csv`
- Updated ticket response record:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/RESPONSE.md`

## Scope Guard
- No pass gate changed.
- No queue changed.
- No Google Sheets write made.
- No local DB change made.
- No scraper run made.
- No A script run made.
- No full F061 rescan run made.
- One-off script remains in `scripts/one_off/` and is not imported by daily loops.

## Test Results
- `python -m py_compile scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py tests/test_f023_build_demand_range_bbp_conflict_audit.py`
  - Passed.
- `pytest tests/test_f023_build_demand_range_bbp_conflict_audit.py -q`
  - Passed: `9 passed in 5.54s`.
- `python scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`
  - Passed and wrote latest audit CSV.

## Audit Totals
- Pass review input rows audited: `266`
- Near-miss review input rows audited: `3056`
- Total input rows audited: `3322`
- Output audit rows: `3456`
- Unclassified output rows: `0`

## Count By demand_conflict_code
- `amazon_50_bbp_inflated`: `10`
- `amazon_50_bbp_reasonable`: `16`
- `amazon_50_bbp_warn`: `10`
- `amazon_blank_bbp_high`: `84`
- `amazon_blank_bbp_low`: `3202`
- `seller_stock_missing_for_demand_check`: `104`
- `weak_uk_review_confirms_demand_risk`: `30`

## Count By recommended_action
- `allow_if_other_checks_pass`: `3218`
- `manual_review`: `10`
- `remove_from_clean_pass`: `94`
- `strengthen_demand_risk_action`: `30`
- `targeted_rescan_needed`: `104`

## B0C8C3JF9X Classification
- Present in current artifacts: `yes`
- Primary demand conflict code: `amazon_blank_bbp_high`
- Additional evidence codes:
  - `seller_stock_missing_for_demand_check`
  - `weak_uk_review_confirms_demand_risk`
- Stored values:
  - Amazon demand signal: blank
  - Amazon demand range: `0-49`
  - BBP units: `1017`
  - Expected units next 30 days: `813.6`

## New Data Before Enforcement
- Main Amazon-vs-BBP demand rule does not require new data.
- Seller-stock enforcement requires new data because no seller stock count column was found in the current stored sources.
- Rule requiring new data before enforcement:
  - `seller_stock_missing_for_demand_check`

## Evidence Baseline
- `EVIDENCE_BASELINE.md` was not changed because the currently recorded source counts still match current artifacts:
  - Pass review rows: `266`
  - Scrape evidence rows: `4397`
  - Backtest summary rows: `2358`
  - Review event rows: `1`
