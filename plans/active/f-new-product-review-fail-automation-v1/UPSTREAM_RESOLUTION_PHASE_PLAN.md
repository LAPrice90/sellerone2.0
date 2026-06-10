# Upstream Resolution Phase Plan

Date: 2026-05-19
Plan owner: F feeder / New Product Review
Source evidence:
- `out/systems/F/inbox/feeder_review_events.csv`
- `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- `plans/active/f-new-product-review-fail-automation-v1/FIX_LIST.md`

## Purpose
This plan explains how to stop the same bad products from reaching New Product Review as clean passes.

The simple picture is a factory line:
- supplier file comes in
- the system tries to match it to an Amazon product
- the scanner collects seller, demand, review, and profit evidence
- the pass gate decides whether the row is safe enough for review
- New Product Review sees only the rows that made it through

The fix should happen as early as possible on that line. If a supplier row is the wrong product, it should be stopped at the identity gate. If Amazon or the brand controls the listing, it should be stopped at the seller gate. If profit is too thin, it should be stopped at the profit gate. New Product Review should not be the place where these obvious cases are discovered for the first time.

## Guardrails
- Do not change Google Sheets.
- Do not write to the local Product DB.
- Do not run a broad live rescan without an approved F-owned proof window.
- Do not turn missing evidence into a hard fail. Missing evidence should become a hold or targeted rescan.
- Do not bury the user feedback in free text only. Every repeated reason needs a reason code.
- Every implemented rule needs a focused test, a local output proof, and a count reconciliation.

## Current Evidence Summary
- Review feedback rows studied: `21`
- Manual fail feedback rows: `18`
- Manual pass feedback rows: `3`
- Manual fail rows now matched in F021 triage: `18`
- Current F021 output rows: `2337`
- Current F021 unclassified rows: `0`

Main issue themes:
- Seller or ownership risk: Amazon-only, brand-owned, private-label, or restricted seller control.
- Product identity mismatch: supplier SKU or price-list product does not match the Amazon ASIN.
- Profit or upside weakness: profit too low, VAT/profit uncertainty, or suspicious profit caused by bad matching.
- Demand weakness or demand conflict: missing Amazon 50+ sold signal, low current sales signal, or demand estimate too optimistic.
- Review and variant risk: parent reviews look strong, but the actual UK variant is weak or recent reviews are poor.

## Phase 0 - Freeze Feedback And Add Reason Themes
Goal:
- Turn the 18 manual fails into a structured training set before changing pass rules.

Root-cause target:
- The system already stores your feedback, but the reasons are still mostly free text. That makes the feedback useful to a person, but weak for automatic rule building.

Work:
- Build a read-only feedback reason report.
- Classify each manual fail into one or more reason themes:
  - `seller_ownership_risk`
  - `product_identity_mismatch`
  - `profit_or_upside_weak`
  - `demand_signal_conflict`
  - `review_or_variant_risk`
  - `missing_evidence_needed`
- Keep the original note unchanged.
- Mark each theme as either:
  - `hard_rule_candidate`
  - `manual_review_candidate`
  - `evidence_capture_gap`

Likely files:
- New read-only script: `scripts/one_off/F030_build_review_feedback_reason_theme_report.py`
- New test: `tests/test_f030_build_review_feedback_reason_theme_report.py`
- Output: `out/analysis_reports/f_review_feedback_reason_theme_latest.csv`
- Summary: `out/analysis_reports/f_review_feedback_reason_theme_summary_latest.md`

Proof:
- `18/18` manual fail rows have at least one reason theme.
- `0` unclassified manual fail rows.
- The `3` manual pass rows are present as pass calibration examples, not fail rules.

Do not do yet:
- Do not change pass routing in this phase.
- Do not rescan.

## Phase 1 - Product Identity Mismatch Gate
Goal:
- Stop wrong-product rows before they reach the pass review pack.

Root-cause target:
- Some Amazon ASIN matches are not the same product as the supplier SKU or price-list row. This makes every later calculation look fake, because the system is doing profit and demand math on the wrong item.

User examples:
- Fluval row where the actual supplier product was a different filter cartridge.
- Carolina Herrera row where the supplier SKU text pointed to Calvin Klein.
- Lexar row where the supplier SKU text pointed to Joby.

Upstream owner:
- Supplier converter identity fields.
- F061 first-check identity evidence.
- F019 pass gate.

Work:
- Compare supplier product title, brand, barcode, pack size, and known SKU text against Amazon ASIN title and brand.
- Add a reason code such as `identity_supplier_asin_mismatch`.
- Route clear mismatches to hard reject or near miss before New Product Review.
- Route fuzzy or incomplete identity cases to manual review, not clean pass.

Likely files:
- Supplier converter output schemas where identity fields are prepared.
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Shared schema file: `scripts/flows/F/_schemas.py`
- Focused tests for F019 and F061 identity fields.

Proof:
- Known wrong-product examples are blocked before clean Pass.
- Clear good matches still pass identity checks.
- Output count shows identity mismatches separately from profit and seller-risk fails.

Success condition:
- New Product Review no longer receives clear wrong-product ASIN matches as clean passes.

## Phase 2 - Seller Ownership And Restricted Listing Gate
Goal:
- Stop Amazon-only, brand-owned, private-label, and restricted seller-control listings before they reach clean Pass.

Root-cause target:
- The system has some seller-count evidence, but it needs to treat seller ownership as a stronger upstream blocker when evidence is clear.

User examples:
- BOSS and Issey Miyake rows with one seller / Amazon-only style evidence.
- Plus-Plus where rank-1 seller looked like the brand.
- K18 and Estee Lauder style rows where brand/private or restriction risk is high.

Upstream owner:
- Webscrape / WebscraperS2 seller evidence capture.
- F061 scrape evidence schema.
- F019 pass gate.

Work:
- Use structured seller-rank fields already added for rank 1 to rank 3.
- Use dashboard YES/NO when logged in and available.
- Treat these as hard blockers when proven:
  - Amazon-only single seller.
  - Rank-1 seller matches brand or official store.
  - Dashboard says `NO` and historical seller count is below 2.
  - Restricted category plus seller collapse evidence.
- Treat these as manual-review cases when not fully proven:
  - low seller count but dashboard missing
  - seller owner unclear
  - FBA seller absent but FBM sellers exist

Likely files:
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `tests/test_f_legacy_webscrape_money_input.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`

Proof:
- Focused tests show Amazon-only and brand-owner rows leave clean Pass.
- A scoped F061 proof writes populated `bbp_seller_rank_1_name` and related fields.
- A dashboard proof writes `YES` or `NO`, not `LOGIN`.

Current blocker:
- Some live dashboard evidence is still blocked by BBP login returning `LOGIN`.

Success condition:
- Clear seller-control rows are removed upstream before New Product Review sees them.

## Phase 3 - Profit And Upside Gate
Goal:
- Stop low-upside or suspicious-profit rows before they reach clean Pass.

Root-cause target:
- A product can look attractive when profit is inflated, VAT is not accounted for, shipping is missing, or the ASIN is wrong. Profit should be calculated from fee-based net profit, not from simple break-even subtraction.

User examples:
- TePe rows where profit/upside looked too small or VAT/profit looked wrong.
- Suspiciously profitable rows where the product match also looked wrong.
- Low-sales game row where profit was not enough to justify trying.

Upstream owner:
- F071/backtest profit calculation.
- F027 profit audit.
- F019 pass gate.

Work:
- Continue using fee-based profit as the source of truth.
- Add pass-gate thresholds for:
  - minimum per-unit profit
  - minimum expected 30-day profit
  - minimum ROI
  - suspicious profit when identity confidence is weak
- Keep low-profit but valid rows as manual review or hold, not necessarily permanent hard reject.

Likely files:
- `scripts/one_off/F027_build_profit_formula_conflict_audit.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- F071/backtest files that produce profit evidence.
- Focused tests for profit routing.

Proof:
- Known low-upside examples route out of clean Pass.
- Known valid low-volume but acceptable examples can still route to manual review or small test-buy pass.
- Profit evidence includes the formula code used.

Success condition:
- Clean Pass no longer contains rows where the only appeal is fake or too-thin profit.

## Phase 4 - Demand Confidence Gate
Goal:
- Stop rows where current demand evidence does not support the system's expected-sales number.

Root-cause target:
- The system can over-trust historical BBP demand when the current Amazon page does not show enough current sales signal.

User examples:
- PowerA row where Amazon showed no `50+ sold` signal but the system estimated high demand.
- Low-selling rows where a small test might be acceptable, but a confident pass is too strong.

Upstream owner:
- Webscrape demand evidence.
- F023 demand audit.
- F019 pass gate.

Work:
- Keep `missing Amazon 50+ sold` as a demand-confidence limiter.
- If expected units are high but Amazon demand signal is blank, route to manual review or hold.
- Add seller stock count capture only if the scanner can store it reliably.
- If seller stock count is missing, keep it as an evidence gap, not a hard fail.

Likely files:
- `scripts/one_off/F023_build_demand_range_bbp_conflict_audit.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`

Proof:
- Known PowerA demand conflict is caught.
- Missing seller stock count remains Type 3 evidence gap.
- Demand-conflict counts are reported separately from low-profit rows.

Success condition:
- Clean Pass no longer treats weak current demand evidence as strong demand.

## Phase 5 - UK Variant And Review Quality Gate
Goal:
- Stop rows where the parent product looks strong, but the actual UK variant is weak or risky.

Root-cause target:
- Parent review count is not enough. The system needs to care about the exact variant and UK review evidence because that is what the buyer sees.

User examples:
- PowerA row with strong parent reviews but very weak UK variant evidence.
- MrBeast row with poor recent reviews and product-quality risk.

Upstream owner:
- WebscraperS2 review field capture.
- F061 scrape evidence schema.
- F026 UK review signal audit.
- F019 pass gate.

Work:
- Persist parent review count, matching variant review count, UK review count, global rating, and variant mode.
- Add hard blocks for very weak UK evidence where the listing depends on variant trust.
- Add manual-review routing for poor recent review patterns until sentiment capture is reliable enough to automate.

Likely files:
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F026_build_uk_review_signal_audit.py`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`

Proof:
- Weak UK variant examples route out of clean Pass.
- Review fields appear in `feeder_legacy_scrape_evidence_live.csv` after a scoped scrape proof.
- Parent-only review strength does not override weak UK variant evidence.

Success condition:
- New Product Review no longer needs to manually discover that a high parent-review listing has weak UK variant proof.

## Phase 6 - Central Pass Gate And Reason Priority
Goal:
- Put the accepted rules into the earliest shared pass decision point so all supplier runs behave consistently.

Root-cause target:
- If each report has its own interpretation, the system can still leak false passes. The pass gate needs one shared order of decisions.

Rule priority:
- Product identity mismatch.
- Seller ownership or restricted listing.
- Profit and upside weakness.
- Demand confidence conflict.
- UK variant and review weakness.
- Missing evidence hold or targeted rescan.
- Manual review memory.
- Clean pass.

Work:
- Make F019 or shared feeder pass logic apply the same reason order every time.
- Make each removed row carry one primary reason plus supporting reason fields.
- Keep F021 as the audit and reconciliation layer, not the main blocker.

Likely files:
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- Possible shared logic file if one already exists in F flow.
- `scripts/flows/F/price_list_manager/FPM150_build_completed_review_pack.py`
- Focused tests for each reason priority.

Proof:
- Rebuild review packs locally.
- Confirm known examples leave clean Pass for the correct primary reason.
- Confirm manual passes are not accidentally blocked by broad rules.
- Confirm no unclassified rows.

Success condition:
- F021 becomes a check on the pass gate, not a place where bad passes are first discovered.

## Phase 7 - Safe Rollout And F-Owned Proof
Goal:
- Prove the rules without disturbing live scanner ownership or writing to external systems.

Work:
- Run focused unit tests.
- Run read-only pack rebuilds.
- Compare old vs new pass counts and reason counts.
- Use a bounded F-owned proof window before any live scrape-dependent proof.
- Publish no Google Sheets writes and no Product DB writes.

Proof stages:
- Code fix applied.
- Isolated verification passed.
- Local artifact rebuild passed.
- F-owned scoped proof passed where live scanner evidence is required.
- Live loop verification confirmed only after the owner process produces the expected finalized artifacts.

Success condition:
- Clean Pass has fewer obvious false positives, and every removed row has an understandable reason.

## Phase 8 - UI Feedback Loop Upgrade
Goal:
- Make future feedback easier to learn from.

Root-cause target:
- Free-text notes are valuable, but the system should also capture the reason in a structured way at the moment of review.

Work:
- Add optional reason buttons or a selector to New Product Review decisions.
- Store reason codes alongside `review_note`.
- Keep free text as supporting detail.
- Add a feedback summary report after each completed supplier review batch.

Likely reason buttons:
- `wrong product`
- `seller controlled`
- `profit too weak`
- `demand too weak`
- `review or variant risk`
- `missing evidence`
- `other`

Proof:
- New review events include reason codes.
- Old free-text-only feedback remains readable.
- F021 can group feedback by reason without text guessing.

Success condition:
- Future false-pass learning is fast, structured, and visible.

## Recommended Implementation Order
1. Phase 0 - reason-theme report for the 18 matched manual fails.
2. Phase 1 - product identity mismatch gate.
3. Phase 2 - seller ownership gate.
4. Phase 3 - profit and upside gate.
5. Phase 4 - demand confidence gate.
6. Phase 5 - UK variant and review-quality gate.
7. Phase 6 - central pass-gate rule priority.
8. Phase 7 - safe rollout proof.
9. Phase 8 - UI reason-code upgrade.

## Definition Of Done
- All 18 current manual fails have structured themes.
- Accepted hard-rule themes are implemented upstream of New Product Review.
- Clean Pass rebuild has `0` unclassified rows.
- Every removed row has one clear primary reason.
- Known user examples route to the expected outcome.
- Focused tests pass.
- A rollback snapshot exists for changed files and outputs.
- No Google Sheets or Product DB writes occur unless explicitly approved later.

## Implementation Status - 2026-05-19
- Phase 0 status: implemented and rebuilt. The feedback reason-theme report has `21` feedback rows, `18` manual fail rows, `3` manual pass rows, and `0` unclassified manual fail rows.
- Phase 1 status: implemented in F019. Clear weak or mismatched identity evidence now routes out of clean Pass or into manual review.
- Phase 2 status: already implemented in F019 seller-history routing and kept in central priority order. Live seller/dashboard field population still needs the next scoped F061 proof.
- Phase 3 status: implemented in F019. F027 profit audit findings and low expected-profit evidence now route rows out of clean Pass or into manual review.
- Phase 4 status: active in F019. Demand conflicts continue to route separately, and missing seller stock remains an evidence gap.
- Phase 5 status: active in F019. UK review weakness continues to route separately.
- Phase 6 status: implemented in F019 central priority order.
- Phase 7 status: isolated proof passed, but live F019 proof is parked pending an F-owned source-window proof. The current default launch baseline points at an old run with no matching active row-state rows.
- Phase 8 status: implemented in the O UI and F review-event contract. Future New Product Review sends can store a structured `review_reason_code` beside the free-text note.
