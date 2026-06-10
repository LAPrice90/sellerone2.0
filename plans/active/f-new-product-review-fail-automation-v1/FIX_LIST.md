# Fix List

Date opened: 2026-04-23
Source review event: `o-ui-f-review-bfc06f252e51`
Source ASIN: `B0C8C3JF9X`
Source lane: `passes`

## Purpose
- Track repeated New Product Review fail reasons one by one.
- Turn user-submitted review notes into root-cause fixes, stored-evidence rules, or targeted rescan requirements.
- Keep each fix separately testable before applying broad automation.

## Status Key
- `proposed`: issue captured, not yet implemented.
- `implemented`: code changed and isolated tests passed.
- `needs proof`: code exists but live artifact proof is not current yet.
- `parked`: blocked by missing evidence or needs a future rescan.

## Fix 001 - Pass-lane review memory excluded from triage
- Status: implemented, needs next full proof bundle
- Submitted issue:
  - User failed a pass-lane ASIN, but original triage did not show it as Type 2 memory.
- Root cause:
  - F021 originally read near-miss rows only, so pass-lane review events had no source row to classify.
- Solution:
  - Read both pass and near-miss review packs in F021.
  - Include identity columns so reviewed rows can be traced by ASIN, candidate, supplier SKU, pack type, and batch.
- Expected output:
  - `B0C8C3JF9X` appears as `type_2_known_policy_or_memory`.
- Proof required:
  - F020 contract check passes.
  - F021 rebuild shows `type_2_known_policy_or_memory >= 1`.
  - B0C8C3JF9X row has `evidence_source=feeder_review_events:o-ui-f-review-bfc06f252e51`.

## Fix 002 - Demand estimate ignores missing Amazon 50+ sold signal
- Status: implemented, needs current artifact proof and rule tuning
- Planning folder:
  - `plans/active/f-new-product-review-fail-automation-v1/demand-range-controls-bbp-demand-v1/`
- Submitted issue:
  - Amazon page shows no 50+ sold signal, so likely fewer than 50 sold in the last 30 days.
  - Current system still estimated very high units for B0C8C3JF9X.
- Evidence seen:
  - `monthly_sold` is blank.
  - `demand_confidence_note=amazon_missing_bbp_capped_to_50`.
  - `expected_units_next_30d=813.6`.
- Root-cause theory:
  - Backtest/triage is allowing BBP historical demand to drive a high estimate even when current Amazon demand signal is missing.
- Solution:
  - Add deterministic rule `demand_conflict_missing_amazon_50_signal`.
  - Flag or fail rows where Amazon sold signal is missing and expected units are materially above the Amazon-visible demand cap.
- Proof required:
  - Count affected pass-lane and near-miss rows.
  - Confirm B0C8C3JF9X is caught by this rule.
  - Review sample rows before deciding whether rule is a hard fail or manual-review flag.

## Fix 003 - Price/history risk does not override pass result clearly enough
- Status: implemented, current artifact proof complete
- Planning folder:
  - `plans/active/f-new-product-review-fail-automation-v1/history-risk-overrides-pass-v1/`
- Submitted issue:
  - Price history showed Amazon or market history around/under break-even risk.
  - System still surfaced the product in passes.
- Evidence seen:
  - Review pack says `original_test_result=PASS`.
  - Review pack `commercial_note` starts with `Avoid`.
  - Scrape evidence has `history_recommendation=FAIL`.
  - Scrape evidence has `phase_recommendation=AVOID`.
  - Backtest summary has `recommendation=Avoid`.
- Root-cause theory:
  - Pass selection is not treating `history_recommendation=FAIL` or `phase_recommendation=AVOID` as a strong enough blocker.
- Solution:
  - Add deterministic rule `history_fail_overrides_pass`.
  - Make pass-lane rows with contradictory PASS/Avoid/FAIL evidence visible as Type 1 data or calculation issues until pass-gate logic is corrected upstream.
- Proof required:
  - Count affected pass-lane rows.
  - Confirm B0C8C3JF9X is caught by this rule when memory is not the primary reason.
  - Inspect pass-pack builder to decide whether the root fix belongs in F019, F073, or the pass-gate source.

## Fix 004 - Weak UK variant review signal is not blocking enough
- Status: implemented, current artifact proof complete; source-field propagation proof pending
- Planning folder:
  - `plans/active/f-new-product-review-fail-automation-v1/weak-uk-variant-review-signal-v1/`
- Submitted issue:
  - Parent review count is high, but the selected variant has weak UK review evidence.
  - B0C8C3JF9X had only 3 UK reviews according to stored evidence.
- Evidence seen:
  - `historical_uk_reviews=3`.
  - Existing live scrape evidence does not yet include all WebscraperS2 review fields in current CSV snapshot.
  - WebscraperS2 can capture `parent_total_reviews`, `matching_variant_reviews`, `global_ratings`, and `variant_mode`.
- Root-cause theory:
  - The scoring layer gives too much credit to broad review strength and not enough weight to UK variant-specific evidence.
- Solution:
  - Add deterministic rule `weak_variant_uk_review_signal`.
  - Propagate WebscraperS2 review detail fields into F061 scrape evidence and schema so future runs can separate parent, variant, global, and UK review evidence.
- Proof required:
  - Current artifact proof: rows caught using `historical_uk_reviews`.
  - Next scoped F061 proof: new propagated columns appear in `feeder_legacy_scrape_evidence_live.csv`.
  - Decide threshold for hard fail versus manual review.

## Fix 005 - Seller stock count is not stored
- Status: parked
- Submitted issue:
  - User saw seller stock of 42 from all sellers, which contradicted the high expected sales estimate.
- Evidence seen:
  - Seller stock count is not present in current pass review pack, near-miss pack, or scrape evidence artifact.
- Root cause:
  - Current scraper output does not persist seller stock count into the F review artifacts.
- Solution:
  - Treat stock-count-dependent checks as Type 3 targeted rescan requirements until the scraper captures and persists stock count.
  - Add a future scanner enhancement to capture seller stock count if available from the page/tool source.
- Proof required:
  - F021 reports `seller_stock_count_missing_rescan_required` count.
  - Future scoped rescan writes seller stock count to evidence artifact before any stock-count auto-fail is applied.

## Fix 006 - Manual fail reasons need structured reason codes
- Status: proposed
- Submitted issue:
  - User can explain fail reasons clearly, but notes are currently stored as free text.
- Root-cause theory:
  - Free-text notes are useful evidence, but weak for automated aggregation and repeat-fail detection.
- Solution:
  - Add a lightweight reason-code parser or UI reason-code selector for New Product Review sends.
  - Initial reason codes should include:
    - `demand_signal_conflict`
    - `history_price_risk`
    - `weak_uk_variant_reviews`
    - `missing_seller_stock_evidence`
- Proof required:
  - Review event output includes structured reason codes while retaining the original note.
  - Future triage can group submitted fails by reason code without text parsing.

## Fix 006A - Manual fail memory must remove rows from clean Pass upstream
- Status: implemented, current artifact proof complete
- Submitted issue:
  - User failed `1167948 / B007SJSX3M`, but it was still visible in clean Pass because F019 did not read review-memory events.
- Root cause:
  - F021 could classify fail memory after the fact, but F019 was the first UI-facing clean Pass pack builder and did not consult `out/systems/F/inbox/feeder_review_events.csv`.
- Solution:
  - F019 now reads latest review events when run from CLI.
  - Latest `fail` routes a Pass row out to near miss as `review_memory_fail`.
  - Latest `pass` overrides an older fail, so a row is not permanently blocked by stale memory.
  - Output rows now carry review-memory evidence columns:
    - `review_memory_event_id`
    - `review_memory_decision`
    - `review_memory_note`
    - `review_memory_event_utc`
- Proof completed:
  - `python -m py_compile scripts\one_off\F019_build_live_price_file_near_miss_pack.py scripts\one_off\F021_build_new_product_review_fail_triage.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py`
  - `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py -q` -> `51 passed`
  - `python scripts\one_off\F020_check_review_event_contract.py` -> `status=pass`, `row_count=13`
  - `python scripts\one_off\F019_build_live_price_file_near_miss_pack.py` -> `pass_review_rows=3`, `near_miss_review_rows=1619`, `review_memory_routed_remove_from_clean_pass_rows=9`
  - `python scripts\one_off\F021_build_new_product_review_fail_triage.py` -> `type_2_known_policy_or_memory=10`, `unclassified_rows=0`
  - `1167948 / B007SJSX3M` is absent from clean Pass and present as `review_memory_fail` with `evidence_source=feeder_review_events:o-ui-f-review-f1f8eba0bdf2`.

## Fix 006B - Brand-owner seller evidence needs structured competition-table capture
- Status: implemented, isolated proof complete; live scraper proof pending
- Submitted issue:
  - `1167948 / B007SJSX3M` looked like it should have failed because the top seller was the brand, but current machine capture did not prove the rank-1 seller repeatably.
- Root cause:
  - The scanner stored a flat list of seller names, but did not preserve structured rank-1/rank-2/rank-3 competition-table evidence.
- Solution:
  - Webscrape now parses the first 3 BBP competition-table rows into structured seller fields:
    - seller name
    - price
    - fulfilment
    - delivery
    - reviews
    - positive feedback percent
    - brand-match flag
    - row text
    - row HTML
  - F061 and F schema now propagate those fields into `feeder_legacy_scrape_evidence_live.csv`.
  - F019 now removes a Pass row if rank-1 seller or Amazon buy-box seller is proven to match the brand, even when the historical seller count is more than 1.
  - F061 health now includes `feeder_bbp_seller_rank_capture_runtime`, warning when scrape evidence is captured but rank-1 seller is not populated.
- Proof completed:
  - `python -m py_compile scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\_schemas.py scripts\one_off\F019_build_live_price_file_near_miss_pack.py scripts\one_off\F021_build_new_product_review_fail_triage.py tests\test_f_legacy_webscrape_money_input.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py`
  - `pytest tests\test_f_legacy_webscrape_money_input.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py -q` -> `63 passed`
  - F019/F021 rebuilds still pass and keep `1167948 / B007SJSX3M` blocked by review memory.
- Live proof still needed:
  - Next scoped F061 scrape must show populated `bbp_seller_rank_1_name` and related rank fields for at least one product before this can be called live-proven.

## Fix 007 - Profit inflated by break-even subtraction
- Status: implemented, isolated proof complete; partial live scraper proof observed; full refresh still running
- Planning folder:
  - `plans/active/f-new-product-review-fail-automation-v1/profit-calculation-correction-v1/`
- Submitted issue:
  - New Product Review showed inflated per-unit and monthly profit by treating `break_even` as if it were unit cost.
- Evidence seen:
  - Example ASIN `B0B7298QN6` had `avg_30_day_price=24.28`, `break_even=17.36`, and stored `profit_per_unit_30d=6.92`.
  - Stored value exactly matched `24.28 - 17.36`.
- Root cause:
  - Profit logic in upstream Webscrape and downstream F071 qualification used break-even subtraction instead of fee-based net-profit math.
- Solution:
  - Added shared F flow helper for fee-based net profit:
    - `sale_price_ex_vat = sale_price / (1 + vat_rate)`
    - `profit = sale_price_ex_vat - cost - fba_fee - referral_fee - digital_fee - est_shipping`
  - When sale price differs from referral-fee basis price, referral fee is recalculated by derived referral rate.
  - Updated F019 to attach and use corrected profit evidence from F027 audit so review packs stop presenting inflated `profit_per_unit_30d_gbp` as true profit when correction evidence exists.
  - Added read-only audit:
    - `scripts/one_off/F027_build_profit_formula_conflict_audit.py`
    - output: `out/analysis_reports/f_profit_formula_conflict_audit_latest.csv`
  - Proof status:
  - Isolated code + tests passed.
  - Audit generated with zero unclassified rows.
  - Review-pack row for `B0B7298QN6` now displays corrected per-unit profit and corrected expected 30-day profit.
  - Weekend F061 scan has now written new scraper rows after the code change.
  - Checked new scrape rows: `30`.
  - Rows still matching old formula `avg_30_day_price - break_even`: `0`.
  - Full scraper-owned refresh for all rows remains in progress.

## Fix 008 - Seller count needs dashboard YES/NO ownership signal
- Status: implemented, isolated proof complete; live scrape data population pending
- Submitted issue:
  - Low seller count alone can mean either a privately controlled brand or an opportunity where we could own the listing.
  - BuyBotPro dashboard YES/NO (`//*[@id="dashboardYesOrNo"]`) helps separate those cases.
- Root cause:
  - The scanner did not persist `dashboardYesOrNo`, so F019/F021 could only use historical seller count and Amazon/FBA channel evidence.
- Solution:
  - Capture `#dashboardYesOrNo` in WebscraperS2 output as `bbp_dashboard_yes_or_no`.
  - Propagate that field through F061 scrape evidence and schema.
  - Add review-pack output column `seller_history_dashboard_yes_or_no`.
  - Apply rule:
    - `NO` plus historical seller count `<2` = remove from clean Pass.
    - `NO` plus historical seller count `>=2` = manual review alert.
    - dashboard missing = keep existing channel-aware seller-history logic.
- Proof status:
  - Focused F019/F021/F061/schema tests passed.
  - Local F019 and F021 rebuilds passed.
  - Current live scrape evidence is pre-change for this field, so existing review rows show blank `seller_history_dashboard_yes_or_no` until a future scraper-owned row writes fresh evidence.
  - Read-only targeted rescan planner added:
    - `scripts/one_off/F028_build_dashboard_yes_no_rescan_plan.py`
    - output: `out/analysis_reports/f_dashboard_yes_no_rescan_plan_latest.csv`
  - Current planner result:
    - clean Pass rows selected now: `13`
    - near-miss rows deferred: `1324`
    - selected-now queue matches: `13`
    - full old scrape rows not selected for broad rescan.
  - Clean Pass rescan execution result:
    - 13 selected Pass rows were queued and run through F061.
    - F061 completed the scoped run.
    - The new `bbp_dashboard_yes_or_no` column was written to scrape evidence.
    - All 14 scrape evidence rows from the run have blank `bbp_dashboard_yes_or_no`.
    - Runtime log shows the element returned `LOGIN`, so the remaining issue is BBP/Seller dashboard access, not missing CSV storage.
    - Scraper was hardened to ignore non-YES/NO values so `LOGIN` is not stored as a false dashboard decision.

## Fix 009 - History rule may be too harsh on borderline Near Misses
- Status: implemented in read-only audit, upstream routing not yet changed
- Submitted issue:
  - User observed several reviewed products had good-looking history, suggesting current history failure rules may be too fussy.
- Root-cause theory:
  - `history_fail_phase_avoid` currently removes rows when `history_recommendation=FAIL` and `phase_recommendation=AVOID`.
  - The old rule is too blunt because it treats the full 365-day history too evenly.
  - User calibration showed that recent 30/90/180-day recovery should soften old bad history, unless Amazon has meaningful below-break-even pressure.
  - Low upside is a separate hold/fail reason, not the same as unstable history.
- Read-only audit:
  - Script: `scripts/one_off/F029_build_history_borderline_near_miss_audit.py`
  - Output: `out/analysis_reports/f_history_borderline_near_miss_audit_latest.csv`
  - Summary: `out/analysis_reports/f_history_borderline_near_miss_summary_latest.md`
- Implemented rule v1:
  - `history_recent_recovery_pass_candidate`: old weakness can be softened when recent evidence has recovered.
  - `history_amazon_below_be_fail_supported`: Amazon below our break-even remains a hard history risk.
  - `history_recent_weakness_fail_supported`: current 30/90/180-day weakness remains a fail/hold.
  - `borderline_but_limited_upside`: stable-but-too-close-to-BE cases stay separate from history instability.
- Proof completed:
  - `python -m py_compile scripts\one_off\F029_build_history_borderline_near_miss_audit.py tests\test_f029_build_history_borderline_near_miss_audit.py`
  - `pytest tests\test_f029_build_history_borderline_near_miss_audit.py -q` -> `12 passed`
  - `python scripts\one_off\F029_build_history_borderline_near_miss_audit.py` -> pass
- Current counts:
  - history conflict rows audited: `163`
  - `history_amazon_below_be_fail_supported`: `99`
  - `history_recent_weakness_fail_supported`: `26`
  - `history_recent_recovery_pass_candidate`: `19`
  - `borderline_but_limited_upside`: `10`
  - `history_fail_supported`: `9`
  - unclassified rows: `0`
- User-calibrated examples now match:
  - Pass history candidates: `B0016B20EG`, `B07NR39TXK`, `B0BYT7QCFB`, `B005G0YQDG`, `B09DYNQKRK`, `B07FFXXTMY`, `B001BQXPBS`, `B000C1UBQU`.
  - Keep failed/hold: `B08ZFKB8ZK`, `B0BWGXDCWJ`, `B0DSC9WHGG`, `B0949KH6B6`, `B00F0X9QFM`, `B084LC9S3X`.
- Next step:
  - Review the 19 `history_recent_recovery_pass_candidate` rows.
  - If accepted, move the v1 rule upstream into F019 so these rows can route to manual review instead of hard history near miss.

## Fix 010 - May feedback was recorded but missed by F021 triage
- Status: implemented, current artifact proof complete
- Submitted issue:
  - The feedback inbox contained newer May review decisions for DHB and Entertainment Trading, but the main F021 fail-triage output was still based on the older top-level review pack.
- Root cause:
  - F021 read only one top-level pass/near-miss review-pack pair by default.
  - Completed supplier review handoff packs live under `out/systems/F/price_list_manager/review_handoffs/`, so review-memory events for May supplier runs could be stored but not matched to source review rows.
- Solution:
  - F021 now reads completed handoff folders referenced by `active_supplier_id` and `active_run_id` in `feeder_review_events.csv`.
  - F021 keeps the normal top-level review-pack read, then combines and deduplicates matching handoff pack rows.
- Proof completed:
  - Backup snapshot created: `out/backups/new_product_review_feedback_triage_20260519T121717Z`
  - `python -m py_compile scripts\one_off\F021_build_new_product_review_fail_triage.py tests\test_f021_build_new_product_review_fail_triage.py` -> pass
  - `pytest tests\test_f021_build_new_product_review_fail_triage.py -q` -> `19 passed`
  - `python scripts\one_off\F020_check_review_event_contract.py` -> `status=pass`, `row_count=21`
  - `python scripts\one_off\F021_build_new_product_review_fail_triage.py` -> `unclassified_rows=0`
  - F021 loaded `2` handoff folders: DHB and Entertainment Trading.
  - F021 indexed `18` manual fail-memory rows.
  - All `18` manual fail feedback events now match triage rows as `type_2_known_policy_or_memory` / `review_memory_fail_decision`.
  - The `3` manual pass events remain outside fail triage, as expected.

## Current Priority Order
1. Fix 007 - Profit inflated by break-even subtraction (implemented, monitor scrape-refresh proof).
2. Fix 008 - Seller dashboard YES/NO capture and low-seller routing (implemented, wait for fresh scrape evidence population).
3. Fix 010 - May feedback handoff pack inclusion (implemented, proof complete).
4. Fix 002 - Demand estimate conflict.
5. Fix 003 - History FAIL or Avoid overriding pass.
6. Fix 004 - UK variant review weakness.
7. Fix 005 - Seller stock count capture or rescan route.
8. Fix 006 - Structured manual reason codes.

## Next Batch Recommendation
- Batch 002A:
  - Produce a counts report for the 18 matched manual fail feedback rows by reason theme.
  - Separate hard-rule candidates from evidence-capture gaps.
  - Do not change queue files.
  - Do not run a rescan.
- Batch 002B:
  - Decide which themes should become upstream auto-fail rules.
- Batch 002C:
  - Move accepted rules upstream into the earliest correct owner path.
