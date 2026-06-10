# B Marketplace Coverage Report Diagnosis

Generated UTC: 2026-06-09T14:20:00Z
Job ref: `B-MARKETPLACE-COVERAGE-REPORT`
Packet: `tasks/approved/MOT_B_B_MARKETPLACE_COVERAGE_REPORT.md`
Worker type: read-only MOT diagnosis

## Plain-English Result

`b_marketplace_coverage_report` is not currently proved as `ok` because the latest report still has two warning rows.

This is not an active missing-order failure. It is a labelled comparison warning: Sellerboard and local B disagree on order status for two marketplace rows, but the current report shows zero missing shipped orders and zero shared cursor risk.

## Current Evidence

- Latest marketplace report:
  - `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_marketplace_coverage\b_marketplace_coverage_by_marketplace.csv`
  - observed UTC: `2026-06-09T14:00:04Z`
  - participating marketplaces: `17`
  - local order marketplaces: `5`
  - Sellerboard marketplaces: `4`
  - missing shipped orders: `0`
  - shared cursor risk rows: `0`
  - fail rows: `0`
  - warn rows: `2`

- Latest marketplace summary:
  - `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_marketplace_coverage\b_marketplace_coverage_summary.csv`
  - `overall_status=warn`
  - `marketplace_fail_rows=0`
  - `marketplace_warn_rows=2`
  - `marketplace_status_difference_warn_rows=2`
  - `sellerboard_missing_shipped_orders=0`
  - `shared_cursor_risk_rows=0`

- Latest MOT row:
  - `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
  - observed UTC: `2026-06-09T14:00:37Z`
  - work item: `MOT_B_B_MARKETPLACE_COVERAGE_REPORT`
  - status: `parked`
  - root cause guess: `Marketplace coverage is warning-labelled, but no missing shipped order or shared cursor risk is active.`
  - notes: `participating=17;local_markets=5;sellerboard_markets=4;fail_rows=0;warn_rows=2;status_diff_warn_rows=2. Marketplace coverage is warning-labelled, not failed. Current warnings are comparison/status rows and there is no missing shipped-order or shared-cursor failure.`

## Warning Rows

| Marketplace | Channel | Warning |
|---|---|---|
| `A1F83G8C2ARO7P` | `Amazon.co.uk` | Sellerboard and local B status differ on 13 rows. |
| `AZMDEXL2RVFNN` | `Non-Amazon` | Sellerboard and local B status differ on 1 row. |

## Code Path Read

- `sellerone_manager/hourly_mot.py` builds the marketplace report read-only through `build_b_marketplace_coverage_report`, then writes manager proof outputs under `out/systems/M/b_marketplace_coverage`.
- The same MOT code marks `b_marketplace_coverage_report` as `warn` when the report status is warning-only.
- The controlled warning logic parks this work item when proof contains `fail_rows=0` and status-difference warning rows, because that means the current issue is a visible comparison warning, not a live missing-order or shared-cursor failure.
- `sellerone_manager/b_marketplace_coverage.py` classifies status differences as `warn`, not `fail`, and only promotes missing shipped marketplace activity or shared cursor risk into harder marketplace proof checks.

## Diagnosis

The original approved packet was created when the marketplace coverage lane still needed repair/proof design. The current evidence shows that the risky parts of the lane have cleared:

- no Sellerboard shipped orders are missing locally
- no shared cursor risk is active
- the separate `b_marketplace_sellerboard_gaps` check is `ok`
- the separate `b_marketplace_shared_cursor_risk` check is `ok`

The only remaining reason `b_marketplace_coverage_report` is not `ok` is that the overall report deliberately stays `warn` while Sellerboard/local status comparison differences remain visible.

That means the safe status for this pass is not `fixed_needs_retest`, because no code fix was made and no repair is being claimed. It is also not `blocked_needs_luke`, because no protected Luke decision is needed for read-only comparison warnings.

## Recommended Next Safe Status

Recommended next safe status: `ready for a later bounded repair/retest worker`

Recommended shape:

- A later bounded worker should decide whether `b_marketplace_coverage_report` should remain a parked warning while `b_marketplace_sellerboard_gaps` and `b_marketplace_shared_cursor_risk` prove the hard risks, or whether the MOT proof rule should be tightened so warning-only status differences no longer keep this specific packet in the active approved queue.
- The later worker may retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` only if Operations approves a repair/retest pass.

## Boundaries Preserved

- Did not run B runtime.
- Did not restart B.
- Did not edit locks or maintenance markers.
- Did not write Google Sheets.
- Did not change prices, queues, tokens, business data, local DB, or Product DB.
- Did not delete, move, archive, compress, or purge outputs.
- Did not implement code changes.
