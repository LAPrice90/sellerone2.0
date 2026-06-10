# Chrome Full Capture Guide

## Purpose
- Define how Codex should use Chrome to capture the full BBP and Amazon evidence set for an ASIN.
- Stop adding one more field at a time.
- Capture the full page state once, normalize it once, and only then decide which fields matter for decision logic.

## Plain-English rule
- Capture first.
- Derive second.
- Drop later.

That means:
- the scraper should not start by asking "which 3 fields do we need today?"
- it should ask:
  - what is the full evidence state on the page right now
  - how do we save it in raw form
  - how do we normalize it into stable tables
  - which derived fields are safe to trust

## Why this is needed
- Current sales-history logic is stronger than before, but scrape coverage is still weak.
- We already know the BBP sales chart can mislead if:
  - current month is treated as trusted demand
  - future predictions leak into demand basis
  - a field is missing and fallback logic quietly takes over
- The fix is not more downstream adjustment.
- The fix is a fuller capture contract at the Chrome page level.

## What Codex should do in Chrome

### Job
- Open the real Chrome profiles already used by F automation.
- Visit the actual BBP and Amazon pages for each ASIN.
- Wait for the page to finish loading.
- Capture the whole evidence area, not just the few fields currently consumed.
- Save raw artifacts and normalized outputs separately.

### Existing runtime we should build on
- Existing Chrome automation already exists in:
  - [F061_run_legacy_first_checks_local.py](C:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/F/F061_run_legacy_first_checks_local.py)
  - [Webscrape.py](C:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/F/legacy_scanner_2_1/Webscrape.py)
- Existing BBP profile wiring already exists:
  - UC136 BBP profile
  - Chrome 91 fallback profile for Amazon product-info/date scraping
- Existing snapshot path already exists:
  - [bbp_section_snapshots](C:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/F/legacy_scanner_2_1/logs/bbp_section_snapshots)

## Core design

### Layer 1 - Raw capture
- Save what Chrome actually saw.
- No business interpretation.
- No pass/fail.
- No fallback math.

### Layer 2 - Normalized facts
- Parse the raw capture into stable tables.
- Keep every field explicit.
- Use blanks and status codes instead of silent fallback.

### Layer 3 - Derived model fields
- Only after raw and normalized layers are stable.
- This is where:
  - trusted completed month
  - qualified demand
  - seasonality
  - recent-vs-baseline
  - confidence
  - pass/fail
  should be derived.

## What to capture for every ASIN

### Session metadata
- run id
- observed UTC
- ASIN
- source URL
- Chrome profile used
- page title
- final URL after redirects
- load timing markers
- capture status

### Raw BBP section
- Full node snapshot for the BBP evidence area
- Existing selectors already prove useful:
  - `#quickInfoEstSales`
  - `#quickInfoRoi`
  - `#quickInfoBsr`
  - `#estSalesMonthlyChart`
  - `#asinAverageStatisticsDataTable`
  - `#calculatorSellPrice`
- Capture:
  - text
  - ids
  - classes
  - attributes
  - relevant `data-*` attributes
  - short outer HTML

### Raw chart state
- Save the Chart.js state if available.
- Save:
  - chart ids found
  - dataset labels
  - month labels
  - month units
  - series ordering
  - current month bar
  - future predicted bars
  - any tooltip-derived values if needed
- Treat the chart object as the primary truth for monthly sales, not hover text alone.

### Raw tables and cards
- Save all visible BBP cards and tables in the capture zone:
  - quick info card
  - estimated sales calculator summary tiles
  - monthly sales chart labels and values
  - average statistics table
  - pricing calculator values
  - eligibility
  - hazmat
  - IP risk
  - overview section
  - product info where exposed in BBP
  - variations section if present

### Raw Amazon page support data
- Save the supporting Amazon page facts from the Amazon tab/session:
  - title
  - brand
  - category
  - product info text
  - release date if present
  - ratings and review count
  - sold in last 30 days text if present
- This should remain support evidence, not replace the BBP chart.

### Screenshots
- Save screenshot evidence for operator review.
- Minimum:
  - one full BBP evidence area screenshot
  - one screenshot around the sales estimator/chart
  - one screenshot around Amazon sold-in-last-30-days text if present

## Output datasets we should keep

### Dataset A - Raw capture manifest
- One row per ASIN run
- Purpose:
  - show whether capture happened
  - where the artifacts live
  - which browser/profile/session produced them

### Dataset B - Raw JSON snapshot
- One JSON file per ASIN run
- Purpose:
  - the exact raw browser evidence
  - future parser changes can re-read this without reopening Chrome

### Dataset C - Monthly chart points table
- One row per ASIN + month point + capture run
- Purpose:
  - month-by-month truth table
- Keep:
  - label shown
  - parsed month key
  - units
  - point class:
    - completed_history
    - last_completed
    - current_partial
    - future_predicted

### Dataset D - Normalized listing facts
- One row per ASIN run
- Purpose:
  - stable flat facts parsed from the raw snapshot
- Examples:
  - title
  - BSR%
  - ROI
  - est sales quick info
  - prev 90d
  - cur 30d
  - next 90d
  - avg/mo
  - next month
  - best/worst month
  - buy price
  - sell price
  - break-even
  - profit
  - eligibility
  - hazmat
  - IP

### Dataset E - Discrepancy report
- One row per ASIN + field + run comparison
- Purpose:
  - make instability explicit
  - never hide scrape disagreement behind fallback logic

## How the 10-ASIN audit should work

### Goal
- Prove that the full capture contract is stable enough before we promote any of it into daily logic.

### Sample design
- Use about 10 ASINs with mixed behaviour:
  - 3 trusted completed-month cases
  - 2 explicit zero-history cases
  - 3 missing-basis or weird cases
  - 1 high-volume / likely predicted-bar case
  - 1 likely seasonal or irregular case

### Run design
- For each ASIN, do 3 passes:
  1. first live capture in an existing BBP Chrome session
  2. second capture after page refresh
  3. third capture after browser restart or fresh automation session

- That gives:
  - 10 ASINs
  - 3 runs each
  - 30 raw captures

### What we compare
- Compare raw normalized facts across the 3 runs.
- Compare monthly chart points across the 3 runs.
- Compare screenshot evidence where parser disagreement appears.

## How to judge consistency

### Must match exactly
- ASIN
- page title family
- chart source id
- month label order for completed months
- last completed month label
- last completed month units
- zero-history classification when there is no history
- field presence flags

### Allowed to drift slightly
- current month units
- next month prediction
- live sell price
- live BSR
- live Buy Box

### Must not be trusted yet
- any field that changes across runs without a clear page-state reason
- any field that only appears when hover logic succeeds
- any field that depends on future predicted bars

## Discrepancy classes
- `page_not_ready`
- `chart_not_loaded`
- `chart_loaded_but_dataset_missing`
- `field_present_but_parser_failed`
- `field_missing_in_dom`
- `current_month_drift`
- `future_prediction_drift`
- `account_state_difference`
- `profile_state_difference`
- `tooltip_dependency_unstable`
- `html_shape_changed`
- `unknown`

## Implementation plan

### Section 1 - One-off capture runner
- Job:
  - create a one-off script that opens Chrome and captures the full raw evidence set for a supplied ASIN list
- Expectations:
  - visible Chrome session
  - no headless-only truth
  - JSON snapshot + screenshot + manifest row written for each ASIN
- Tests:
  - smoke test on a small fixture
  - parser handles missing nodes without crashing
- Sign-off:
  - all expected artifact files exist for a single ASIN run

### Section 2 - Normalization layer
- Job:
  - parse the raw JSON into flat facts and monthly-point tables
- Expectations:
  - raw files remain untouched
  - normalized files contain explicit blanks and status codes
- Tests:
  - fixture-driven parser tests
  - month classification tests for completed/current/future
- Sign-off:
  - same raw file always produces the same normalized rows

### Section 3 - 10-ASIN consistency audit
- Job:
  - run the one-off capture against about 10 ASINs and compare 3 passes each
- Expectations:
  - discrepancy report produced
  - unstable fields clearly marked
  - stable fields identified for production use
- Tests:
  - audit summary generation test
  - discrepancy bucketing test
- Sign-off:
  - stable core field set agreed from evidence, not guesswork

### Section 4 - Production contract update
- Job:
  - update F scrape contracts to use only the stable normalized fields
- Expectations:
  - no daily loop uses raw JSON directly
  - no silent fallback on missing trusted fields
- Tests:
  - F-scoped pytest
  - one-off replay of the audit pack
- Sign-off:
  - manual-review share and mismatch rates improve from the new capture path

### Section 5 - Field pruning
- Job:
  - decide what we actually need for business logic after the full capture exists
- Expectations:
  - we drop unused derived fields later
  - we do not shrink raw capture just because a field is not used today
- Tests:
  - schema tests
  - consumer contract tests
- Sign-off:
  - raw capture remains broad, derived model remains focused

## What "good" looks like
- Codex opens Chrome using the real BBP profile.
- Each ASIN run writes:
  - raw JSON
  - screenshots
  - normalized facts
  - monthly chart rows
  - discrepancy status
- We can rerun parsers against old raw captures without reopening Chrome.
- We can prove which fields are stable across 10 ASINs.
- Decision logic then uses only the proven stable fields.

## What "bad" looks like
- We keep scraping a new tiny slice every time a question changes.
- We only keep derived values and throw away raw page evidence.
- We cannot explain why a field changed.
- We patch CSV outputs by hand.
- We promote fields into decision logic before proving they are stable.

## Sign-off checklist
- [x] One-off Chrome full-capture runner exists
- [x] Raw JSON artifact exists per ASIN run
- [x] Screenshot artifact exists per ASIN run
- [x] Normalized fact table exists
- [x] Monthly chart point table exists
- [x] 10-ASIN audit pack exists
- [x] 3-pass comparison exists for each ASIN
- [x] Discrepancy report exists
- [ ] Stable production field set agreed
- [ ] Production consumers use stable fields only

## Immediate next step
- Build the one-off full-capture runner first.
- Do not jump straight to production parser changes.
- The first proof target is:
  - 10 ASINs
  - 3 passes each
  - full raw capture
  - discrepancy report

## Why this is the right order
- Once the raw capture is complete, we can answer future questions from saved evidence.
- That means:
  - less blind scraping
  - less guesswork
  - less one-field-at-a-time rework
  - better confidence in what should and should not drive decisions
