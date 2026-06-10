# Status Report - 2026-04-14

## Purpose
- This report states, plainly:
  - what Batch 001 actually achieved
  - what the plan still does not have
  - why the next blocker is scrape coverage, not more scoring logic
  - what has to happen before tonight's normal scan can be trusted to collect the fuller BBP data set we now know we need

## Plan Goal
- The active plan is trying to answer one business question truthfully:
  - if we buy this now, what monthly sales and profit should we expect at our economics
- To do that safely, the system needs:
  - trusted completed-month demand
  - price-qualified demand
  - clear pass/fail/manual-review output
  - enough raw history coverage to decide how to interpret seasonality, stability, and recent drift

## What We Achieved vs The Plan

### 1. Demand truth contract
- Planned:
  - stop using current partial month and future predicted bars as trusted demand
- Achieved:
  - `Webscrape.py` now exposes completed/current/future BBP month fields
  - `F071` now allows `ready` rows only when the demand basis is trusted:
    - `bbp_last_completed_month`
    - `bbp_zero_history`
- Result:
  - the decision path no longer quietly promotes fallback demand into trusted demand

### 2. Raw demand vs price-qualified demand
- Planned:
  - split raw observed demand from demand available to us at our economics
- Achieved:
  - `F071`, `F072`, and `F073` now carry:
    - raw monthly units
    - price-qualified monthly units
    - price-qualified monthly profit
- Result:
  - the output can now fail a row because the market only sells below our floor

### 3. Monthly profit floor
- Planned:
  - align the commercial rule with the user
- Achieved:
  - policy default is now `GBP 20` expected monthly profit
  - summary output exposes simple `decision_state`
- Result:
  - rows can now fail for a direct business reason rather than hiding behind technical labels

### 4. Health and proof
- Planned:
  - health must show stale or mixed truth, not hide it
- Achieved:
  - `F074` now checks:
    - health staleness
    - demand basis integrity
    - price-qualified demand integrity
    - decision floor integrity
    - join resolution on ready rows
- Result:
  - the old demand-basis warning is gone because the system now refuses to trust fallback demand

### 5. Validation exports
- Planned:
  - produce one-off exports the operator can check against live Amazon/BBP
- Achieved:
  - `F004` sampled-ASIN audit exists
  - `F005` monthly validation export exists
- Result:
  - the system has a durable audit path outside the daily loop

## Current Live State

### F outputs
- `feeder_backtest_input_view_live.csv`
  - rows: `1542`
  - ready: `300`
  - manual_review: `1242`
- `feeder_backtest_summary_live.csv`
  - rows: `1542`
  - decision states:
    - `manual_review`: `1242`
    - `fail`: `249`
    - `pass`: `51`
- `feeder_backtest_health.csv`
  - rows: `16`
  - status counts:
    - `ok`: `15`
    - `warn`: `1`

### Remaining health alert
- Current warning:
  - `f_backtest_manual_review_share = warn`
  - value: `0.8054`
- Meaning:
  - the logic is now stricter and safer, but too many rows still lack trusted completed-month evidence

### Sample audit state
- `f_backtest_bbp_sales_sample_audit_latest.csv`
  - rows: `18`
  - mismatches: `18`
  - mismatch reason:
    - `fallback_basis_no_trusted_month`
- Meaning:
  - the sampled audit is now pointing at the true root cause:
    - missing trusted month capture
    - not downstream math

## Root Cause Of What Remains
- The current blocker is not the pass/fail logic.
- The current blocker is evidence coverage.

### Current scrape evidence coverage
- `feeder_legacy_scrape_evidence_live.csv`
  - rows: `1581`
  - supplier: `stocklist_supplier`
  - rows with chart month labels: `303`
  - rows with completed-month fields populated: `330`
  - rows with current-month fields populated: `330`
  - rows with future-month-ignore count populated: `330`
  - rows with replay basis populated: `330`
  - rows missing full chart basis despite having an ASIN: `1251`

### Basis-source split in scrape evidence
- blank replay basis: `1251`
- `bbp_last_completed_month`: `303`
- `bbp_zero_history`: `21`
- `bbp_current_month_fallback`: `6`

### Why this matters
- Batch 001 correctly tightened trust.
- But only about `21%` of current scrape evidence rows actually carry the full BBP month fields needed to pass that trust gate.
- That is why `manual_review_share` is high.

## Current Scrape List Reality

### Active run
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - rows: `33204`
  - supplier: `stocklist_supplier`
  - all rows currently `pending`

### Supplier-specific queue
- `out/systems/F/inbox/suppliers/stocklist_supplier/active_run.csv`
  - rows: `33204`
- `out/systems/F/inbox/suppliers/stocklist_supplier/canonical_current.csv`
  - rows: `42663`

### Important operational mismatch
- Checked-in runner batch files are:
  - `run_F_shure_full_legacy_scan.bat`
  - `run_F_shure_test_mode_scan_once.bat`
- Live queue and evidence are:
  - `stocklist_supplier`
- Meaning:
  - the checked-in runner path does not line up with the current supplier queue we actually need to recover

## What This Means For Tonight
- We should not pretend that a normal overnight loop will refresh the whole current list.
- The active queue is too large (`33204` pending rows).
- The current evidence gap is specific:
  - `1251` rows already have ASINs but still lack full BBP month fields
- So the right order is:
  1. validate a handful of ASINs live
  2. target the missing-coverage rows first
  3. rebuild F outputs
  4. then restore the supplier to its normal full queue for the overnight run

## Handful-Of-ASIN Validation Pack
- Use these first because they cover the three cases we care about:
  - trusted completed month present
  - explicit zero history
  - missing full month fields

### Trusted completed month present
- `https://www.amazon.co.uk/dp/B0C486SM3R`
- `https://www.amazon.co.uk/dp/B0BXSMFFPN`
- `https://www.amazon.co.uk/dp/B08NFZYX7Y`
- `https://www.amazon.co.uk/dp/B09R85ZDLH`

### Explicit zero history
- `https://www.amazon.co.uk/dp/B06XDLPVNS`

### Missing full month fields
- `https://www.amazon.co.uk/dp/B091BPSRXL`
- `https://www.amazon.co.uk/dp/B0CX1XW3L9`

## What Still Remains In The Plan

### Not done yet
- scrape coverage recovery
- live ASIN validation against BBP for the current supplier set
- seasonality rules
- recent-vs-baseline classification
- confidence model
- Amazon sold-in-last-30-days validation lane
- post-purchase 90-day learning loop

### Immediate blocker before those
- we need materially better BBP chart coverage from the scraper first

## Recommended Next Steps

### Step 1 - validate the mixed ASIN pack
- Goal:
  - confirm the scraper fields match what BBP is showing for:
    - trusted completed month
    - zero history
    - missing-field rows
- Output needed:
  - a short checked list saying each ASIN is:
    - correct
    - zero-history correct
    - missing fields and needs rescrape

### Step 2 - build a targeted rescrape subset for the current supplier
- Goal:
  - do not start with all `33204` pending rows
  - target the `1251` rows that already have ASINs but still do not have full BBP month fields
- Required behavior:
  - temporary subset queue for `stocklist_supplier`
  - no hand-editing of evidence rows
  - normal queue must be restorable afterwards

### Step 3 - run targeted recovery before the overnight loop
- Goal:
  - lift coverage on trusted completed-month capture before the normal run
- Proof needed:
  - `feeder_legacy_scrape_evidence_live.csv` shows higher completed-month coverage than `330`
  - sampled missing-field ASINs move into either:
    - trusted completed month
    - explicit zero history
    - explicit scrape failure reason

### Step 4 - rebuild F truth after the rescrape
- Required rebuild chain:
  - `F070`
  - `F071`
  - `F072`
  - `F073`
  - `F074`
  - `F004`
  - `F005`
- Proof needed:
  - ready row count rises
  - `manual_review_share` falls
  - sampled audit mismatch count falls

### Step 5 - restore normal supplier queue and run overnight
- Goal:
  - go back to normal scanning after the targeted recovery
- Restore path:
  - use the supplier reset workflow from `F062_reset_supplier_test_mode.py` style behavior to rebuild the full queue from `canonical_current`
- Required operational truth:
  - the overnight runner must point at `stocklist_supplier` if that is still the active supplier queue

## Tonight Go / No-Go

### Good enough to run overnight
- mixed ASIN validation confirms the new BBP fields are being captured truthfully
- targeted rescrape subset exists
- queue restore path is defined and tested
- runner points at the correct supplier
- F rebuild after targeted rescrape shows improved coverage

### Not good enough to run overnight
- we still do not know whether the current active queue is being run by the right supplier path
- ASIN checks show the scraper is still missing fields on rows that should have them
- there is no safe restore path from targeted subset back to the full queue

## Bottom Line
- Batch 001 fixed the decision truth problem.
- It did not fix scrape coverage.
- The next real job is to recover BBP chart coverage on the current supplier list, prove it on a handful of ASINs, and only then let the overnight scan run as the normal collection path.
