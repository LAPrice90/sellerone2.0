# B Marketplace Coverage Audit Blueprint

Created UTC: 2026-05-27T11:15:00Z

## What This Is
B is not allowed to be treated as proved just because UK orders look current.

B must prove order coverage by marketplace:
- UK
- Ireland
- Amazon.ae
- Saudi
- Non-Amazon marketplace rows
- any other marketplace where SellerOne is participating or where Sellerboard shows activity

## Why This Exists
Sellerboard showed one shipped Amazon.ae order that SellerOne did not match:
- order: `171-1388771-2409132`
- sales channel: `Amazon.ae`
- SKU: `GH-XAAE-HRU7`
- ASIN: `B072K2PG11`
- purchase date: 2026-05-23

Luke confirmed the order exists in Amazon Seller Central.

This means a single-order recovery is not enough. The manager must check whether B is missing a whole marketplace, not just one order.

## Current Read-Only Evidence
Current local B order proof shows:
- UK orders are current through 2026-05-27.
- Ireland orders are current in the Sellerboard sample and match the bridge sample.
- Amazon.ae exists in old local order proof, but the latest local Amazon.ae order found is 2026-02-13.
- Sellerboard shows an Amazon.ae shipped order on 2026-05-23 that local B proof does not contain.
- Saudi exists only as old local evidence in the current order files.
- Non-Amazon rows exist and need separate treatment because their order status can differ from Sellerboard.

## Current Manager Report Result
The read-only marketplace coverage report is implemented.

Latest manager result:
- participating marketplaces: 17
- local order marketplaces currently visible: 5
- Sellerboard marketplaces in the manual sample: 4
- Amazon.ae: fail, because Sellerboard has 1 shipped order missing from local B proof
- Ireland: ok in the manual Sellerboard sample
- UK: warning, because there are status differences but no missing shipped order in the sample
- Non-Amazon: warning, because Sellerboard and local status differ
- Saudi: not checked for current activity, because only old local history is visible

Plain English meaning: the confirmed hard gap is Amazon.ae coverage. UK and Non-Amazon need follow-up review, but they are not currently the same as a missing shipped order.

## Likely Root Cause Shape
The likely issue is marketplace coverage, not a random SKU lookup problem.

The normal B order pull uses one marketplace at a time and defaults to the UK marketplace.

The order cursor is shared. If the shared cursor advances because UK orders are current, it can hide older or quieter non-UK marketplace orders unless each marketplace has its own coverage proof.

The orphan-recovery helper can loop marketplaces, but it prefers marketplaces already showing local order activity in the target window. If Amazon.ae has no local activity in that window, it may be skipped exactly when it is needed most.

## Manager Expectation
B manager proof must answer:
- Which marketplaces are in scope?
- Which marketplaces had Sellerboard activity?
- Which marketplaces had local B order activity?
- What is the latest local order date per marketplace?
- Does each marketplace have order rows, item rows, level 1 rows, and order master rows?
- Are refunds and fees present by marketplace?
- Is any marketplace stale while UK looks current?

## MOT Proof Check
Add or extend read-only B MOT checks for:
- marketplace participation list present
- latest local order by marketplace
- Sellerboard sales channel comparison by marketplace
- per-marketplace order row count
- per-marketplace item row count
- per-marketplace level 1 row count
- per-marketplace order master row count
- marketplace with Sellerboard activity but no matching local B activity
- shared cursor risk where UK marker is fresh but another marketplace is stale

The old B checklist remains only a clue.

## Bounded Worker Task
Create a worker task to build a read-only B marketplace coverage report.

Allowed:
- inspect B order-pull code
- inspect local order, item, finance, refund, and order-master proof
- inspect Sellerboard bridge output
- create or update manager reports and MOT checks
- write tests for the manager report and MOT checks

Forbidden:
- no B run
- no B restart
- no marker edit
- no lock or maintenance marker edit
- no Google Sheets write
- no local DB alignment
- no output deletion
- no order, token, refund, fee, or ROI data correction
- no price or queue change

## Retest Rule
This is not proved by a code edit.

Proof requires:
- marketplace coverage report runs read-only
- B MOT reads the marketplace coverage report
- Sellerboard marketplace activity is compared with local B marketplace activity
- missing or stale marketplace coverage creates bounded work items
- the same MOT check clears after a valid approved recovery or proof change

## Luke Decision Boundary
Stop for Luke before:
- adding Amazon.ae to normal live B runtime
- running Amazon.ae backfill
- running or restarting B
- changing order markers
- changing locks or maintenance markers
- writing Sheets
- editing local database facts
- correcting missing orders manually
- feeding Sellerboard bridge values into live ROI or restocking
- widening beyond B order-marketplace coverage

## Plain English Summary
Do not fix one missing order and move on.

First prove whether B is seeing every marketplace it should see. If a marketplace is quiet, the manager must not assume it is healthy just because UK is busy.
