# Phase 4 Upstream Plan

## Status
- Ticket: F demand range controls BBP demand - Phase 4 upstream planning only.
- Status: planning complete.
- Scope: planning docs only.
- No code was changed in this ticket.
- No pass gate, queue, Google Sheets, local DB, scraper, A script, full F061 rescan, or upstream enforcement was changed or run.

## Phase 4 Question
Accepted demand-range outcomes are visible in F021 triage, but F021 is downstream of the clean Pass review pack. The Phase 4 question is where the accepted rules should move so future clean Pass packs do not include obvious demand-conflict rows.

The root-cause issue is not the F021 triage classification. The root-cause issue is that the clean Pass review pack is assembled before demand-range conflicts are considered.

## Files Inspected
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

## Field Provenance
- `expected_units_next_30d`
  - Produced in `scripts/flows/F/F073_build_backtest_summary.py`.
  - F073 uses F071 `price_qualified_units_monthly` when available and falls back to replay units.
  - F019 copies this value into the pass and near-miss review packs, with scrape-based fallback when the backtest value is missing.
- `backtest_decision_state`
  - Produced as `decision_state` in `scripts/flows/F/F073_build_backtest_summary.py`.
  - F019 copies it into the review pack as `backtest_decision_state`.
- `pass_reason_summary`
  - Produced in `scripts/one_off/F019_build_live_price_file_near_miss_pack.py` by `_pass_reason_summary`.
- `commercial_note`
  - Produced in `scripts/one_off/F019_build_live_price_file_near_miss_pack.py` by `_commercial_note`.

## Owner Path Recommendation
Recommended owner for the next implementation ticket: `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`.

Reason: F019 is the first place where the clean Pass review pack is actually created. It joins the screening row state, first checks, scrape evidence, and backtest summary, then writes:
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

The clean Pass inclusion decision happens in F019 when rows with `row_status == "pass"` are appended to the pass review output. Today that append does not check the accepted demand-range blockers. That is the earliest correct root-cause location for stopping demand-conflict rows from entering clean Pass.

## Why Not Other Owners
- `scripts/flows/F/F030_build_shared_feeder_pass_logic.py`
  - Too early. It classifies supplier rows before Amazon evidence, BBP units, backtest expected units, or visible Amazon demand are available.
- `scripts/flows/F/F071_build_backtest_input_view.py`
  - Owns backtest input demand and price qualification. A change here would alter the demand basis used by backtest replay, not just clean Pass lane assignment.
  - This may become a future model-semantics ticket if the business wants expected units capped by Amazon visible demand, but it is broader than the current accepted rule movement.
- `scripts/flows/F/F073_build_backtest_summary.py`
  - Owns backtest summary and `decision_state`. Changing it would change backtest decisions for all consumers of the summary, including flows that are not clean Pass pack creation.
  - The accepted Phase 3 mapping is a review-lane decision, not a backtest-model decision.
- `scripts/one_off/F017_build_pass_gate_review_pack.py`
  - Too late. It reviews pass-gate behavior after the clean Pass pack exists.
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
  - Not the owner of individual clean Pass row inclusion. It builds launch/readiness baseline metrics.
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`
  - Too late. It can make the issue visible, but solving clean Pass inclusion there would be downstream masking.

## Recommended Rule Placement
The accepted demand-range rules should change pass-pack lane assignment, not the backtest decision.

Recommended placement in F019:
- `amazon_blank_bbp_high`
  - Hard clean-Pass blocker.
  - Remove from clean Pass output and route to a review/fail lane with the demand conflict visible.
- `amazon_50_bbp_inflated`
  - Hard clean-Pass blocker.
  - Remove from clean Pass output and route to a review/fail lane with the demand conflict visible.
- `amazon_50_bbp_warn`
  - Manual-review blocker.
  - Remove from clean Pass output and route to manual review.
- `weak_uk_review_confirms_demand_risk`
  - Supporting confidence reducer only.
  - Record as supporting evidence, but do not block clean Pass by itself.
- `seller_stock_missing_for_demand_check`
  - Targeted rescan needed when seller stock evidence is required and missing.
  - Do not invent seller stock data.
- `amazon_50_bbp_reasonable`
  - Allow if all other checks pass.

This keeps the backtest model truthful while preventing a clean Pass review pack from presenting rows that the accepted rule says are not clean Pass candidates.

## Exact Proposed Code Touchpoints For Later Implementation
Primary implementation file:
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`

Proposed touchpoints:
- Add demand-range classification helpers near the existing review-pack helper functions:
  - parse Amazon visible demand from scrape evidence, including blank demand as range `0-49` and Amazon `50+` as floor `50`.
  - choose BBP/backtest comparison units from backtest `expected_units_next_30d` and scrape BBP demand fields without inventing values.
  - preserve the accepted Phase 3 rule mapping.
- Add explicit output columns to the pass and near-miss review packs if approved:
  - `demand_conflict_code`
  - `demand_recommended_action`
  - `demand_evidence_source`
  - `demand_supporting_codes`
- Apply the demand-range classification before the current pass append path for `row_status == "pass"`.
- For hard clean-Pass blockers, do not append the row to `pass_rows`.
- Route blocked pass rows into the review output with an explicit demand reason, for example:
  - `screening_fail_code`: `demand_range_block`
  - `screening_status_reason`: accepted demand conflict code
  - `review_action`: `remove_from_clean_pass`, `manual_review`, or `targeted_rescan_needed`
- Update the review summary metrics so removed pass rows and routed demand-review rows reconcile.
- Keep one-off code out of daily loop imports. If a shared helper is needed, create a normal F helper module under `scripts/flows/F/` and update both F019 and one-off audit tests to use it. Do not import F023 from a daily or shared path.

Possible supporting test touchpoints:
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `tests/test_o_ui_operator_view.py` if added columns affect the operator UI preview or report readers.
- A new focused demand helper test if the helper is moved to a shared F module.

Files not recommended for Phase 4 implementation:
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F030_build_shared_feeder_pass_logic.py`
- `scripts/one_off/F017_build_pass_gate_review_pack.py`
- `scripts/one_off/F021_build_new_product_review_fail_triage.py`

## Tests Required In Phase 4 Implementation
- Pass row with Amazon blank and BBP or expected units over 49 is excluded from clean Pass and routed with `amazon_blank_bbp_high`.
- Pass row with Amazon `50+` and BBP over 250 is excluded from clean Pass and routed with `amazon_50_bbp_inflated`.
- Pass row with Amazon `50+` and BBP 101-250 is excluded from clean Pass and routed as manual review with `amazon_50_bbp_warn`.
- `weak_uk_review_confirms_demand_risk` appears as supporting evidence and does not block clean Pass by itself.
- `seller_stock_missing_for_demand_check` is reported as missing evidence or targeted rescan needed; no seller stock value is invented.
- Amazon `50+` with BBP 50-100 remains allowed if other checks pass.
- Existing timeout and near-miss classifications still work.
- Output has no demand-blocked rows without a classification.
- B0C8C3JF9X, if present in the F019 inputs, does not remain in the clean Pass output after implementation and is visible in the routed review lane with supporting demand codes.
- Summary counts reconcile:
  - clean Pass output count decreases by the demand-blocked pass rows.
  - review/manual/demand-routed output count increases by the same rows.
  - no source audit file is modified.

## Proof Path For Later Implementation
Use existing artifacts and focused tests only. Do not run A scripts or a full F061 rescan.

Recommended commands for the later implementation ticket:
- `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py`
- `pytest tests/test_f019_build_live_price_file_near_miss_pack.py -q`
- `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py`

Required proof after the implementation run:
- Output path exists:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- Count by demand action.
- Count by lane after demand routing.
- Count of clean Pass rows removed by demand-range blocker.
- B0C8C3JF9X clean Pass presence check.
- B0C8C3JF9X routed review-lane classification if present.
- Reconciliation that removed clean Pass rows equal added demand-review rows.
- Confirmation that no pass gate, queue, sheet, DB, scraper run, A script, full F061 rescan, or upstream enforcement was changed or run.

## Risks
- F019 outputs are consumed by later review and operator views. Adding new columns is low risk for CSV readers that ignore extras, but tests should confirm the O UI reader still handles the files.
- Routing demand-blocked rows into the existing near-miss output needs a clear reason code so they are not confused with timeout-only near misses.
- Moving the rule into F071 or F073 would have broader effects on backtest semantics and downstream consumers. That should not be done unless a separate ticket approves model-level demand capping.
- Seller stock is still missing from current evidence. Any seller-stock enforcement needs new data before it can become a hard rule.
- Reusing F023 code directly from F019 would violate the one-off boundary if F019 is ever used by a repeated flow. Shared logic should live in a proper F helper module if reuse is needed.

## Non-Goals
- No code implementation in this ticket.
- No pass gate change in this ticket.
- No queue change.
- No Google Sheets change.
- No local DB change.
- No scraper run.
- No A script run.
- No full F061 rescan.
- No change to backtest decision state in this ticket.
- No invented seller stock data.

## Planning Conclusion
The next implementation ticket should put the accepted demand-range rule at the F019 clean Pass lane-assignment point. That is the earliest location that has all required evidence and directly owns whether a row enters the clean Pass review output. It avoids downstream masking because the row is stopped before the clean Pass pack is written, and it avoids overreaching into backtest model semantics before that broader change is explicitly approved.
