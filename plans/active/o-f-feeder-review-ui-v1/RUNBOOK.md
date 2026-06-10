# Runbook

## Purpose
- explain how the temporary feeder review UI should work once implemented

## Intended use
1. Open the operator UI.
2. Go to `New Product Review`.
3. Pick a lane and review batch.
4. Read the commercial card for each row.
5. mark `Pass` or `Fail`
6. add a note
7. click `Send Batch for Analysis`

## Inputs
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

## Proposed write path
- intake:
  - `out/systems/F/inbox/feeder_review_events.csv`
- applied log:
  - `out/systems/F/live/feeder_review_log.csv`
- analysis:
  - `out/analysis_reports/f_feeder_review_gap_analysis_latest.csv`

## Safety rules
- do not write into `restock_decision_events.csv`
- do not write straight into `feeder_approval_decisions_log.csv`
- do not create PO-ready rows from this page directly

## ASIN link rule
- uppercase ASIN text
- if shorter than 10 characters, left-pad with `0`
- open:
  - `https://www.amazon.co.uk/dp/<asin_padded>`

## What good looks like
- the page feels like the restocker
- the user can review quickly without reading raw codes
- each reviewed row produces a durable event
- analysis can later answer:
  - why did the user fail model passes
  - why did the user pass near misses
  - what fields are still missing from the commercial review surface
