# H0 Listing Offer History Spec v1 (Daily Snapshot + History)

Purpose:
- Store daily (or periodic) listing context so decisions are history-aware.
- This is NOT an orders/financials dataset. It is market context.

---

## 1) What H captures

At minimum, for each SKU/ASIN:
- timestamp_utc
- marketplace
- sku
- asin
- our_price
- buy_box_price
- buy_box_channel (FBA/FBM/Amazon/Unknown) if available
- lowest_fba_price (if available)
- lowest_fbm_price (if available)
- offer_count_fba (if available)
- offer_count_fbm (if available)
- bsr (if available)
- bsr_category (if available)
- source (SPAPI / BBP / MANUAL_TOOL)

Optional but useful:
- is_buy_box_ours (true/false/unknown)
- is_prime_ours (true/false/unknown)
- fulfilment_disadvantage_flag (example: hazmat next-day mismatch)
- notes

---

## 2) Files

Required files:
- out/listing_offer_snapshot_YYYY-MM-DD.csv
  - Overwritable daily snapshot (latest run for the day).

- out/listing_offer_history.csv
  - Append-only (or idempotent upsert by unique key)
  - Keep all history.

Optional:
- out/listing_offer_history.parquet (if you later want performance)
- out/listing_offer_history.db (SQLite) if you prefer a DB

---

## 3) Schema (CSV)

Required columns:
- timestamp_utc
- marketplace
- sku
- asin
- our_price
- buy_box_price
- buy_box_channel
- lowest_fba_price
- lowest_fbm_price
- offer_count_fba
- offer_count_fbm
- bsr
- bsr_category
- source
- notes

All numeric fields should be parseable as numbers or blank.

---

## 4) Idempotency rules

H must be safe to rerun.

Recommended approach:
- Always write a full snapshot file for the run.
- When appending to history:
  - Use (timestamp_utc, sku, marketplace) as the unique key.
  - If a row already exists for that key, replace it (upsert).
  - Otherwise insert.

If you cannot do upsert easily in CSV:
- Keep history append-only and accept duplicates
- But then your analysis must dedupe by (timestamp_utc, sku, marketplace)

---

## 5) How E and F will use history later

History enables:
- Typical buy box range (min/median/max over last N days)
- Price volatility score (thrash detection)
- Buy box stability score
- Estimated competitor aggressiveness (how often buy box price changes)
- Detect "special situations" like fulfilment disadvantage requiring larger discount (your hazmat example)

Important:
- History does not replace velocity or projected ROI checks. It adds context.

---

## 6) Data source options

Preferred (cleanest):
- Amazon SP-API pricing/competitive endpoints (your own account access)
- Store only aggregated info (prices, offer counts, channels)
- Avoid scraping websites.

Optional:
- BuyBotPro exports (if available)
- Keepa exports (if you have access and it is permitted)
- Manual exports from tools are emergency one-off only and must never run in daily loops.
- Manual exports require explicit approval before use.

All backfilled data must set source=BBP (or source=KEEPA) so it is distinguishable.

End.
