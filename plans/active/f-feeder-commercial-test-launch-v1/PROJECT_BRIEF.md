# Project Brief

## Title
- F feeder commercial test launch

## Why this exists
- We now have enough sold-truth evidence to stop treating the predictor as an exact future-forecast tool.
- The next job is to use the feeder on real new-product candidates from the live supplier file in a controlled way.
- The commercial aim is simple:
  - be a bit fussy
  - miss some upside if needed
  - avoid tying up cash in below-average listings that only grind out weak ROI

## Operating principle
- This phase is not about predicting the exact monthly unit count.
- This phase is about deciding:
  - is this worth testing at all
  - what is a safe starter quantity
  - what should be watched or rejected
- Lower-band logic is the control:
  - if the product still looks sensible on the conservative lower estimate, it can enter test-buy review
  - if it only works on the optimistic view, it should not be a live test candidate yet

## What this phase must achieve
- Finish the active live price-file screening path for the current supplier wave in a controlled way.
- Rebuild the live commercial review surface from current screening truth, not stale recommendation files.
- Give the user two practical review lists:
  - pass candidates worth test-buy review
  - near-miss candidates that only just failed, with explicit reasons
- Keep the user as final veto before any new-product test order is released.
- Move approved candidates into a small, monitored live-test lane.
- Measure live outcome against conservative bands and feed the result back into pass logic.

## What this phase must not do
- do not drift back into an exact-forecast project
- do not trust stale feeder recommendation or approval files as current live truth
- do not auto-approve new-product orders
- do not open multiple uncontrolled supplier waves at once
- do not hide weak products inside optimistic best-case estimates

## Current evidence that matters
- Sold-truth work is now good enough to support conservative commercial bands and false-red review.
- The active supplier queue is currently `stocklist_supplier` with queue state updated at `2026-04-21T10:34:51Z`.
- Current supplier-list health shows:
  - raw source rows: `42717`
  - canonical rows: `42663`
  - health state: `warn` only because holds are present
- Current screening row state for `stocklist_supplier` shows:
  - total rows: `42856`
  - `pending`: `32869`
  - `timeout`: `9721`
  - `pass`: `266`
- Current explicit pass output exists:
  - `feeder_legacy_first_checks_live.csv` -> `266` pass rows
- Current scrape evidence exists:
  - `feeder_legacy_scrape_evidence_live.csv` -> `4397` rows
  - `PASS`: `266`
  - `RESCAN`: `162`
  - `FAIL`: `3969`
- The current feeder recommendation and approval layer is not safe to use as live commercial truth for this wave:
  - `feeder_candidate_recommendations_live.csv` -> `9552` rows dated `2026-04-07`
  - `feeder_approval_queue_live.csv` -> `9552` rows dated `2026-04-07`
  - sample rows are from `shure_cosmetics`, not the active `stocklist_supplier` wave
  - `feeder_po_handoff_ready_live.csv` -> `0` rows
- No active `F061_run_legacy_first_checks_local.py` worker was observed at plan-creation time, so a clean controlled refresh window is available.

## End state
- one controlled launch path exists from live supplier file to user-reviewed test-buy shortlist
- one explicit near-miss review lane exists so borderline candidates are visible
- one small approved test-order lane exists with conservative starter quantities
- one monitoring loop exists so live test outcomes can tune the pass structure without chasing perfection
