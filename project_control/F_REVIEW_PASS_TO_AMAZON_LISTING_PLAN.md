# Review Pass To Amazon Listing Plan

## Purpose
Build the next downstream step after New Product Review:

- scanner finds supplier candidates
- completed supplier scan builds a review pack
- user approves rows in New Product Review
- approved rows become Amazon listing drafts
- only explicitly approved listing drafts are submitted to Amazon by API

This is not part of the price-list process manager. It is a later selling/listing workflow fed by reviewed supplier opportunities.

## Key Rule
Do not automatically add every scanner PASS to Amazon.

A scanner PASS means:
- the product passed the automated sourcing checks
- it is eligible for human review

It does not mean:
- supplier stock has been manually checked
- the product should be listed
- the Amazon listing payload is complete
- the item is safe to sell
- the listing should be pushed live

The first live version must require a user approval event from New Product Review before any Amazon listing draft can be submitted.

## Current System Fit
The existing scanner-to-review plan already has the correct upstream rule:

- completed supplier runs build immutable review packs
- New Product Review reads completed packs
- operator decisions are written to `out/systems/F/inbox/feeder_review_events.csv`
- later downstream logic consumes approved review decisions, not raw scanner passes

This new feature should consume that review event file plus the completed review pack manifest.

## Amazon API Direction
Use Amazon Selling Partner API listing operations, not browser automation.

Current official Amazon documentation points to:
- Listings Items API for seller listing create/update/search flows.
- Product Type Definitions API for the schema and required attributes for a marketplace/product type.
- `putListingsItem` for create or full update.
- `patchListingsItem` for partial update.
- validation preview mode before submitting changes.

Important safety point:
- Amazon warns that `putListingsItem` can replace existing listing content if fields are omitted.
- Therefore the bridge creates drafts and validation previews first.
- Live submit is a separate, explicit, guarded action after preview acceptance.

Source references checked on 2026-05-01:
- https://developer-docs.amazon.com/sp-api/lang-US/docs/listings-items-api
- https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/create-a-listing
- https://developer-docs.amazon.com/sp-api/lang-en_US/reference/patchlistingsitem

## Scope Decision
The first version should only support creating our seller offer/listing for an existing ASIN.

Do not start with creating brand-new Amazon catalogue pages.

Reason:
- scanner PASS rows normally have ASIN evidence already
- existing-ASIN offer creation is much simpler and safer
- new catalogue-page creation needs stricter product data, product type mapping, image rules, brand rules, and higher risk of suppressed listings

## Proposed Flow
1. Supplier scan completes.
2. FPM150 builds the completed supplier review pack.
3. User opens New Product Review.
4. User checks supplier website and marks a row as `pass` in New Product Review.
   - This first `pass` should mean: "commercially worth moving to product profile review".
   - It should not ask for all Amazon/product-profile details on this first page.
5. The passed row moves to a second review page: `Product Listing Profile Review`.
   - This second page collects and confirms the data needed to create the product profile and Amazon listing.
   - Required examples:
     - Country of Origin (`country_of_origin`, ISO 3166-1 alpha-2 such as `GB`, `CN`, `US`)
     - purchase pack size, meaning how many sellable units we buy from the supplier
     - sold pack size, meaning how many units the Amazon customer receives per sale
     - VAT status/rate confirmation from the price list, with user confirmation before submit
     - supplier case quantity
     - whether supplier ordering must follow case multiples
     - valid order step
     - MOQ
     - target margin/profit setup
     - price currency (`currency_code`, default `GBP` for UK)
     - tax code (`product_tax_code`, default from config, editable)
     - tax-included price basis (`price_includes_tax`, default `1` for UK `value_with_tax`)
     - starting sell price
     - starting quantity / inactive quantity rule
     - condition
     - brand approval / restriction check status
     - invoice requirement quantity, if Amazon requires approval
     - invoice-risk decision: fail, park, try Seller Central approval, or plan invoice purchase
     - any product-profile fields required before Product DB promotion
   - If Country of Origin, VAT confirmation/rate, pack sizing, order rules, or profit setup is unknown, the row stays in profile review hold and does not create an Amazon-ready draft.
   - If brand approval is required, the row moves to a brand approval queue and does not create a Product DB row or repricer-eligible product.
6. Review-pass bridge creates a local listing-intake draft from completed-pack review pass rows only.
7. SKU reservation creates or reuses one stable seller SKU for the approved candidate.
8. Draft builder creates an Amazon listing draft using that reserved seller SKU and completed profile data.
9. Draft validator checks required local fields.
10. User explicitly approves the listing draft for Amazon preview.
11. Amazon validation preview is run, if credentials and API access are available.
12. UI shows draft status:
   - missing local data
   - product profile review required
   - product profile complete
   - SKU reserved
   - ready for Amazon preview
   - Amazon preview accepted
   - Amazon preview rejected
   - ready for live submit
   - submitted
- accepted for processing
- read-back confirmed
- post-submit issue found
13. Live submit only runs with an explicit apply flag and exact candidate approval.
14. Local Product DB and operations loop are updated only after Amazon accepts the listing submission and reconciliation confirms the listing exists.
15. If read-back finds a blocking Amazon issue, that product stays blocked and must not be promoted to Product DB.

## COO, Currency, And 3-Pass Execution Addendum - 2026-05-01
This addendum updates the task from "preview-only bridge" to "existing-ASIN offer listing with required compliance fields".

Root-cause rule:
- do not default or guess Country of Origin downstream
- the first New Product Review `pass` is only the commercial approval to move forward
- the earliest correct truth point for COO, VAT confirmation, and pack sizing is the next `Product Listing Profile Review` page
- therefore the UI should move COO and product-profile fields off the first review page and require them on the second page before Amazon draft approval

API payload rule:
- existing-ASIN offer listings use `PRODUCT` with `LISTING_OFFER_ONLY`
- price must be explicit for the marketplace; UK default is `currency_code=GBP`
- use tax-inclusive price for UK via `purchasable_offer.our_price.schedule.value_with_tax`
- include `country_of_origin` and `product_tax_code` in draft, preview, and live submit payloads
- before live submit, retrieve the latest Product Type Definition for `PRODUCT` / marketplace / seller and verify the exact ASIN link attribute for the schema (`merchant_suggested_asin` vs `item_id`)

Current 3-pass proof source:
- source file: `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- summary file: `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- latest summary observed: `2026-04-29T15:01:19Z`
- `pass_review_rows=3`
- sample rows:
  - supplier SKU `1144846`, ASIN `B082NMTZC2`, brand `JVC`, title starts `JVC RV-NB300DAB Boombox`
  - supplier SKU `1257989`, ASIN `B09FQCWKPW`, brand `Kensington`, title starts `Kensington Orbit Wireless Trackball`
  - supplier SKU `1174830`, ASIN `B084CTW7T8`, brand `Embryolisse`, title starts `Embryolisse Hydra-Cream Light`

## Brand Approval And Invoice Requirement Addendum - 2026-05-01
This addendum handles the case where Amazon blocks a submitted or pre-checked listing because the seller account needs brand/category approval.

Research findings:
- The Listings Restrictions API can check whether restrictions prevent listing creation for an existing ASIN.
- When approval is required, Amazon can return next-step links so the seller can pursue approval.
- The documented flow points the seller to a URL/Seller Central approval path; no public SP-API operation was found for completing the selling application or uploading brand-approval invoices directly.
- `getListingsItem` can then be used after submit/read-back to inspect listing issues if a listing exists but is not buyable.

Plain-English rule:
- Brand approval required means "not ready to sell".
- A row blocked by brand approval must not be promoted to Product DB.
- A row blocked by brand approval must not enter the repricer.
- If approval needs an invoice quantity, store that requirement before any buying decision.
- If the invoice quantity is too risky, the operator can fail or park the row immediately.

Important operating distinction:
- The repricer should not decide what to buy.
- The approval queue can store "invoice quantity required" and create a buying/invoice requirement later.
- The repricer should only see active, approved, Product DB products with sellable Amazon listings.

### Scenario Matrix
| Scenario | Example | System action |
|---|---|---|
| No restriction | API returns no restrictions | Continue to draft, preview, submit, read-back, Product DB promotion gate |
| Auto/instant approval possible | Seller Central approval link may clear without invoice | Show approval link, keep row blocked, recheck after operator tries approval |
| Low invoice requirement | 10 units and risk is acceptable | Store required invoice quantity, estimated cost, supplier, and approval intent in approval queue; do not promote until approval clears |
| High invoice requirement | 100 units / about GBP 700 risk | Fail or park; default recommendation is fail/park, not buy stock just to unlock |
| Already submitted then blocked | Embryolisse created SKU but Amazon returned issue `18304` | Keep local SKU reservation and read-back evidence, mark `blocked_brand_approval`, keep out of Product DB/repricer |
| Brand unlocked later | Approval gained using a different cheaper product from same brand | Recheck parked same-brand rows and allow them to re-enter the listing flow if restriction clears |

### Storage Plan
New F-owned contracts:
- `out/systems/F/live/amazon_listing_restrictions_live.csv`
- `out/systems/F/history/amazon_listing_restriction_events.csv`
- `out/systems/F/live/brand_approval_queue_live.csv`
- `out/systems/F/history/brand_approval_decision_events.csv`

Core fields:
- `observed_utc`
- `candidate_id`
- `supplier_id`
- `supplier_sku`
- `barcode`
- `asin`
- `brand`
- `amazon_title`
- `expected_seller_sku`
- `marketplace_id`
- `condition_type`
- `restriction_status`
- `approval_required_flag`
- `reason_code`
- `reason_message`
- `approval_link`
- `invoice_required_quantity`
- `invoice_unit_cost_gbp`
- `invoice_total_risk_gbp`
- `operator_decision`
- `decision_reason`
- `cooldown_until_utc`
- `recheck_trigger`
- `approval_application_status`
- `invoice_artifact_reference`
- `updated_at_utc`

Operator decisions:
- `fail_now`: product is not worth the invoice risk.
- `park`: keep evidence, do not keep checking daily.
- `try_seller_central`: user will try the approval link, then system rechecks.
- `invoice_planned`: user accepts the invoice quantity risk and wants it added to an approval-buying queue.
- `invoice_uploaded`: user has uploaded/recorded invoice evidence and wants a recheck.
- `approved_recheck`: rerun restrictions/read-back because approval may now be cleared.

Cooldown rules:
- `fail_now`: no automatic recheck.
- `park`: default `365` days or recheck only when the same brand appears again with a better/cheaper qualifying product.
- `try_seller_central`: recheck only after the operator marks the Seller Central attempt complete.
- `invoice_planned`: recheck only after invoice evidence exists.
- `invoice_uploaded`: recheck immediately, then park or advance based on Amazon response.
- Do not recheck approval-blocked products daily by default.

### UI Plan
On `Product Listing Profile Review`, add a Brand Approval section:
- button: run restriction pre-check
- status: clear / approval required / blocked / unknown
- approval reason text
- approval link, if Amazon returns one
- required invoice quantity
- estimated invoice cost
- decision buttons: fail, park, try approval, plan invoice, mark invoice uploaded

If the operator sees a requirement such as `100` units and decides the risk is too high, they can fail the row from this second page without creating a Product DB row.

### API Plan
Add a pre-submit step:
- call Listings Restrictions API `getListingsRestrictions` for ASIN, seller, marketplace, and condition
- if restrictions list is empty, continue
- if reason code indicates approval required, write approval queue row and block draft/live submit
- store approval links if returned
- do not create Product DB promotion event

Add a post-submit/read-back safety net:
- if `getListingsItem` reports issue `18304` or another approval-related blocking issue, move the row to `blocked_brand_approval`
- keep the SKU reservation as local evidence
- keep out of Product DB and repricer

### Repricer Boundary
Repricer eligibility must require all of these:
- Product DB active row exists
- Amazon read-back reconciliation is `confirmed_product_db_eligible`
- no active restriction row
- no active brand approval queue block
- listing is buyable or explicitly allowed by a controlled inactive-listing rule

Approval-blocked rows can produce a buying/invoice requirement, but they must not become repricer targets.

### Execution Phases
1. Add Listings Restrictions API wrapper. Status: implemented.
2. Add F097 restriction pre-check script. Status: implemented.
3. Add F098 brand approval queue builder. Status: implemented.
4. Add UI fields and decisions. Status: implemented as a separate `Brand Approval Queue` page in O400.
5. Block F094 when approval is required unless an explicit future exception is designed. Status: implemented for known active restriction/approval queue blocks.
6. Update F096 so Product DB eligibility excludes active approval blocks. Status: implemented.
7. Add repricer/Product DB guard tests so blocked SKUs cannot leak into active repricing. Status: implemented for the Product DB promotion gate; direct repricer integration remains future because Product DB promotion is still not built.

### Proof Required
- Embryolisse-like `APPROVAL_REQUIRED` rows are held before Product DB promotion.
- User can enter invoice requirement quantity and fail/park the row.
- A low-quantity approval candidate can be stored without becoming repricer eligible.
- A high-quantity approval candidate can be failed without daily rechecks.
- Already-submitted blocked SKUs remain traceable but excluded from Product DB.
- Recheck only runs on manual trigger, invoice upload, same-brand opportunity, or bounded cooldown.

### Implementation Proof - 2026-05-01
Implemented files:
- `scripts/api/amazon_listings_restrictions.py`
- `scripts/flows/F/F097_check_amazon_listing_restrictions.py`
- `scripts/flows/F/F098_build_brand_approval_queue.py`
- `scripts/flows/F/F096_reconcile_amazon_listing_submissions.py`
- `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_amazon_listings_restrictions.py`
- `tests/test_f097_f098_brand_approval_queue.py`
- `tests/test_f094_submit_amazon_listing_drafts.py`
- `tests/test_f095_f096_amazon_listing_readback.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_f000_paths_and_schemas.py`

Live restriction check:
- Command: `python scripts\flows\F\F097_check_amazon_listing_restrictions.py --draft-id draft_3ba619917e858347 --draft-id draft_e7e9e5a062489d4b --draft-id draft_c5655daf8ea8cc5f --run-check`
- Result: `checked_rows=3;clear_rows=2;approval_required_rows=1;restricted_rows=0;failed_rows=0`.

Live approval queue:
- Command: `python scripts\flows\F\F098_build_brand_approval_queue.py`
- Result: `queue_rows=1;failed_rows=0;parked_rows=0;invoice_required_rows=0`.
- Queue row: Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`, `approval_status=approval_required`, `reason_code=APPROVAL_REQUIRED`.
- Seller Central approval link was captured from the Amazon restriction response.

Reconciliation after the approval queue:
- Command: `python scripts\flows\F\F096_reconcile_amazon_listing_submissions.py`
- Result: `reconciliation_rows=3;confirmed_rows=2;blocked_rows=1;pending_rows=0`.
- Product DB eligible rows remain Kensington and JVC only.
- Embryolisse remains blocked with `block_reason=approval_required` and `source_reference` including `brand_approval_queue_live`.

Focused proof:
- `pytest tests/test_o_ui_operator_view.py tests/test_amazon_listings_restrictions.py tests/test_f097_f098_brand_approval_queue.py tests/test_f094_submit_amazon_listing_drafts.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f000_paths_and_schemas.py`
- Result: `80 passed in 8.15s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

UI proof:
- `http://localhost:8502/?page=brand_approval_queue` returned HTTP `200`.

Product DB and Google Sheets writes did not run.

## Product DB Promotion Gate Addendum - 2026-05-01
This addendum implements the safe bridge from Amazon-confirmed listing rows into Product DB promotion candidates.

Plain-English rule:
- Amazon-clear does not automatically mean Product DB-ready.
- Product DB promotion needs both Amazon read-back success and complete product profile data.
- Missing purchase pack size, sold pack size, VAT confirmation, or Product DB order fields must hold the row before any Product DB create event.

Implemented files:
- `scripts/flows/O/O430_build_product_db_promotion_candidates.py`
- `scripts/flows/O/O431_stage_product_db_create_events.py`
- O contracts in `scripts/flows/O/_schemas.py`
- `tests/test_o430_o431_product_db_promotion.py`
- `tests/test_o000_paths_and_schemas.py`

New O-owned contracts:
- `out/systems/O/live/product_db_promotion_candidates_live.csv`
- `out/systems/O/live/product_db_promotion_holds_live.csv`
- `out/systems/O/live/product_db_promotion_health.csv`

Gate behavior:
- O430 reads Amazon reconciliation, listing drafts, intake/profile data, the brand approval queue, and Product DB preview for duplicate-SKU checks.
- O430 creates promotion candidates only for rows with `reconciliation_status=confirmed_product_db_eligible`.
- O430 writes hold rows for confirmed listings that are missing required Product DB profile data.
- O430 keeps brand-approval rows, parked rows, blocked reconciliation rows, and duplicate Product DB SKUs out of ready promotion.
- O431 defaults to dry-run and writes no Product DB edit event unless both `--stage-events` and `--confirm-product-db-promotion` are provided.
- O431 stages into the existing O-owned Product DB edit-event inbox, not directly into Product DB or Google Sheets.

Live proof:
- Command: `python scripts\flows\O\O430_build_product_db_promotion_candidates.py`
- Result: `candidate_rows=2;ready_rows=0;held_rows=2;hold_rows=3;blocked_rows=1`.
- Command: `python scripts\flows\O\O431_stage_product_db_create_events.py`
- Result: `stage_not_run;eligible_rows=0;staged_rows=0;held_rows=0;failed_rows=0`.
- Product DB edit events were not created by the dry run.
- Product DB and Google Sheets writes did not run.

Live product status:
- Kensington `NP-STO-E149D07A` / `B09FQCWKPW`: Amazon-clear, held for missing Product DB profile data.
- JVC `NP-STO-3502B107` / `B082NMTZC2`: Amazon-clear, held for missing Product DB profile data.
- Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`: parked/blocked by brand approval and invoice risk.

Missing fields blocking Kensington and JVC:
- purchase pack size
- sold pack size
- supplier case quantity
- valid order step
- MOQ
- VAT rate
- VAT confirmation

Focused proof:
- `pytest tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py tests/test_o420_product_database_edit_ui.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f097_f098_brand_approval_queue.py`
- Result: `24 passed in 3.58s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Next execution rule:
- Fill or repair the missing Product Listing Profile fields for Kensington and JVC first on the user-facing Product Listing Profile Review page.
- Rerun O430.
- Only if rows become `ready_for_product_db_event`, run O431 with explicit promotion approval.
- Keep Embryolisse parked until brand approval/invoice risk changes.

Operator feedback correction:
- The missing Product DB fields are not meant to be guessed by the system after Amazon listing.
- The user must complete the product's profile/profit setup before sending it on.
- Product Listing Profile Review now collects supplier case quantity, case-multiple rule, order step, MOQ, target margin, VAT source/rate, and VAT confirmation alongside COO, pack sizes, price, quantity, and condition.
- These fields flow through F090 intake, F092 drafts, and O430 Product DB promotion candidates.

Product DB destination schema correction:
- The O-owned edit-event format can carry the full profile, but the current Product DB preview/header cannot yet store all of it.
- O431 now checks the destination Product DB header before staging promotion events.
- If destination columns are missing, O431 writes `product_db_destination_schema=fail` to `product_db_promotion_health` and refuses to stage Product DB create events.
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
- `out/product_db_preview.csv` also currently has a duplicate `last_updated_A003` header.
- Google Sheets and `out/product_db_preview.csv` were not changed.

Regression proof:
- `pytest tests/test_o_ui_operator_view.py tests/test_f090_build_amazon_listing_intake.py tests/test_f092_build_amazon_listing_drafts.py tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py`
- Result: `82 passed in 15.49s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Destination schema proof:
- `pytest tests/test_o430_o431_product_db_promotion.py tests/test_o000_paths_and_schemas.py tests/test_o420_product_database_edit_ui.py`
- Result: `20 passed in 2.42s`.
- Live O431 dry-run returned `schema_missing_fields=9` and staged no events.

Execution phases for this update:

### Phase A - Product Listing Profile Review Page
Files:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`

Behavior:
- first-page `pass` writes a lightweight event that means "send to product profile review"
- the next page shows rows waiting for product/listing profile completion
- `country_of_origin` is required on this second page and must be two uppercase letters
- purchase pack size is required
- sold pack size is required
- VAT status/rate from the price list is shown and the user must confirm it
- supplier case quantity, valid order step, MOQ, and target margin are captured before the row can move on
- `product_tax_code` defaults from config, but is visible and editable
- `currency_code` defaults to `GBP` for `A1F83G8C2ARO7P`
- `price_includes_tax` defaults to `1`
- `starting_price_gbp` is required because the API will not infer or convert the offer price
- if the operator cannot confirm COO, VAT, pack sizing, order rules, or profit setup, the row stays in profile review hold and cannot become Amazon preview-ready

Proof:
- selecting `pass` on the first page can route a row to profile review without requiring COO
- profile review cannot be marked complete without COO, purchase pack size, sold pack size, VAT source/rate, VAT confirmation, and starting price
- completing profile review writes `country_of_origin`, pack sizes, order rules, target margin, VAT confirmation, tax code, currency, and starting price into the listing-profile event/state
- three current pass rows can each be completed on the profile review page and carry the values forward

### Phase B - Contract Expansion
Files:
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `scripts/flows/F/F092_build_amazon_listing_drafts.py`
- `tests/test_f090_build_amazon_listing_intake.py`
- `tests/test_f092_build_amazon_listing_drafts.py`

Behavior:
- add fields to intake and drafts:
  - `country_of_origin`
  - `product_tax_code`
  - `currency_code`
  - `price_includes_tax`
  - `purchase_pack_size`
  - `sold_pack_size`
  - `supplier_case_qty`
  - `supplier_case_multiple`
  - `valid_order_step`
  - `moq`
  - `target_margin`
  - `vat_confirmed_flag`
  - `vat_source_value`
- hold rows missing `country_of_origin`
- hold rows missing `product_tax_code`
- hold rows missing `currency_code`
- hold rows missing `starting_price_gbp`
- hold rows missing purchase pack size or sold pack size
- hold rows missing VAT source/rate
- hold rows where VAT has not been user-confirmed

Proof:
- completed profile event with COO, VAT confirmation, and pack sizes creates intake and draft
- first-page pass without completed profile stays in profile review and does not create an Amazon-ready draft
- profile event missing COO, VAT confirmation, or pack sizes is held before preview
- rerun remains idempotent

### Phase C - Payload Builder Correction
Files:
- `scripts/api/amazon_listings_items.py`
- `tests/test_amazon_listings_items.py`

Behavior:
- include `country_of_origin`
- include `product_tax_code`
- include explicit `currency_code`
- use `value_with_tax` when `price_includes_tax=1`
- keep `mode=VALIDATION_PREVIEW` for preview calls
- add Product Type Definition lookup or schema-cache step before live submit to verify exact attribute naming for the target seller/marketplace/product type

Proof:
- generated JSON includes COO, product tax code, explicit currency, condition, fulfillment, and ASIN link
- preview wrapper still forces `VALIDATION_PREVIEW`

Earlier implementation status - 2026-05-01T11:05:28Z, superseded by the profile-review update below:
- Phase A originally put COO and starting price on the O400 Pass path; this has now been superseded so first-page `pass` routes to Product Listing Profile Review instead.
- Phase B implemented: review events, Amazon listing intake, and Amazon listing drafts now carry `country_of_origin`, `product_tax_code`, `currency_code`, `price_includes_tax`, and `starting_price_gbp`; missing or invalid compliance data is held before preview.
- Phase C implemented: the Listings Items validation-preview payload now sends COO, product tax code, explicit currency, and tax-inclusive price basis.
- Focused proof passed: `80 passed in 7.35s` for the Amazon Listings payload, F090, F091, F092, F093, F schema, and O400 tests.
- Remaining note: pytest emitted the known Windows temp-folder cleanup `PermissionError` after tests completed.

Implementation status - Product Listing Profile Review update - 2026-05-01:
- First-page New Product Review `pass` now routes to profile review without requiring COO or starting price.
- Added second-page contract `amazon_listing_profile_events`.
- Added O400 `Product Listing Profile Review` page.
- Profile review requires COO, purchase pack size, sold pack size, VAT confirmation, tax code, currency, tax-included basis, and starting price before Amazon draft eligibility.
- F090 now holds passed rows as `product_listing_profile_required` until profile review is complete.
- F090/F092/F093/F094 now carry and require profile fields before preview/live submit.
- Focused proof: `84 passed in 8.96s`.

Runtime proof - 2026-05-01T11:23:49Z:
- Three controlled Pass events were seeded with COO and explicit starting price:
  - `1144846` / `B082NMTZC2` / COO `CN` / price `299.00`
  - `1257989` / `B09FQCWKPW` / COO `CN` / price `69.97`
  - `1174830` / `B084CTW7T8` / COO `FR` / price `17.99`
- F090, F091, and F092 produced `3` intake rows, `3` reserved SKUs, and `3` ready drafts with no holds.
- First validation preview correctly exposed a local payload issue: Amazon rejected `fulfillment_availability=AFN` with issue `90244`.
- UK listing defaults were corrected to `fulfillment_channel=DEFAULT`; the three drafts were rebuilt, reapproved for preview, and rerun.
- Final validation preview passed all three rows: `eligible_rows=3;attempted_rows=3;passed_rows=3;rejected_rows=0;failed_rows=0`.
- Final preview events show `response_status=VALID` and `issue_count=0` for all three drafts.
- `amazon_listing_preview_issues_live.csv` has `0` rows.
- Initial live submit attempt correctly stayed in F094 but Amazon returned HTTP `400` because the live request included preview-only `includedData`.
- Root cause fixed: validation preview still sends `includedData=issues,identifiers`; live submit now omits `includedData`.
- Guarded live retry submitted all three drafts: `eligible_rows=3;attempted_rows=3;submitted_rows=3;rejected_rows=0;failed_rows=0`.
- Submission IDs:
  - Kensington `NP-STO-E149D07A` / `B09FQCWKPW`: `a81a02a5c0534058b324df809161ab0c`
  - Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`: `813fa67240d6490daf8c1f9abc5cb324`
  - JVC `NP-STO-3502B107` / `B082NMTZC2`: `f2ff25a82e5b478c82325b698fb7b3c0`
- Final draft state: all three are `submitted_to_amazon`, `amazon_submission_status=submitted`, `response_status=ACCEPTED`, `http_status=200`.
- Product DB writes and Google Sheets writes did not run.
- Final focused regression proof: `89 passed in 10.48s`.

### Phase D - 3-Pass Controlled Preview Test
Files:
- `scripts/flows/F/F093_run_amazon_listing_preview.py`
- `tests/test_f093_run_amazon_listing_preview.py`

Procedure:
- use only the three current checked pass rows from `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- operator enters COO for each row in UI
- build intake, reserve SKUs, build drafts
- approve listing drafts for preview only
- run validation preview for those exact three draft IDs
- do not live submit

Success evidence:
- three review events with COO
- three SKU reservations
- three listing drafts with COO, tax code, currency
- three preview events
- preview issue rows recorded truthfully if Amazon rejects any row
- no Product DB promotion
- no Google Sheets write
- no live submit event

### Phase E - Guarded Live Submit
Files:
- `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- `tests/test_f094_submit_amazon_listing_drafts.py`

Status:
- implemented and proven for the three controlled drafts on 2026-05-01

Live submit preconditions:
- exact draft IDs
- latest preview accepted or known non-blocking WARN explicitly approved
- COO present
- product tax code present
- explicit currency present
- duplicate seller SKU check passed
- `--run-submit`
- `--confirm-live-submit`

API request rule:
- preview requests may send `includedData`
- live submit requests must not send `includedData`

Retry rule:
- `--retry-failed-submit` may retry previous HTTP submit failures only when preview passed, there is no submission ID, and the prior failure was not an Amazon validation rejection.

### Phase F - Read-Back And Product DB Promotion
Files:
- `scripts/flows/F/F095_check_amazon_listing_submission_status.py`
- `scripts/flows/F/F096_reconcile_amazon_listing_submissions.py`
- `scripts/flows/O/O430_apply_product_db_create_events.py`

Status:
- Amazon read-back and reconciliation are implemented and live-tested for the three controlled submitted drafts.
- Product DB promotion remains blocked until an O-owned promotion/apply step is built.

Live read-back proof - 2026-05-01T12:18:58Z:
- F095 read back the three exact submitted SKUs from Amazon Listings Items API.
- F096 reconciled the read-back events into Product-DB-eligibility state.
- Result: `reconciliation_rows=3;confirmed_rows=2;blocked_rows=1;pending_rows=0`.
- Kensington `NP-STO-E149D07A` / `B09FQCWKPW`: `confirmed_product_db_eligible`.
- JVC `NP-STO-3502B107` / `B082NMTZC2`: `confirmed_product_db_eligible`.
- Embryolisse `NP-STO-B1FFE9D8` / `B084CTW7T8`: blocked by Amazon issue `ERROR 18304 You need approval to list this brand.`
- Health row is truthful: `amazon_listing_reconciliation=fail` because one submitted listing is blocked.
- Product DB writes and Google Sheets writes did not run.

Focused proof:
- `pytest tests/test_amazon_listings_items.py tests/test_f095_f096_amazon_listing_readback.py tests/test_f000_paths_and_schemas.py tests/test_f093_run_amazon_listing_preview.py tests/test_f094_submit_amazon_listing_drafts.py`
- Result: `22 passed in 3.42s`.
- Note: Windows emitted the known pytest temp-folder cleanup `PermissionError` after tests completed.

Promotion rule:
- Product DB promotion may proceed only for rows with `confirmed_product_db_eligible`.
- Blocked rows must stay out of Product DB until Amazon restrictions are resolved or the product is explicitly parked/rejected.

## Back-To-Back Bridge Plan
This is the execution sequence to bridge a product from New Product Review pass to saved SKU to Amazon listing draft.

### Locked Decision
Do not overload scanner PASS or New Product Review `pass`.

Meaning:
- scanner PASS = eligible for human review
- New Product Review `pass` = eligible to create a local listing-intake draft and reserve a SKU
- listing draft approval = eligible for Amazon preview
- guarded live submit approval = eligible for Amazon write
- Amazon reconciliation success = eligible for Product DB / operations-loop promotion

This keeps the earliest gate truthful and avoids output-masking later.

### Phase 1 - Contract Bridge
Add F-owned contracts for the bridge:

- `amazon_listing_intake_live`
- `amazon_listing_sku_reservations_live`
- `amazon_listing_drafts_live`
- `amazon_listing_draft_events`
- `amazon_listing_preview_events`
- `amazon_listing_preview_issues_live`
- `amazon_listing_holds_live`
- `amazon_listing_health`

First implementation files:
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `tests/test_f090_build_amazon_listing_intake.py`

Rules:
- read `out/systems/F/inbox/feeder_review_events.csv`
- require latest review event to be `review_decision=pass`
- require `review_pack_type=passes`
- require completed handoff manifest / completed review pack lineage
- do not read raw scanner PASS rows as the approval source
- do not call Amazon
- do not write Product DB
- do not write Google Sheets

Proof:
- raw scanner PASS alone creates 0 listing-intake rows
- running scan creates 0 listing-intake rows
- completed review pack plus latest `pass` event creates 1 listing-intake row
- later `fail` or reopen event removes/blocks the intake row

### Phase 2 - SKU Reservation
Create a deterministic seller SKU reservation step.

First implementation files:
- `scripts/flows/F/F091_reserve_amazon_listing_skus.py`
- `tests/test_f091_reserve_amazon_listing_skus.py`

Recommended first SKU format:
- `NP-{SUP}-{HASH8}`

Where:
- `NP` means new product intake
- `SUP` is a short supplier code derived from `supplier_id`
- `HASH8` is a stable uppercase hash of `supplier_id | active_run_id | candidate_id | asin | marketplace_id`

Rules:
- rerunning the same candidate must reuse the same seller SKU
- no existing `out/product_db_preview.csv` seller SKU may be reused
- no existing listing snapshot SKU may be reused
- no duplicate reservation identity may exist
- if a collision exists, hold the row with `sku_collision`, do not invent a second SKU silently
- reserve SKU locally before Amazon draft, but do not promote to Product DB yet

Output:
- `out/systems/F/live/amazon_listing_sku_reservations_live.csv`
- optional SQL mirror when storage mode is enabled

Proof:
- same candidate rerun returns same SKU
- different candidates get different SKUs
- existing Product DB SKU blocks reservation
- existing listing snapshot SKU blocks reservation
- reservation output is one row per stable identity

### Phase 3 - Draft Builder
Build Amazon listing drafts from intake rows plus SKU reservations.

First implementation files:
- `scripts/flows/F/F092_build_amazon_listing_drafts.py`
- `tests/test_f092_build_amazon_listing_drafts.py`
- `config/feeder/amazon_listing_defaults.csv`

Rules:
- only rows with `reservation_status=reserved` may become drafts
- existing-ASIN offer only
- no Amazon calls
- no Product DB writes
- no Google Sheets writes
- rows missing ASIN, cost, marketplace, condition, fulfillment channel, product type, or starting price are held with a clear reason

Output:
- `out/systems/F/live/amazon_listing_drafts_live.csv`
- `out/systems/F/live/amazon_listing_holds_live.csv`
- `out/systems/F/history/amazon_listing_draft_events.csv`

Proof:
- approved review pass with full data creates one draft
- missing ASIN/cost/defaults create hold rows
- rerun updates the same draft, no duplicate
- `review_decision=fail` does not create a draft

### Phase 4 - Product DB Save Boundary
Do not write `out/product_db_preview.csv` directly at review-pass time.

Reason:
- Product DB is still sheet-backed through A/B refresh paths.
- Direct local edits can be overwritten by the next sheet export.
- A half-created Amazon listing should not appear as a normal live Product DB row.

Instead:
- SKU reservation is the first saved local database record.
- Product DB promotion waits for Amazon acceptance and read-back reconciliation.
- Promotion should use an event bridge into `out/systems/O/inbox/product_db_edit_events.csv` or a new O-owned product-intake apply script, not a silent CSV patch.

Implementation files for promotion:
- `scripts/flows/F/F096_reconcile_amazon_listing_submissions.py`
- `scripts/flows/O/O430_build_product_db_promotion_candidates.py`
- `scripts/flows/O/O431_stage_product_db_create_events.py`
- `tests/test_f096_reconcile_amazon_listing_submissions.py`
- `tests/test_o430_o431_product_db_promotion.py`

Promotion rule:
- Product DB row may be created only when Amazon accepted the listing submission, read-back confirms the seller SKU exists for the expected ASIN and marketplace, no active brand approval block exists, and the Product Listing Profile fields required by Product DB are complete.

### Phase 5 - UI Bridge
Add an "Approved For Amazon Listing" lane/tab after the New Product Review pass lane.

First implementation file:
- `scripts/flows/O/O400_operator_ui.py`

UI rules:
- show reserved seller SKU
- show blocked reasons
- separate buttons:
  - `Approve listing draft`
  - `Run Amazon preview`
  - `Submit to Amazon`
- hide or disable live submit until preview and proof are clean
- do not make New Product Review `pass` look like Amazon submit approval

### Phase 6 - Amazon Preview
Add API validation preview only.

First implementation files:
- `scripts/api/amazon_listings_items.py`
- `scripts/flows/F/F093_run_amazon_listing_preview.py`
- `tests/test_f093_run_amazon_listing_preview.py`

Rules:
- preview calls must use `mode=VALIDATION_PREVIEW`
- record all preview issues
- rows with rejected preview cannot be submitted

### Phase 7 - Guarded Live Submit And Reconciliation
Add live submit only after draft and preview evidence are clean.

First implementation files:
- `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- `scripts/flows/F/F095_check_amazon_listing_submission_status.py`
- `tests/test_f094_submit_amazon_listing_drafts.py`
- `tests/test_f095_check_amazon_listing_submission_status.py`

Rules:
- require `--run-submit`
- require `--confirm-live-submit`
- require exact draft IDs or batch ID
- require accepted preview
- require no local holds
- require no duplicate seller SKU already listed
- write Product DB promotion event only after Amazon read-back confirms the listing

## New User-Facing UI
Add a lane or tab in New Product Review:

- Approved For Amazon Listing

Each approved row should show:
- supplier
- source price file/run
- supplier SKU
- barcode
- ASIN
- Amazon title
- supplier cost
- expected listing SKU
- listing mode: existing ASIN offer
- draft status
- Amazon preview issues
- final submit status

Add a second operator page after New Product Review pass:

- Product Listing Profile Review

This page should show only rows that have passed the first review but still need product/listing profile data. It is the right place to enter or confirm:
- Country of Origin
- purchase pack size
- sold pack size
- VAT status/rate from price list, with user confirmation
- tax code
- currency
- tax-included price basis
- starting sell price
- starting quantity / inactive quantity rule
- condition
- any Product DB profile fields that must be known before promotion

The first New Product Review page should stay fast: pass/fail/watch the opportunity. The second page should be the slower product setup check before Amazon preview and Product DB promotion.

Buttons should be separated:
- `Approve listing draft`
- `Run Amazon preview`
- `Submit to Amazon`

The first version should hide `Submit to Amazon` behind an operator confirmation setting until the dry-run flow is proven.

## Data Contracts
Suggested new files:

- `out/systems/F/live/amazon_listing_drafts_live.csv`
- `out/systems/F/live/amazon_listing_intake_live.csv`
- `out/systems/F/live/amazon_listing_sku_reservations_live.csv`
- `out/systems/F/live/amazon_listing_holds_live.csv`
- `out/systems/F/history/amazon_listing_draft_events.csv`
- `out/systems/F/history/amazon_listing_preview_events.csv`
- `out/systems/F/live/amazon_listing_preview_issues_live.csv`
- `out/systems/F/history/amazon_listing_submission_events.csv`
- `out/systems/F/health/amazon_listing_health.csv`
- `config/feeder/amazon_listing_defaults.csv`

Suggested draft fields:

- observed_utc
- draft_id
- supplier_id
- supplier_name
- source_run_id
- review_snapshot_id
- review_batch_id
- candidate_id
- supplier_sku
- barcode
- asin
- amazon_title
- supplier_cost_gbp
- expected_seller_sku
- sku_reservation_status
- sku_reservation_reason
- marketplace_id
- product_type
- condition_type
- country_of_origin
- product_tax_code
- currency_code
- price_includes_tax
- purchase_pack_size
- sold_pack_size
- vat_source_value
- vat_confirmed_flag
- fulfillment_channel
- starting_price_gbp
- starting_quantity
- listing_mode
- draft_status
- block_reason
- amazon_preview_status
- amazon_preview_issue_count
- amazon_submission_status
- amazon_submission_id
- updated_at_utc

## Approval Gate
A row may enter `amazon_listing_drafts_live.csv` only when all are true:

- completed supplier review pack exists
- source supplier run is complete
- row came from the PASS review pack
- latest New Product Review decision is `pass`
- seller SKU has been reserved by the SKU reservation step
- ASIN is present
- seller SKU can be generated
- supplier cost is present
- minimum selling price rule is available
- condition is known
- Country of Origin is known
- purchase pack size is known
- sold pack size is known
- VAT status/rate has been confirmed by the user
- product tax code is known
- currency code is known
- marketplace is known

Rows that fail the gate should be held with a clear `block_reason`.

A Product DB row may be created only when all are true:

- Amazon submit was explicitly approved
- Amazon accepted the listing submission
- Amazon read-back confirms the expected seller SKU exists for the expected ASIN and marketplace
- no duplicate seller SKU exists in Product DB or listing snapshots
- Product DB promotion event passes O-owned validation

## Idempotency
The system must not create duplicate Amazon listings because a script is rerun.

Use a stable identity key:

- candidate_id
- ASIN
- expected_seller_sku
- marketplace_id

If the same approved row is processed again, update the same draft row and event history. Do not create a second draft.

SKU reservation idempotency key:

- supplier_id
- active_run_id
- candidate_id
- ASIN
- marketplace_id

If the same approved row is processed again, reuse the same reserved seller SKU. Do not generate a new SKU unless the old reservation is explicitly voided by a later guarded action.

## Live Submit Safety
Default mode:

- build drafts only
- no Amazon write
- no Product DB write
- no Google Sheets write

Live submit should require:

- explicit CLI flag, for example `--apply-live`
- explicit confirmation flag, for example `--confirm-amazon-listing-submit`
- exact draft IDs or batch ID
- API validation preview already passed
- no unresolved local block reasons
- no duplicate seller SKU already listed

## Health Checks
Add health items for:

- approved review rows not converted to drafts
- draft rows missing required columns
- draft rows blocked by missing local data
- Amazon preview failures
- Amazon live submission failures
- duplicate draft identity
- submission accepted but not confirmed by later `getListingsItem`

Hard FAIL examples:

- live submit attempted without explicit apply flag
- duplicate seller SKU submit attempt
- Product DB updated before Amazon acceptance
- Google Sheets write attempted

WARN examples:

- approved rows waiting for preview
- preview rejected by Amazon
- product type missing and row held
- listing restrictions detected

## Tests Needed
Minimum tests for the first implementation:

- raw scanner PASS does not create listing draft
- incomplete supplier scan does not create listing draft
- completed review pack plus approved review event creates one draft
- rerun updates same draft, no duplicate
- missing ASIN blocks
- missing supplier cost blocks
- missing seller SKU blocks
- preview mode does not submit live
- live submit fails without explicit flags
- accepted Amazon response writes submission event
- Product DB update is blocked until Amazon acceptance/reconciliation exists
- SKU reservation is stable across reruns
- duplicate Product DB or listing snapshot seller SKU blocks reservation
- latest `fail` event after an earlier `pass` blocks intake/draft creation
- Product DB promotion event is written only after Amazon read-back confirms the listing
- New Product Review `pass` without Country of Origin can route to Product Listing Profile Review but cannot create an Amazon-ready draft
- Product Listing Profile Review cannot complete without Country of Origin, purchase pack size, sold pack size, VAT confirmation, and starting price
- Country of Origin, pack sizes, VAT confirmation, product tax code, and currency carry from profile review event to intake to draft
- preview payload includes Country of Origin, product tax code, explicit currency, and tax-inclusive price for UK
- the three checked pass rows can be processed through draft and validation preview without live submit

## Build Phases
### Implementation Status - 2026-05-01
Phase 1 to Phase 5 review-pass through guarded Amazon live submit is implemented.

Implemented files:
- `scripts/api/spapi_owner.py`
- `scripts/api/amazon_listings_items.py`
- `scripts/flows/F/F090_build_amazon_listing_intake.py`
- `scripts/flows/F/F091_reserve_amazon_listing_skus.py`
- `scripts/flows/F/F092_build_amazon_listing_drafts.py`
- `scripts/flows/F/F093_run_amazon_listing_preview.py`
- `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- F contracts in `scripts/flows/F/_schemas.py`
- `scripts/flows/O/O400_operator_ui.py`
- `config/feeder/amazon_listing_defaults.csv`

Proof:
- `pytest tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py`
- Result: 14 passed
- `pytest tests/test_o_ui_operator_view.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py`
- Result: 68 passed
- `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_o_ui_operator_view.py`
- Result: 74 passed
- `pytest tests/test_amazon_listings_items.py tests/test_f000_paths_and_schemas.py tests/test_f090_build_amazon_listing_intake.py tests/test_f091_reserve_amazon_listing_skus.py tests/test_f092_build_amazon_listing_drafts.py tests/test_f093_run_amazon_listing_preview.py tests/test_f094_submit_amazon_listing_drafts.py tests/test_o_ui_operator_view.py`
- Result: 89 passed

Current downstream status:
- Amazon read-back reconciliation is implemented.
- Brand approval blocking is implemented.
- Product DB promotion candidate building and dry-run event staging are implemented.
- No Product DB edit event has been staged for the live rows because Kensington and JVC are missing required Product DB profile fields.
- no Google Sheets writes

### Phase 1 - Investigation
Study existing New Product Review event shape and decide the exact approval decision name.

Decisions to make with the user:
- should approval be called `approve_listing`, `list_on_amazon`, or similar
- seller SKU naming convention
- default condition
- whether first listings should be FBM inactive/zero stock or FBA-ready
- whether price should be minimum viable price, current target sell price, or manual entry

### Phase 2 - Draft Builder
Create read-only intake, SKU reservation, and draft builder from approved review events.

No Amazon calls.
No Product DB writes.
No Google Sheets writes.

### Phase 3 - UI Draft Lane
Show approved listing drafts in the UI with clear blocked/ready statuses.

Status:
- implemented in the operator UI under New Product Review as "Approved For Amazon Listing"
- local-only refresh runs F090/F091/F092
- local-only approval can mark a draft as `ready_for_amazon_preview`
- preview button runs F093 validation preview only
- live submit remains guarded by F094 CLI flags and exact draft IDs

### Phase 4 - Amazon Preview
Add validation preview only.

Status:
- implemented in `scripts/flows/F/F093_run_amazon_listing_preview.py`
- API wrapper hard-codes Listings Items `mode=VALIDATION_PREVIEW`
- preview pass changes a draft to `ready_for_live_submit`
- preview rejection changes a draft to `blocked_amazon_preview`
- preview issues are written to `amazon_listing_preview_issues_live`
- preview events are written to `amazon_listing_preview_events`
- isolated tests passed; real Amazon preview accepted all three controlled drafts

### Phase 5 - Guarded Live Submit
Status:
- implemented in `scripts/flows/F/F094_submit_amazon_listing_drafts.py`
- live submit requires exact draft IDs plus `--run-submit --confirm-live-submit`
- live request omits preview-only `includedData`
- three controlled drafts were accepted by Amazon with HTTP `200` and response status `ACCEPTED`

### Phase 6 - Reconciliation
Use Amazon read-back to confirm listing state before updating internal Product DB / operations loop.

Status:
- implemented in F095/F096.
- Kensington and JVC are confirmed Product-DB-eligible.
- Embryolisse is blocked and parked because Amazon brand approval/invoice risk is too high for this example.

### Phase 7 - Product DB Promotion Gate
Use O430 to build Product DB promotion candidates and O431 to stage Product DB create events only after all gates pass.

Status:
- implemented in O430/O431.
- live dry-run found `2` Amazon-clear candidates and `0` ready Product DB events.
- Kensington and JVC are held for missing profile fields.
- dry-run staged `0` Product DB edit events.

## Handoff Prompt For Next Chat
Continue the Review Pass To Amazon Listing feature from `project_control/F_REVIEW_PASS_TO_AMAZON_LISTING_PLAN.md`.

Start with missing Product Listing Profile data for Product DB promotion:
- use `out/systems/O/live/product_db_promotion_candidates_live.csv` and `out/systems/O/live/product_db_promotion_holds_live.csv` as the current gate evidence
- Kensington and JVC are Amazon-clear but held because Product DB profile fields are missing
- fill or repair purchase pack size, sold pack size, VAT rate/confirmation, supplier case quantity, valid order step, and MOQ before promotion
- extend the real Product DB/Sheet schema with the 9 missing destination fields before allowing O431 live staging
- keep Embryolisse parked because Amazon returned `ERROR 18304 You need approval to list this brand.`
- do not run O431 with `--stage-events --confirm-product-db-promotion` until O430 shows ready rows and the user approves staging
- do not change Google Sheets
- do not write `out/product_db_preview.csv` directly

## Last Updated
- 2026-05-01T13:10:43Z
