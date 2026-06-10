# TASK B Marketplace Coverage Report

Created UTC: 2026-05-27T11:15:00Z

Status: implemented as manager-only read-only proof.

Latest proof:
- marketplace coverage report builds read-only
- B MOT reads marketplace coverage evidence
- targeted manager tests passed
- Amazon.ae remains not yet proven because Sellerboard shows a shipped order missing from local B proof
- no B run, restart, marker edit, Sheet write, local DB alignment, output deletion, or business data correction was performed

## Goal
Build a read-only manager report that proves whether B is covering every marketplace that matters, instead of only proving the UK order stream.

## Manager Expectation
The report must show:
- marketplaces SellerOne participates in
- marketplaces appearing in local B order proof
- marketplaces appearing in Sellerboard bridge proof
- latest order date by marketplace
- order rows, item rows, level 1 rows, order master rows, refund rows, and fee rows by marketplace where available
- marketplaces with Sellerboard activity but missing local B activity
- marketplaces that are stale while UK is fresh

## MOT Proof Check
The B MOT should create a bounded work item when:
- Sellerboard shows marketplace activity missing from local B proof
- a marketplace has orders but missing item rows
- a marketplace has orders/items but missing downstream finance/order-master proof
- a non-UK marketplace is stale beyond the allowed cadence while UK is fresh
- the shared marker creates a risk that non-UK orders are being skipped

## Allowed Files
- `sellerone_manager/hourly_mot.py`
- `sellerone_manager/sellerboard_bridge.py`
- `sellerone_manager/blueprints/B_MARKETPLACE_COVERAGE_AUDIT_BLUEPRINT.md`
- new manager-only report module under `sellerone_manager/`
- manager tests under `tests/manager/`

## Forbidden Actions
- no B run
- no B restart
- no order backfill
- no marker edit
- no lock or maintenance marker edit
- no Google Sheets write
- no local DB alignment
- no output deletion
- no manual order correction
- no token, refund, fee, shipping, or ROI data correction
- no price or queue change
- no scope outside B marketplace coverage

## Acceptance Checks
- Manager report runs read-only.
- Report includes Amazon.ae, Ireland, UK, Saudi, and Non-Amazon if present in current proof.
- Report labels current Amazon.ae coverage as not yet proven for the May 2026 window unless new proof exists.
- B MOT treats old checklist FAIL/WARN only as clues.
- B MOT uses independent marketplace proof as manager truth.
- Tests prove a Sellerboard-only marketplace order creates a bounded B work item.

## Stop Condition
Stop and return to Luke if the next step requires any live B run, backfill, marker change, lock change, Sheet write, database alignment, output deletion, or business-data correction.
