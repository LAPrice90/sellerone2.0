# H0 Backfill Guide v1 (BuyBotPro / Keepa)

Purpose:
- Bootstrap history for a small training set so you can set expectations faster.
- This is optional. It should not block starting F0.

Important:
- Only backfill for the training SKUs at first (5-10).
- Do not scrape websites or violate tool terms.
- Backfilled data must be tagged with source=BBP (or KEEPA).

---

## 1) What backfill is good for

- Typical buy box price range (last 30-90 days)
- Typical BSR range and trend direction
- Identify if the listing is naturally volatile or stable
- Spot seasonality or known dips/spikes

Backfill is NOT good for:
- Exact competitor strategy identification
- Guaranteed future demand
- Replacing your decision signals or current cost inputs

---

## 2) How to backfill (operator process)

**User Task**
For each ASIN in your training set:
1) Export price history and rank history from your tool (if supported).
2) Save as CSV in:
   - imports/bbp_history/<asin>_history.csv
3) Keep the raw export unchanged (do not edit it).

Then run an import script (future):
- H002_import_bbp_history.py
  - reads those exports
  - maps them into the standard H history schema
  - writes to out/listing_offer_history.csv with source=BBP

If you do not have an export:
- Skip backfill and start with daily snapshots only.

---

## 3) Required mapping into our schema

Minimum fields to map:
- timestamp_utc (or date)
- asin (required)
- marketplace (assume UK unless stated)
- buy_box_price (or closest equivalent)
- bsr (if included)
- source=BBP
- notes=BACKFILL

If the export contains only graphs and not numeric data:
- do not attempt OCR in the daily pipeline
- either obtain a numeric export or skip backfill

---

## 4) Backfill integrity rules

- Backfill must never overwrite real daily snapshots.
- Backfill rows must be clearly tagged:
  - source=BBP
  - notes include BACKFILL
- If the same timestamp exists from SPAPI and BBP:
  - prefer SPAPI

End.
