# F Review Pass To Amazon Listing V1 Coding Plan

## Goal
Bridge New Product Review `pass` decisions into a safe saved-SKU and Amazon listing draft pipeline.

Plain-English target:
- a scanner PASS does not create a listing
- a New Product Review `pass` creates a local intake draft
- the system reserves one stable seller SKU for that approved candidate
- Amazon draft and preview use that same reserved SKU
- Product DB promotion waits until Amazon acceptance plus read-back reconciliation

## Current Phase
Status: Product DB promotion gate is implemented and live-proven in dry-run mode for the 3 controlled submitted drafts

Implemented:
- Phase 1 - Contract Bridge
- Phase 2 - SKU Reservation
- Phase 3 - Draft Builder
- UI bridge - Approved For Amazon Listing lane
- Phase 4 - Amazon validation preview
- Phase 5 - Guarded live submit
- Phase 6 - Amazon read-back reconciliation
- Phase 7 - Brand restriction pre-check and invoice-required approval queue
- Phase 8 - O-owned Product DB promotion candidate and event-staging gate

Current phase:
- isolated verification passed
- local UI approval can move a draft to `ready_for_amazon_preview`
- approved preview drafts can run Listings Items `mode=VALIDATION_PREVIEW`
- preview issues are recorded locally
- exact approved draft IDs can be submitted live through F094 only with explicit live flags
- submitted SKUs can be read back through F095 and reconciled through F096
- submitted or pre-submit drafts can be checked through F097 Listings Restrictions API
- approval-required rows are held in F098 Brand Approval Queue and excluded from Product DB/repricer eligibility
- O430 builds Product DB promotion candidates only from `confirmed_product_db_eligible` Amazon reconciliation rows
- O431 defaults to dry-run and cannot stage Product DB create events unless both explicit promotion flags are passed
- Product DB and Google Sheets writes have not run

Next phase to implement:
- enter or repair the missing Product Listing Profile fields for Kensington and JVC on the user-facing Product Listing Profile Review page, then rerun O430 and only stage O431 Product DB create events after explicit approval

## Allowed Files For Current Execution Block
- `scripts/api/spapi_owner.py`
- `scripts/api/amazon_listings_items.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `scripts/flows/F/F091_reserve_amazon_listing_skus.py`
- `scripts/flows/F/F092_build_amazon_listing_drafts.py`
- `scripts/flows/F/F093_run_amazon_listing_preview.py`
- `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/O430_build_product_db_promotion_candidates.py`
- `scripts/flows/O/O431_stage_product_db_create_events.py`
- `config/feeder/amazon_listing_defaults.csv`
- `tests/test_amazon_listings_items.py`
- `tests/test_f090_build_amazon_listing_intake.py`
- `tests/test_f091_reserve_amazon_listing_skus.py`
- `tests/test_f092_build_amazon_listing_drafts.py`
- `tests/test_f093_run_amazon_listing_preview.py`
- `tests/test_f094_submit_amazon_listing_drafts.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_o000_paths_and_schemas.py`
- `tests/test_o430_o431_product_db_promotion.py`

Do not edit in this current block:
- Google Sheets write scripts
- Product DB sheet writers
- A/B/E/H scheduler or loop ownership files

## Inputs
- `out/systems/F/inbox/feeder_review_events.csv`
- completed FPM150 review handoff manifest
- completed pass review pack referenced by the manifest
- `out/product_db_preview.csv` for duplicate SKU checks only
- listing snapshots for duplicate SKU checks only
- `config/feeder/amazon_listing_defaults.csv`

## Outputs
- `out/systems/F/live/amazon_listing_intake_live.csv`
- `out/systems/F/live/amazon_listing_sku_reservations_live.csv`
- `out/systems/F/live/amazon_listing_drafts_live.csv`
- `out/systems/F/live/amazon_listing_holds_live.csv`
- `out/systems/F/history/amazon_listing_draft_events.csv`
- `out/systems/F/history/amazon_listing_preview_events.csv`
- `out/systems/F/history/amazon_listing_submission_events.csv`
- `out/systems/F/live/amazon_listing_preview_issues_live.csv`
- `out/systems/F/health/amazon_listing_health.csv`
- `out/systems/O/live/product_db_promotion_candidates_live.csv`
- `out/systems/O/live/product_db_promotion_holds_live.csv`
- `out/systems/O/live/product_db_promotion_health.csv`

## Hard Boundaries
- Amazon preview calls must use Listings Items `mode=VALIDATION_PREVIEW`.
- Amazon live submit must use F094 with exact draft IDs plus explicit live flags.
- Amazon live submit must not send preview-only `includedData`.
- No Product DB write in the current execution block.
- No Google Sheets write in the current execution block.
- Do not treat scanner PASS as listing approval.
- Do not treat New Product Review `pass` as live submit approval.
- Do not write `out/product_db_preview.csv` directly.
- O431 must stay dry-run unless `--stage-events --confirm-product-db-promotion` are both passed after user approval.

## Tests And Isolated Proof
Run focused tests only:
- `pytest tests/test_f090_build_amazon_listing_intake.py`
- `pytest tests/test_f091_reserve_amazon_listing_skus.py`
- `pytest tests/test_f092_build_amazon_listing_drafts.py`

Minimum proof:
- raw scanner PASS alone creates 0 intake rows
- running supplier scan creates 0 intake rows
- completed review pack plus latest `pass` event creates 1 intake row
- later `fail` after earlier `pass` blocks intake/draft creation
- SKU reservation is stable across reruns
- duplicate seller SKU in Product DB blocks reservation
- duplicate seller SKU in listing snapshot blocks reservation
- draft builder creates one draft from one valid reserved intake row
- rerun updates same draft, no duplicate
- missing ASIN/cost/defaults create hold rows

Draft-only isolated proof:
- Command: `pytest tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py`
- Result: 14 passed in the first-block run; the same F bridge files are also covered by the latest UI bridge proof below.
- Note: pytest returned success; Windows emitted a temp-directory cleanup permission warning after the test run completed.

Latest UI bridge proof:
- Checked at UTC: 2026-05-01T10:33:30Z
- Command: `pytest tests/test_o_ui_operator_view.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py`
- Result: 68 passed
- Note: pytest returned success; Windows emitted a temp-directory cleanup permission warning after the test run completed.

Earlier preview-only proof:
- Checked at UTC: 2026-05-01T10:47:01Z
- Command: `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_o_ui_operator_view.py`
- Result: 74 passed
- Note: pytest returned success; Windows emitted a temp-directory cleanup permission warning after the test run completed.

## Runtime Proof
Code fix applied and isolated verification passed.

Live Amazon verification:
- Amazon validation preview is proven for the three controlled drafts.
- Amazon live submit is proven for the same three controlled drafts.
- Amazon read-back confirmed Kensington and JVC as Product-DB-eligible.
- Embryolisse is parked because Amazon brand approval is required.

Live Product DB promotion dry-run:
- Checked at UTC: 2026-05-01T13:10:43Z
- Command: `python scripts\flows\O\O430_build_product_db_promotion_candidates.py`
- Result: `candidate_rows=2;ready_rows=0;held_rows=2;hold_rows=3;blocked_rows=1`.
- Command: `python scripts\flows\O\O431_stage_product_db_create_events.py`
- Result: `stage_not_run;eligible_rows=0;staged_rows=0;held_rows=0;failed_rows=0`.
- Kensington `NP-STO-E149D07A` and JVC `NP-STO-3502B107` are Amazon-clear but held because Product DB profile fields are missing: purchase pack size, sold pack size, supplier case quantity, valid order step, MOQ, VAT rate, and VAT confirmation.
- Embryolisse `NP-STO-B1FFE9D8` remains parked/blocked by brand approval risk.
- `out/systems/O/inbox/product_db_edit_events.csv` was not created by the dry run.

UI correction after operator feedback:
- Product Listing Profile Review now collects the Product DB/profit setup fields before the product can move on.
- The user must complete COO, purchase pack size, sold pack size, VAT source/rate, VAT confirmation, supplier case quantity, order step, MOQ, target margin, starting price, quantity, and condition in the review page.
- F090 carries those fields into listing intake, F092 carries them into listing drafts, and O430 uses them when building Product DB promotion candidates.

Destination schema guard after Product DB header check:
- O431 now checks whether `out/product_db_preview.csv` has every destination column needed to preserve the full user-entered product profile.
- If destination columns are missing, O431 writes `product_db_destination_schema=fail` into `product_db_promotion_health` and refuses to stage Product DB create events.
- Current live Product DB preview is missing:
  - `supplier_sku`
  - `barcode`
  - `order_qty_mode`
  - `sell_pack_qty`
  - `supplier_case_qty`
  - `supplier_case_multiple`
  - `valid_order_step`
  - `repack_required`
  - `bundle_required`
- Product DB preview also has duplicate column `last_updated_A003`.
- Google Sheets and `out/product_db_preview.csv` were not changed.

Latest Product DB promotion focused proof:
- Command: `pytest tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py tests/test_o420_product_database_edit_ui.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f097_f098_brand_approval_queue.py`
- Result: `24 passed in 3.58s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Latest profile-field regression proof:
- Command: `pytest tests/test_o_ui_operator_view.py tests/test_f090_build_amazon_listing_intake.py tests/test_f092_build_amazon_listing_drafts.py tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py`
- Result: `82 passed in 15.49s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Latest Product DB destination schema proof:
- Command: `pytest tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py tests/test_o420_product_database_edit_ui.py`
- Result: `20 passed in 2.42s`.
- Live O430 dry-run: `candidate_rows=2;ready_rows=0;held_rows=2;hold_rows=3;blocked_rows=1`.
- Live O431 dry-run: `stage_not_run;eligible_rows=0;staged_rows=0;schema_missing_fields=9`.
- `product_db_edit_events.csv` was not created.

## Monitoring Target
No passive live monitoring is active for this block.

For the next read-back phase, monitor:
- `out/systems/F/health/amazon_listing_health.csv`
- `out/systems/F/live/amazon_listing_drafts_live.csv`
- Amazon preview/submission event files

Default future cadence:
- first check at +5 minutes
- second check at +10 minutes
- then every +15 minutes
- stop at +60 minutes unless the later phase plan changes this

## Automatic Next Step After Current Execution Block
Focused tests passed, preview passed, and guarded live submit was accepted for the three controlled drafts:
- continue with Amazon read-back reconciliation.
- keep Product DB and Google Sheets writes blocked until read-back confirms the submitted listings.

If tests fail:
- fix the root cause in the earliest failing stage, then rerun the same focused tests.

If Product DB promotion is requested before Amazon reconciliation exists:
- keep it blocked and build the reconciliation step first.

## Next Execution Block - Amazon Read-Back Reconciliation
Status: implemented and live proof completed for the three submitted drafts

Reason:
- Amazon accepted the live submit requests, but that means Amazon accepted them for processing.
- Product DB promotion must wait until read-back confirms each seller SKU exists on the expected ASIN and marketplace with no blocking issues.

Allowed files for next block:
- `scripts/api/amazon_listings_items.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F095_check_amazon_listing_submission_status.py`
- `scripts/flows/F/F096_reconcile_amazon_listing_submissions.py`
- `tests/test_amazon_listings_items.py`
- `tests/test_f095_check_amazon_listing_submission_status.py`
- `tests/test_f096_reconcile_amazon_listing_submissions.py`

Completion proof for next block:
- read back all three submitted SKUs from Amazon
- confirm seller SKU, ASIN, marketplace, and no blocking issues
- write a truthful reconciliation health row
- keep Product DB and Google Sheets writes blocked

Implementation proof - 2026-05-01T12:18:58Z:
- Added F095 `scripts/flows/F/F095_check_amazon_listing_submission_status.py` to read submitted SKUs back from Listings Items API.
- Added F096 `scripts/flows/F/F096_reconcile_amazon_listing_submissions.py` to convert read-back events into Product-DB-eligibility state.
- Added read-back/reconciliation contracts:
  - `amazon_listing_readback_events`
  - `amazon_listing_reconciliation_live`
- Live read-back command used the three exact submitted draft IDs and made three Listings Items GET calls.
- Live read-back result: `eligible_rows=3;attempted_rows=3;confirmed_rows=2;blocked_rows=1;failed_rows=0`.
- Reconciliation result: `reconciliation_rows=3;confirmed_rows=2;blocked_rows=1;pending_rows=0`.
- Product DB and Google Sheets writes did not run.

Read-back result by SKU:
- Kensington `NP-STO-E149D07A` / `B09FQCWKPW`: `confirmed_product_db_eligible`.
- JVC `NP-STO-3502B107` / `B082NMTZC2`: `confirmed_product_db_eligible`.
- Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`: blocked by Amazon issue `ERROR 18304 You need approval to list this brand.`

Health after read-back:
- `amazon_listing_reconciliation=fail`
- reason: `confirmed_rows=2;blocked_rows=1;pending_rows=0`

Focused proof:
- Command: `pytest tests/test_amazon_listings_items.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f000_paths_and_schemas.py tests/test_f093_run_amazon_listing_preview.py tests/test_f094_submit_amazon_listing_drafts.py`
- Result: `22 passed in 3.42s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Next execution block:
- Product DB promotion may proceed only for the two `confirmed_product_db_eligible` SKUs.
- Embryolisse must stay blocked until Amazon brand approval is resolved or the product is explicitly rejected/parked.

## Completed Execution Block - Brand Restriction And Invoice Requirement Gate
Status: implemented and live proof completed for the three submitted drafts

Reason:
- Amazon can accept a listing request for processing and still later block the listing because the brand requires approval.
- Some approvals clear by trying the Seller Central approval flow.
- Other approvals require an invoice for a minimum quantity, such as 10, 50, 100, or more units.
- The system must know the required invoice quantity before Product DB promotion, repricer eligibility, or buying signals.

Plain-English rule:
- If Amazon says brand approval is required, the product is not ready to sell.
- If the required invoice quantity is too risky, fail or park the product.
- If the required invoice quantity is acceptable, keep the candidate in a separate approval queue until invoice proof is available and Amazon approval clears.
- Do not put approval-blocked SKUs into the normal Product DB or repricer feed.

Research basis:
- Listings Restrictions API can check whether restrictions prevent listing creation and can return next-step links when approval is required.
- Amazon docs say sellers should follow the returned link to apply for approval.
- No public SP-API operation was found for uploading brand-approval invoices or completing the Seller Central selling application directly.

New contracts:
- `out/systems/F/live/amazon_listing_restrictions_live.csv`
- `out/systems/F/history/amazon_listing_restriction_events.csv`
- `out/systems/F/live/brand_approval_queue_live.csv`
- `out/systems/F/history/brand_approval_decision_events.csv`

Implemented UI:
- Added `Brand Approval Queue` page in O400.
- The page records fail, park, try Seller Central, invoice planned, invoice uploaded, and approval recheck decisions.
- Invoice quantity, unit cost, total risk, invoice reference, and notes are stored in `brand_approval_decision_events`.

UI fields:
- restriction pre-check status
- approval required flag
- approval reason code
- approval reason message
- Seller Central approval link, if returned by Amazon
- required invoice quantity
- estimated invoice unit cost
- estimated invoice total risk
- approval decision: `fail_now`, `park`, `try_seller_central`, `invoice_planned`, `invoice_uploaded`, `approved_recheck`
- approval note
- cooldown/recheck date

Scenario rules:
- `restriction_clear`: continue to draft, preview, live submit, read-back, then Product DB promotion.
- `approval_required_no_invoice_seen`: show Seller Central approval link and let the user try approval manually; keep out of Product DB and repricer.
- `approval_required_low_invoice_qty`: if the user accepts the risk, create an approval-queue row and buying/invoice requirement, but still keep out of Product DB and repricer until approval clears.
- `approval_required_high_invoice_qty`: fail or park the product; default recommendation is park/fail when invoice risk is above the user's threshold.
- `already_submitted_then_blocked`: keep the local SKU reservation and Amazon read-back evidence, but mark the row `blocked_brand_approval`; do not promote to Product DB. Delete from Amazon only if clutter becomes a real operating problem.
- `brand_unlocked_later`: rerun restriction check when a new product from the same brand appears, when the user uploads an invoice, or on a low-cadence watchlist check.

Cooldown rule:
- Failed due to high invoice requirement: default `365` days or until the brand appears again with a cheaper qualifying product.
- Parked for possible brand unlock: check only on new same-brand candidate, invoice upload, or manual recheck.
- Invoice planned: check after invoice is uploaded and again after the Seller Central application is submitted.
- Never recheck daily by default.

Repricer boundary:
- The repricer must not treat an approval-blocked SKU as sellable stock.
- Repricer eligibility must require Product DB active status plus Amazon reconciliation success plus no active restriction.
- The approval queue may create a buying signal for the required invoice quantity, but that is not a repricing signal.

Implementation files for next block:
- `scripts/api/amazon_listings_restrictions.py`
- `scripts/flows/F/F097_check_amazon_listing_restrictions.py`
- `scripts/flows/F/F098_build_brand_approval_queue.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/_schemas.py`
- `tests/test_amazon_listings_restrictions.py`
- `tests/test_f097_f098_brand_approval_queue.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_f094_submit_amazon_listing_drafts.py`
- `tests/test_f095_f096_amazon_listing_readback.py`
- `tests/test_f000_paths_and_schemas.py`

Proof:
- restriction check runs before live submit
- `APPROVAL_REQUIRED` rows are blocked before Product DB promotion
- invoice-required rows store quantity and estimated risk
- user can fail, park, try approval, plan invoice, upload invoice, or request approval recheck from the Brand Approval Queue page
- parked rows are not checked daily
- repricer/Product DB eligibility excludes approval-blocked SKUs

Implementation proof - 2026-05-01T12:54:45Z:
- F097 live restriction check on the three exact draft IDs returned `checked_rows=3;clear_rows=2;approval_required_rows=1;restricted_rows=0;failed_rows=0`.
- F098 built one Brand Approval Queue row:
  - Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`
  - `approval_status=approval_required`
  - `reason_code=APPROVAL_REQUIRED`
  - Seller Central approval link captured from Amazon.
- F096 reconciliation still returned `confirmed_rows=2;blocked_rows=1;pending_rows=0`.
- The blocked reconciliation row now references `brand_approval_queue_live` and uses `block_reason=approval_required`.
- F094 live submit now blocks known active brand approval / restriction rows before calling the live submit API.
- Product DB and Google Sheets writes did not run.

Focused proof:
- Command: `pytest tests/test_o_ui_operator_view.py tests/test_amazon_listings_restrictions.py tests/test_f097_f098_brand_approval_queue.py tests/test_f094_submit_amazon_listing_drafts.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f000_paths_and_schemas.py`
- Result: `80 passed in 8.15s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

UI proof:
- `http://localhost:8502/?page=brand_approval_queue` returned HTTP `200`.

## Implemented UI Refinement - Product Listing Profile Review
Status: implemented in code and locally proven

Plain-English decision:
- the first New Product Review page should stay fast
- `Pass` should mean "this is worth setting up", not "all listing data is complete"
- COO, VAT confirmation, pack sizes, and product-profile fields should move to a second page before Amazon preview/submit

New page:
- `Product Listing Profile Review`

Required fields on the second page:
- `country_of_origin`
- `purchase_pack_size`
- `sold_pack_size`
- `vat_source_value`
- `vat_confirmed_flag`
- `product_tax_code`
- `currency_code`
- `price_includes_tax`
- `starting_price_gbp`
- `starting_quantity`
- `condition_type`

Behavior:
- first-page `pass` routes the product to profile review
- profile review complete creates the Amazon listing intake/draft eligibility
- missing COO, pack sizes, VAT confirmation, or price keeps the row held on the profile review page
- Amazon preview, live submit, Product DB promotion, and Google Sheets writes remain blocked until the profile review is complete

Tests needed:
- first-page `pass` can be saved without COO
- first-page `pass` creates a profile-review-pending row, not an Amazon-ready draft
- profile review cannot complete without COO, purchase pack size, sold pack size, VAT confirmation, and starting price
- completed profile review carries values into F090/F092/F093/F094
- Product DB promotion stays blocked until profile review plus Amazon read-back reconciliation pass

Implementation proof - 2026-05-01:
- First-page New Product Review `pass` no longer requires COO or starting price.
- Added `amazon_listing_profile_events` as the second-page profile completion event contract.
- Added O400 `Product Listing Profile Review` page.
- F090 now holds passed products with `product_listing_profile_required` until a completed profile event exists.
- F090/F092/F093/F094 now require/carry `purchase_pack_size`, `sold_pack_size`, and `vat_confirmed_flag` before preview/live submit.
- Focused proof: `pytest tests/test_o_ui_operator_view.py tests/test_f090_build_amazon_listing_intake.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_f094_submit_amazon_listing_drafts.py tests/test_f000_paths_and_schemas.py`
- Result: `84 passed in 8.96s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

## Completed Execution Block - COO, Tax, Currency, 3-Pass Preview, And Guarded Submit
Status: implemented and proven for the three controlled drafts

Current 3-pass sample:
- source: `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- latest summary: `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- observed UTC: `2026-04-29T15:01:19Z`
- `pass_review_rows=3`
- sample rows:
  - `1144846` / `B082NMTZC2` / JVC
  - `1257989` / `B09FQCWKPW` / Kensington
  - `1174830` / `B084CTW7T8` / Embryolisse

Allowed files for completed block:
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `scripts/flows/F/F092_build_amazon_listing_drafts.py`
- `scripts/api/amazon_listings_items.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_f090_build_amazon_listing_intake.py`
- `tests/test_f092_build_amazon_listing_drafts.py`
- `tests/test_amazon_listings_items.py`
- `tests/test_f093_run_amazon_listing_preview.py`

Phase A - Review PASS UI gate:
- when `pass` is selected, require `country_of_origin`
- validate COO as two uppercase ISO letters
- capture `product_tax_code`, default from config
- capture `currency_code`, default `GBP` for UK marketplace
- capture `price_includes_tax`, default `1`
- capture required `starting_price_gbp` because the Listings Items API will not infer or convert a listing price
- block event write if `pass` has no COO

Phase B - Contract carry-forward:
- add fields to review event, intake, draft, preview payload
- hold rows missing COO/product tax/currency/starting price before preview

Phase C - Payload update:
- include `country_of_origin`
- include `product_tax_code`
- include explicit currency
- keep `value_with_tax` for UK tax-inclusive prices
- verify exact ASIN-link attribute through Product Type Definitions before live submit (`merchant_suggested_asin` vs `item_id`)

Phase D - Three checked pass rows:
- approve only the three current pass rows
- enter COO for each in the UI
- build intake, SKU reservations, and drafts
- approve drafts for preview
- run validation preview only for the three exact draft IDs
- do not live submit
- do not write Product DB
- do not write Google Sheets

Completion proof for next block:
- tests prove `pass` without COO or starting price cannot write an event
- tests prove COO/product tax/currency/starting price carry through event -> intake -> draft -> payload
- tests prove preview remains `VALIDATION_PREVIEW`
- runtime proof records three preview attempts or truthful holds for the three selected rows

Implementation status - 2026-05-01T11:05:28Z:
- Phase A complete in code: O400 now shows listing compliance fields when `Pass` is selected, keeps incomplete Pass rows as drafts, and blocks event writes without valid two-letter COO or positive starting price.
- Phase B complete in code: F contracts now carry `country_of_origin`, `product_tax_code`, `currency_code`, `price_includes_tax`, and `starting_price_gbp` through review events, intake, and drafts; F090/F092 hold missing or invalid compliance data before preview.
- Phase C complete in code: Listings Items validation-preview payload now includes COO, product tax code, explicit currency, and tax-inclusive `value_with_tax` when `price_includes_tax=1`.
- Phase D not run yet: controlled three-row Amazon validation preview still needs the operator to enter COO and starting price for the three current Pass rows and approve the exact drafts for preview only.

Isolated proof - 2026-05-01T11:05:28Z:
- Command: `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_o_ui_operator_view.py`
- Result: `80 passed in 7.35s`
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after the test session completed.

Runtime proof - 2026-05-01T11:23:49Z:
- Seeded three fresh review `pass` events with COO and starting price:
  - `1144846` / `B082NMTZC2` / COO `CN` / price `299.00`
  - `1257989` / `B09FQCWKPW` / COO `CN` / price `69.97`
  - `1174830` / `B084CTW7T8` / COO `FR` / price `17.99`
- F090 initial hold root cause was `no_completed_review_pack`; fixed by allowing F090 to use the current published `out/analysis_reports/f_live_price_file_pass_review_latest.csv` pack when no price-list-manager handoff manifest exists.
- F090 also now fills missing supplier cost from `f_dashboard_yes_no_rescan_plan_latest.csv` or first-check evidence rather than leaving downstream drafts blank.
- First Amazon validation preview found local payload issue: `fulfillment_availability=AFN` was rejected by Amazon issue `90244`.
- Fixed UK default fulfillment channel to `DEFAULT`, rebuilt and reapproved the three drafts, then reran validation preview.
- Final F093 result: `eligible_rows=3;attempted_rows=3;passed_rows=3;rejected_rows=0;failed_rows=0`.
- Final preview event status: all three `preview_passed`, response status `VALID`, issue count `0`.
- `amazon_listing_preview_issues_live.csv` row count: `0`.
- `amazon_listing_submission_events.csv` row count: `0`; no live submit occurred.
- Health: intake, SKU reservation, draft builder, and preview checks are `ok`.

Regression proof - 2026-05-01T11:23:49Z:
- Command: `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_o_ui_operator_view.py`
- Result: `82 passed in 7.27s`
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after the test session completed.

Live submit proof - 2026-05-01T11:49:56Z:
- First F094 live submit attempt returned Amazon HTTP `400` for all three rows because the live request still sent preview-only `includedData`; Amazon documentation says `includedData` can only be requested when `mode=VALIDATION_PREVIEW`.
- Fixed `amazon_listings_items.py` so preview sends `includedData=issues,identifiers`, but live submit omits it.
- Fixed F094 audit notes so non-2xx responses record `http_status` instead of the misleading `listing_submitted` fallback.
- Added guarded `--retry-failed-submit` selection for previous HTTP submit failures with passed preview, no submission ID, and no Amazon rejection.
- Live retry command: `python scripts\flows\F\F094_submit_amazon_listing_drafts.py --draft-id draft_3ba619917e858347 --draft-id draft_e7e9e5a062489d4b --draft-id draft_c5655daf8ea8cc5f --retry-failed-submit --run-submit --confirm-live-submit`
- Live retry result: `eligible_rows=3;attempted_rows=3;submitted_rows=3;rejected_rows=0;failed_rows=0`.
- Submission IDs:
  - Kensington `NP-STO-E149D07A` / `B09FQCWKPW`: `a81a02a5c0534058b324df809161ab0c`
  - Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`: `813fa67240d6490daf8c1f9abc5cb324`
  - JVC `NP-STO-3502B107` / `B082NMTZC2`: `f2ff25a82e5b478c82325b698fb7b3c0`
- Draft state: all three rows are `submitted_to_amazon`, `amazon_submission_status=submitted`, `response_status=ACCEPTED`, `http_status=200`.
- Health: `amazon_listing_submit=ok`, `submitted_rows=3`, `rejected_rows=0`, `failed_rows=0`.
- Product DB and Google Sheets writes still did not run.

Final regression proof - 2026-05-01T11:50Z:
- Command: `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_f094_submit_amazon_listing_drafts.py tests/test_o_ui_operator_view.py`
- Result: `89 passed in 10.48s`
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after the test session completed.
