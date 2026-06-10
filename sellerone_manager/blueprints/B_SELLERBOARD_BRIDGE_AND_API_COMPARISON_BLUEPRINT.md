# B Sellerboard Bridge And API Comparison Blueprint

## Purpose
B should prove the 7-day order picture from outside the B loop:
- orders
- units
- order status
- SKU mapping
- shipping
- commission and FBA fees
- refunds
- ROI support fields

Sellerboard is a temporary second ruler while direct API access is incomplete. It is not the permanent source of truth.

## Manager Expectation
The manager must never say B is proved just because B's own files look tidy.

For this bridge, the manager should prove:
- the Sellerboard export has the expected columns
- Sellerboard shipped orders are present in SellerOne
- Sellerboard product/ASIN rows map back to SellerOne SKUs
- return rows are separated from purchase-window order rows
- refunds, shipping, commission, FBA fee, and ROI gaps are labelled clearly
- every bridge value is labelled as `API proved`, `Sellerboard bridge estimate`, or `not yet proven`

## MOT Proof Check
The B MOT reads the bridge report only after the report has been built.

It checks:
- bridge report exists and is fresh enough
- bridge output columns are stable
- Sellerboard shipped orders are not missing from SellerOne
- Sellerboard shipped rows map to SKUs
- refund, fee, and ROI gaps are visible as warnings, not hidden inside ROI

Missing Sellerboard bridge evidence is `not_checked`, not B runtime proof.

## Bounded Worker Task
If Sellerboard proves a shipped order is missing from SellerOne, or a shipped row cannot map to a SKU, the manager can create a bounded B task:
- inspect Sellerboard bridge report
- inspect local order and item proof
- repair parser/proof mapping if the report is wrong
- do not backfill data, run B, restart B, write Sheets, or alter ROI

## Retest Rule
A fix is proved only when:
- the Sellerboard bridge report is rebuilt read-only
- the same B MOT check clears
- the report still labels bridge values as bridge values

Code edits alone are not proof.

## Luke Decision Stops
Stop for Luke before:
- using Sellerboard bridge values inside live ROI or restocking decisions
- running or restarting B
- writing Google Sheets
- changing prices or queues
- aligning local database facts
- deleting outputs
- correcting token, order, refund, or fee data
- treating Sellerboard as the permanent replacement for direct API proof

