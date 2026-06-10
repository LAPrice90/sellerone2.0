# FROZEN INPUT MANIFEST

Status: Phase 0 complete

Freeze timestamp (Europe/London): 2026-04-17T22:43:51+01:00

Freeze timestamp (UTC): 2026-04-17T21:43:51Z

Required fields:

- absolute path
- modified time (UTC)
- file size bytes
- SHA256 hash

## Frozen Inputs

1. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\order_ledger_fx.csv`
mtime_utc: `2026-04-17T05:03:51Z`
size_bytes: `3208088`
sha256: `40CE371DE168C7E15F3DB3491123093C57B287F6BA020E5EAAF14566C8CE3348`

2. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\order_master.csv`
mtime_utc: `2026-04-17T21:41:13Z`
size_bytes: `1871285`
sha256: `2C5F8B534908A3B71A22ECC985ED20DA14B23182CAA08D70DE73D98E28390253`

3. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\fx_rates_daily.csv`
mtime_utc: `2026-04-17T05:03:47Z`
size_bytes: `44411`
sha256: `7CE2F78D958DD7AA8F2100D1EC04AD6F55FAA3E75789C1205CDA24D5ECC57F71`

4. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\sku_sales_velocity.csv`
mtime_utc: `2026-04-17T05:01:29Z`
size_bytes: `29975`
sha256: `E428E9CD8CA8CD949DF6E2370357327F43C4F86B919B51638D99964A5A8AC83A`

5. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\sku_roi_snapshot.csv`
mtime_utc: `2026-04-17T21:21:45Z`
size_bytes: `4033`
sha256: `AAC4886CFAB420132B57862FE0711F408A34CF516D0AFDF7B6A1479CA36D6401`

6. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\sku_performance_summary.csv`
mtime_utc: `2026-04-17T21:21:55Z`
size_bytes: `24648`
sha256: `E0AD321F3170B4FDAC8F9DF1653E9EF51C51FB6EB9A82F4B2FFF83B3C16AB4C8`

7. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\sales_truth_sku_30d_latest.csv`
mtime_utc: `2026-04-17T21:21:59Z`
size_bytes: `3536`
sha256: `EE631ACC925E2F6205A01BC14BBA2B687F24AF3D42ED4E0D5A9C11A32A273B43`

8. path: `C:\Users\Luke\Desktop\SellerOne 2.0\out\sales_truth_reconciliation_latest.csv`
mtime_utc: `2026-04-17T21:21:59Z`
size_bytes: `7188`
sha256: `B20E4B11229596BF955898E2BB68FB309D67879820FB4E432B04B4D45820642D`

## Baseline Anchors At Freeze

1. `sales_truth_reconciliation_latest.csv` mismatch rows: `0`
2. `sku_performance_summary.csv` unit mismatch still present:
- units_sold_total=`1913`
- units_sold_roi_total=`1871`
3. `A2-T2AC-TW3L` 30d reconciliation row:
- units_b_source=`354`
- units_e_output=`354.0`
- revenue_b_source_gbp=`3267.95`
- revenue_e_output_gbp=`3267.95`
- profit_b_source_gbp=`290.77999999999986`
- profit_e_output_gbp=`290.78`
- confidence_status=`match`

Execution rule:

If any frozen input above changes before final proof is complete, the proof window is broken and must restart from Phase 0.
