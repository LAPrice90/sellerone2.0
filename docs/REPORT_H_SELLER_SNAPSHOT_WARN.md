# REPORT - H Seller Snapshot WARNs

Run under review: `20260301T144150Z`

WARN keys:
- `h_seller_snapshot_landed_non_null_training`
- `h_seller_snapshot_landed_ge_listing`
- `h_seller_snapshot_shipping_non_negative`

## 1) Exact A015 definitions/rules (with code refs)

A015 logic location:
- [`scripts/flows/A/A015_build_system_health_check.py:3695`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3695)
- [`scripts/flows/A/A015_build_system_health_check.py:3728`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3728)

Rules:
- If seller snapshot is empty:
  - all 3 checks are `warn` with `value=0` and note `snapshot empty`
  - refs: [`:3729-3732`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3729)
- If no training rows are present after filtering:
  - all 3 checks are `warn` with `value=0` and note `no training rows in snapshot`
  - refs: [`:3744-3747`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3744)
- Otherwise:
  - `h_seller_snapshot_landed_non_null_training`:
    - fail count = rows where `offer_price_gbp` is numeric and `offer_landed_price_gbp` is null
    - status `ok` if count is 0 else `fail`
    - refs: [`:3753-3761`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3753)
  - `h_seller_snapshot_landed_ge_listing`:
    - fail count = rows where both prices are numeric and `offer_landed_price_gbp + 1e-9 < offer_price_gbp`
    - status `ok` if count is 0 else `fail`
    - refs: [`:3763-3771`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3763)
  - `h_seller_snapshot_shipping_non_negative`:
    - fail count = rows where shipping is numeric and `< 0`
    - status `ok` if count is 0 else `fail`
    - refs: [`:3773-3781`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:3773)

## 2) Artifacts and columns A015 reads

Artifact selection:
- Seller snapshot file = latest by mtime from `out/listing_offer_seller_snapshot_*.csv`
- ref: [`scripts/flows/A/A015_build_system_health_check.py:747`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:747)

Artifacts used:
- Seller snapshot glob:
  - `out/listing_offer_seller_snapshot_*.csv`
  - ref: [`scripts/flows/A/A015_build_system_health_check.py:57`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:57)
- Training set:
  - `config/f_training_set.csv`
  - ref: [`scripts/flows/A/A015_build_system_health_check.py:43`](c:/Users/Luke/Desktop/SellerOne%202.0/scripts/flows/A/A015_build_system_health_check.py:43)

Columns used by these 3 checks:
- From seller snapshot:
  - `sku`
  - `offer_price_gbp`
  - `offer_shipping_price_gbp`
  - `offer_landed_price_gbp`
- From training set:
  - `sku`
  - optional `enabled` filter (`1/true/yes/y`)

## 3) Evidence for run_id `20260301T144150Z`

### 3.1 Relevant file path(s)
- A015-selected seller snapshot:
  - `out/listing_offer_seller_snapshot_2026-03-01.csv`
  - mtime UTC: `2026-03-01T14:37:43.452750683+00:00`
  - rows: `0` (header-only)
- Previous non-empty seller snapshot (for context):
  - `out/listing_offer_seller_snapshot_2026-02-28.csv`
  - rows: `161`

### 3.2 Row counts and failing counts
- Training set enabled rows: `12`
- Training rows considered from selected snapshot: `0`
- `h_seller_snapshot_landed_non_null_training` failing rows: `0` (WARN came from `snapshot empty` branch)
- `h_seller_snapshot_landed_ge_listing` failing rows: `0` (WARN came from `snapshot empty` branch)
- `h_seller_snapshot_shipping_non_negative` failing rows: `0` (WARN came from `snapshot empty` branch)

Checklist rows (exact):
- `"h_seller_snapshot_landed_non_null_training","warn","0","snapshot empty",...`
- `"h_seller_snapshot_landed_ge_listing","warn","0","snapshot empty",...`
- `"h_seller_snapshot_shipping_non_negative","warn","0","snapshot empty",...`

### 3.3 Example failing rows (10 requested each rule)

No failing rows exist because A015 did not enter numeric comparison branches for this run; it exited early at `snapshot empty`.

- `h_seller_snapshot_landed_non_null_training`: none
- `h_seller_snapshot_landed_ge_listing`: none
- `h_seller_snapshot_shipping_non_negative`: none

No example rows can be produced with `SKU/listing/landed/shipping/training` because the selected snapshot has zero data rows.

### 3.4 Run log evidence

For run `20260301T144150Z`, log shows early launcher completion while stage was still at item_offers transition (no `phase1 snapshot_refresh done` line for this run block):
- [`out/systems/H/live/phase1_pilot_task.log:120066`](c:/Users/Luke/Desktop/SellerOne%202.0/out/systems/H/live/phase1_pilot_task.log:120066) `cycle_start run_id=20260301T144150Z ...`
- [`out/systems/H/live/phase1_pilot_task.log:120073`](c:/Users/Luke/Desktop/SellerOne%202.0/out/systems/H/live/phase1_pilot_task.log:120073) `snapshot_refresh still_working stage=item_offers ...`
- [`out/systems/H/live/phase1_pilot_task.log:120075`](c:/Users/Luke/Desktop/SellerOne%202.0/out/systems/H/live/phase1_pilot_task.log:120075) `child exit raw_rc=0`

## 4) Root cause classification

Chosen category: `wrong file (stale snapshot) being evaluated`

Justification:
- A015 always uses latest seller snapshot by mtime (`_latest_snapshot`).
- Latest file for this window is `out/listing_offer_seller_snapshot_2026-03-01.csv`, but it is header-only (`0` rows), so checks become WARN by design (`snapshot empty`).
- The file mtime (`14:37:43Z`) predates the analyzed run (`20260301T144150Z` starts at ~`14:41:50Z`), so this run did not produce a newer usable seller snapshot for A015 evaluation.
- Therefore the WARNs are not from numeric data violations; they are from A015 evaluating an empty/stale seller snapshot artifact.
