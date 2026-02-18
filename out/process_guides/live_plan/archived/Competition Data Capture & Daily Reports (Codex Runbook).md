# Phase — Competition Data Capture & Daily Reports (Codex Runbook)

## Purpose
Collect all market competition signals your research calls for so that:
- future logic (suppression ceilings, elasticity, roles) can be built without waiting for new history
- you can analyse behaviour over time
- you have a single daily metrics snapshot + history table
- you can generate per-SKU reports with graphs

This is **read-only data collection only** and **must not execute any pricing updates**.

---

## Phase 1 — Define Daily Competition & Market Signals

### Goal
Create a schema for the daily metrics snapshot that captures all market behaviour signals you need.

### Output files
- `out/hos_daily_market_snapshot_YYYY-MM-DD.csv`
- `out/hos_daily_market_history.csv` (append-only)

### Columns required (one row per SKU per day)

#### Keys
- `asof_date` (YYYY-MM-DD)
- `marketplace`
- `sku`
- `asin`

#### Buy Box behaviour
- `buy_box_price_raw_gross` (from latest snapshot)
- `buy_box_price_used_gross` (with fallback logic applied)
- `buy_box_channel` (FBA/FBM/Amazon)
- `buy_box_seller_id` (if available)
- `buy_box_missing_flag` (0/1, whether Buy Box was missing)
- `buy_box_fallback_used_flag` (0/1, fallback applied)

#### Competition price envelope
- `lowest_offer_price_gross`
- `lowest_fba_price_gross`
- `lowest_fbm_price_gross`
- `highest_offer_price_gross`
- `median_offer_price_gross` (optional)
- `price_spread_gross = highest_offer_price_gross − lowest_offer_price_gross`

#### Seller mix & roles
- `offer_count_total`
- `offer_count_fba`
- `offer_count_fbm`
- `amazon_present_flag` (0/1)
- `seller_entry_count_today` (new sellers added today)
- `seller_exit_count_today` (sellers that disappeared since yesterday)

#### Delivery & fulfilment
- `our_delivery_days`
- `buy_box_delivery_days`
- `delivery_parity_flag` (0/1)
- `prime_eligible_flag` (0/1)

#### Economics anchors (from Phase 2)
- `break_even_exvat_gbp`
- `break_even_gross_gbp`
- `token_cost_exvat_gbp`
- `min_price_gross_10pct` (10% ROI floor)
- `max_price_gross_current` (current suppression ceiling)

---

## Phase 1 — Fallback logic (must be explicit)

### Buy Box price used fallback order
1. `buy_box_price_raw_gross` from snapshot
2. last non-null `buy_box_price` from `listing_offer_history`
3. `lowest_fba_price_gross`
4. `our_price_gross`
5. blank + set `buy_box_missing_flag=1`

---

## Phase 2 — Build the Daily Metrics Snapshot

### When to run
After:
- offer collection completes (so pricing exists for today)
- seller-level snapshot exists (for seller mix)
- performance summary exists (for break-even & economics)

### Process
1. Load today’s `listing_offer_snapshot_YYYY-MM-DD.csv`
2. Load today’s seller offer info (seller-level snapshot/history)
3. Load yesterday’s competition to compute entry/exit counts
4. Load `sku_performance_summary.csv` for economics anchors
5. Apply fallback logic to determine `buy_box_price_used_gross`

### Output
Write `out/hos_daily_market_snapshot_YYYY-MM-DD.csv` with one row per SKU.

Then **append** those rows to `out/hos_daily_market_history.csv`.

---

## Phase 3 — Add Health Checks

Health checks must be added so you know the snapshot is valid:

- Snapshot file exists
- Exactly 10 rows (training SKUs)
- All required columns present
- No nulls for:
  - `buy_box_price_used_gross`
  - `offer_count_fba`
  - `offer_count_fbm`
- `delivery_parity_flag` (0/1 only)
- Economics anchors (no blanks for training SKUs)

Add these as part of the daily build’s post-run validation.

---

## Phase 4 — Generate Daily Reports (HTML + PDF + Charts)

### Output folder
