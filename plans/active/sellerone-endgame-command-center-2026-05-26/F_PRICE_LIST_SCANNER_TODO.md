# F Price-List Scanner Todo

Created: 2026-05-26
Owner flow: F
Business purpose: find new products and feed them safely into review, listing, and Product DB promotion.

## Source Plans To Read First

- `project_control/FEEDER_CYCLE_PLAN.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `project_control/F_SCANNER_SPEED_PRODUCTION_PLAN.md`
- `project_control/F_REVIEW_PASS_TO_AMAZON_LISTING_PLAN.md`
- `project_control/F_PRICE_LIST_SCANNER_LOGIN_MODE_DESIGN.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md`
- `plans/active/f-review-pass-to-amazon-listing-v1/CODING_PLAN.md`

## Current Evidence

- Live FPM status at `2026-05-26T08:27:35Z`: `blocked_storage_drift`.
- Blocking drift: `feeder_legacy_chart_daily_raw_live`.
- Drift detail: CSV has 7437 rows, SQL has 34450 rows, SQL timestamp is newer.
- Dashboard currently shows CLF recommended, DHB prioritised, ABGee queued, and Entertainment Trading needing a manual file.
- Feeder expectations say token-safe handoff checks and dropped/discontinued handling are still not started.
- Product DB promotion after Amazon listing is held because destination Product DB fields are missing.

## Plain-English Finish Line

The F scanner is finished for v1 when:

1. Supplier files are imported and normalized.
2. The scanner runs without storage or login blockers.
3. Completed supplier scans build review packs only after quality gates pass.
4. New Product Review decisions feed Product Listing Profile Review.
5. Approved listing/profile rows can become Amazon listing drafts.
6. Product DB promotion happens only after Amazon acceptance and read-back, and only with complete profile fields.

## Phase 0 - Clear Current F Blocker

- [ ] Investigate `blocked_storage_drift` before scanner resume.
- [ ] Identify why SQL has 34450 rows while CSV has 7437 rows for `feeder_legacy_chart_daily_raw_live`.
- [ ] Do not auto-reconcile until source authority is proven.
- [ ] Decide whether CSV is stale export, SQL is correct current source, or SQL contains bad accumulated state.
- [ ] Record the chosen repair path in this file before running any repair.

Success condition:
- FPM can leave `blocked_storage_drift` without losing newer scanner evidence.

## Phase 1 - Finish Production-Line Scanner Rollout

- [ ] Review the May 22 split-production proofs and mark what is still disabled by default.
- [ ] Decide next safe split-enforced proof size after 50 rows.
- [ ] Confirm production-line stage handoffs reconcile input rows to passed, blocked, and retry rows.
- [ ] Confirm browser-last routing avoids repeated API calls.
- [ ] Confirm login-required rows stay in script-owned Login Mode.

Success condition:
- Scanner can process larger batches faster without raising Amazon throttling or browser block risk.

## Phase 2 - Finish Review Handoff Gate

- [ ] Confirm FPM140 readiness gate still blocks incomplete supplier runs.
- [ ] Confirm FPM150 review packs are immutable.
- [ ] Confirm FPM155 AI gate controls operator-ready rows.
- [ ] Confirm current scanner FAIL rows cannot appear in New Product Review.
- [ ] Confirm rescan rows are promoted ahead of ordinary rows and stale decisions are archived.

Success condition:
- The user sees only review-ready products, not raw scanner output.

## Phase 3 - Plan Seller Central SMS 2FA Path

- [ ] Use `goal_files/GOAL_F-009_plan_seller_central_sms_2fa_path.md`.
- [ ] Read `C:\Users\Luke\Downloads\deep-research-report (21).md`.
- [ ] Decide whether SP-API can avoid Seller Central browser login for the target workflow.
- [ ] If SMS automation is still needed, choose iPhone Shortcuts relay, GSM modem, or virtual-number backup path.
- [ ] Keep script-owned visible Login Mode as the default scanner login recovery unless a safer automated path is approved.

Success condition:
- The scanner has a clear 2FA plan with manual fallback, no repo-stored secrets, and no OTP logging.

## Phase 4 - Finish New Product Review To Listing

- [ ] Review `f-review-pass-to-amazon-listing-v1` current phase.
- [ ] Complete missing Product Listing Profile fields for Kensington and JVC only if user approves.
- [ ] Keep Embryolisse parked unless brand approval decision changes.
- [ ] Keep O431 Product DB promotion dry-run unless explicit promotion flags and approval are given.
- [ ] Fix Product DB destination schema before any Product DB create-event staging.

Success condition:
- Amazon-clear products can be promoted only when profile fields and destination Product DB fields are complete.

## Phase 5 - Token-Safe Handoff And Lifecycle

- [ ] Define token-safe handoff checks for approved new products.
- [ ] Confirm pending lot-level tokens are created at PO stage only.
- [ ] Confirm available unit-level tokens are created at receiving stage only.
- [ ] Ensure no new product becomes sellable/repricer-visible before clean Product DB and Amazon listing state exists.

Success condition:
- New products join the buying and COGS system without breaking token traceability.

## Phase 6 - Dropped And Discontinued Handling

- [ ] Implement or verify `Dropped` as recoverable.
- [ ] Implement or verify `Discontinued` as terminal.
- [ ] Create clear review lanes so dropped products do not vanish silently.

Success condition:
- Bad products are not repeatedly rescanned forever, but recoverable products can re-enter when conditions change.

## Stop Conditions

Stop before changing anything if:

- FPM is actively scanning and the task would overwrite live active-run files
- storage drift root cause is unclear
- login recovery would use a separate Chrome window instead of script-owned F061 Login Mode
- Product DB writes would occur
- Amazon live submit would occur
