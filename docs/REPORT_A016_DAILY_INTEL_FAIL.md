# REPORT - A016 Daily Intel FAIL Root Cause

## Scope
- Checks investigated:
  - `a_daily_intel_coverage_non_parked`
  - `a_daily_intel_compliance_nonempty_non_parked`
- Constraints followed:
  - No code changes
  - Artifact and log analysis only

## 1) Exact definitions and thresholds (with code references)

### Check 1: `a_daily_intel_coverage_non_parked`
- A015 reads:
  - scope from `out/phase1_sku_scope.csv` via `PHASE1_SCOPE_PATH`  
    - `scripts/flows/A/A015_build_system_health_check.py:76`
  - daily intel from `data/sku_daily_intel.csv` via `PHASE1_DAILY_INTEL_PATH`  
    - `scripts/flows/A/A015_build_system_health_check.py:77`
  - parked reasons from `out/parking/parked_skus.csv` via `PARKED_SKUS_PATH`  
    - `scripts/flows/A/A015_build_system_health_check.py:79`
- Logic:
  - Build `non_parked_skus` from scope rows where `parked_flag != "1"`  
    - `scripts/flows/A/A015_build_system_health_check.py:1417`
  - Merge parked SKUs from parked-reason map and remove them from non-parked set  
    - `scripts/flows/A/A015_build_system_health_check.py:1421-1422`
  - Exclude dropped SKUs (`sale_status == dropped`) from required set  
    - `scripts/flows/A/A015_build_system_health_check.py:1424-1427`
  - Filter daily intel to `date_utc == today`, compute covered SKUs, missing SKUs  
    - `scripts/flows/A/A015_build_system_health_check.py:1448-1454`
  - Status rule:
    - `pass` if `missing_skus` is empty
    - `fail` if `missing_skus` count > 0 (value = `len(missing_skus)`)  
    - `scripts/flows/A/A015_build_system_health_check.py:1458-1464`

### Check 2: `a_daily_intel_compliance_nonempty_non_parked`
- Uses the same `required_daily_skus` set as Check 1  
  - `scripts/flows/A/A015_build_system_health_check.py:1427-1430`
- Required field: `compliance_ceiling_landed_gbp`
  - If missing column -> `fail` (`missing_column`)  
    - `scripts/flows/A/A015_build_system_health_check.py:1468-1474`
  - Else per required SKU:
    - no row for today -> `missing_row_count += 1`
    - row exists but compliance is blank -> `blank_compliance_count += 1`  
    - `scripts/flows/A/A015_build_system_health_check.py:1478-1487`
  - Status rule:
    - `pass` if `bad_total == 0`
    - `fail` if `bad_total > 0` where `bad_total = missing_row_count + blank_compliance_count`  
    - `scripts/flows/A/A015_build_system_health_check.py:1487-1496`

## 2) Exact non-parked SKU universe used

- Universe computation source code:
  - `scripts/flows/A/A015_build_system_health_check.py:1417-1427`
- For latest failing run date `2026-03-01`, required non-parked (after parked and dropped exclusions) is 51 SKUs:

`0G-JB6S-PN34, 0R-GRRH-W0Z9, 2G-AYBQ-TUQG, 3X-EXDD-TD2K, 4W-VS57-BV6A, 5Z-6Z0P-9TQQ, 6Q-9G2A-IKVV, 6V-EEC1-2S9Z, 714810, 8M-NHB7-T8TR, 8U-QPFH-3EKQ, 9X-HL62-83C7, A1-KSU1-GZMS, A2-T2AC-TW3L, AF-KIHX-ANYY, AX-NKNU-29C1, BL-WX51-KQOK, CJ-X0SS-QOUW, CX-SMCH-4DYA, D0-C7C0-H6LN, D8-1A3E-I37F, DC-K5WH-R7F5, FB-6FW0-Z82Q, H6-E7MP-EBPD, HL-03ZR-QPHH, HS-R5IP-7E1C, IJ-V0PQ-4CZ4, JB-RGB6-LZOJ, LP-QMNJ-J49G, LR-7GM6-1RCH, OV-LVEL-DQL6, R4-0AXZ-ZZ9D, R7-98IN-2PW8, RI-VSUS-0YTD, RZ-6ZL9-CZ7J, TJ-6LOP-OPEU, TK-E7QE-T40G, UR-Q7TM-1F3I, US-AK96-YFSB, VF-3T0K-DR5O, VO-A6AR-18YS, VU-8KRA-QP5M, W3-8FN7-FSP0, WE-1Z7L-SA2I, X7-MY4W-H2I4, XE-27ZG-EZPZ, XE-YPAI-HX9F, XH-0LAE-FQO5, YC-3L3M-BV48, YO-EKK2-FRCC, Z7-26PV-O9LR`

- This same required set is used by both checks above.

## 3) Latest failing global A015 run - counts and missing SKUs

- Failing rows from global artifacts:
  - `out/system_health_checklist.csv` row:
    - `a_daily_intel_coverage_non_parked,fail,50,date=2026-03-01; required=51; dropped=373; non_parked=54; covered=1; ...`
    - `a_daily_intel_compliance_nonempty_non_parked,fail,50,date=2026-03-01; required=51; dropped=373; non_parked=54; missing_rows=50; blank_compliance=0`
  - Also present in `out/cycle_alerts/checklist_A.csv` with same values and `cycle=A`.
- Latest failing global snapshot timestamp:
  - `out/system_health_checklist.csv` LastWriteTimeUtc = `2026-03-01T12:56:50Z`
- Computed counts for `date_utc=2026-03-01` from artifacts A015 reads:
  - required non-parked SKUs: `51`
  - covered by `data/sku_daily_intel.csv`: `1`
  - missing SKUs: `50`
- Missing SKU list (50, all shown; <=200 so no extra CSV needed):

`0G-JB6S-PN34, 0R-GRRH-W0Z9, 2G-AYBQ-TUQG, 3X-EXDD-TD2K, 4W-VS57-BV6A, 5Z-6Z0P-9TQQ, 6Q-9G2A-IKVV, 714810, 8M-NHB7-T8TR, 8U-QPFH-3EKQ, 9X-HL62-83C7, A1-KSU1-GZMS, A2-T2AC-TW3L, AF-KIHX-ANYY, AX-NKNU-29C1, BL-WX51-KQOK, CJ-X0SS-QOUW, CX-SMCH-4DYA, D0-C7C0-H6LN, D8-1A3E-I37F, DC-K5WH-R7F5, FB-6FW0-Z82Q, H6-E7MP-EBPD, HL-03ZR-QPHH, HS-R5IP-7E1C, IJ-V0PQ-4CZ4, JB-RGB6-LZOJ, LP-QMNJ-J49G, LR-7GM6-1RCH, OV-LVEL-DQL6, R4-0AXZ-ZZ9D, R7-98IN-2PW8, RI-VSUS-0YTD, RZ-6ZL9-CZ7J, TJ-6LOP-OPEU, TK-E7QE-T40G, UR-Q7TM-1F3I, US-AK96-YFSB, VF-3T0K-DR5O, VO-A6AR-18YS, VU-8KRA-QP5M, W3-8FN7-FSP0, WE-1Z7L-SA2I, X7-MY4W-H2I4, XE-27ZG-EZPZ, XE-YPAI-HX9F, XH-0LAE-FQO5, YC-3L3M-BV48, YO-EKK2-FRCC, Z7-26PV-O9LR`

## 4) compliance_nonempty details

- Required field list for this check:
  - `compliance_ceiling_landed_gbp` only  
  - `scripts/flows/A/A015_build_system_health_check.py:1468-1486`
- Missing/empty counts on required non-parked set (`date_utc=2026-03-01`):
  - missing row in `data/sku_daily_intel.csv`: `50`
  - present row but blank `compliance_ceiling_landed_gbp`: `0`
  - present row with non-empty `compliance_ceiling_landed_gbp`: `1`
- Example rows (10) showing failure mode (row absent => required compliance missing by absence):
  - `{"sku":"0G-JB6S-PN34","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"0R-GRRH-W0Z9","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"2G-AYBQ-TUQG","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"3X-EXDD-TD2K","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"4W-VS57-BV6A","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"5Z-6Z0P-9TQQ","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"6Q-9G2A-IKVV","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"714810","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"8M-NHB7-T8TR","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`
  - `{"sku":"8U-QPFH-3EKQ","date_utc":"2026-03-01","row_present_in_data_sku_daily_intel":"0","compliance_ceiling_landed_gbp":"<missing because row absent>"}`

## 5) Upstream cause category (one selected + justification)

- Selected category: **A016 filters exclude non-parked SKUs incorrectly**

### Why this category fits the evidence
- H alignment logs on `2026-03-01` show A016 running with single-SKU scope:
  - `phase1 daily_intel alignment status=ok target_mode=single_sku resolved_count=1 processed=1 missing_compliance=0`
  - log lines:
    - `out/systems/H/live/H_pricing_cycle.log:81728`
    - `out/systems/H/live/H_pricing_cycle.log:81796`
    - `out/systems/H/live/H_pricing_cycle.log:81893`
- The resulting daily artifact confirms exactly one SKU written for that date:
  - `data/sku_daily_intel.csv` has only one row for `date_utc=2026-03-01` (`sku=6V-EEC1-2S9Z`).
- A015 required set for that same date is 51 non-parked/non-dropped SKUs.
- Therefore A016 output is scoped to 1 SKU while A015 expects 51, producing:
  - coverage fail = 50 missing
  - compliance fail = 50 missing rows (blank compliance count is 0)

### Additional contributing runtime signal (secondary)
- Later in the same day, H also logged:
  - `phase1 daily_intel alignment status=skipped_disabled ...`
  - `out/systems/H/live/H_pricing_cycle.log:81596`
  - `out/systems/H/live/H_pricing_cycle.log:82259`
- This prevented broad refresh later in the run window, but the primary mismatch is already explained by single-SKU A016 alignment output.

## Exact artifact path(s) A015 reads for A016 intel
- `data/sku_daily_intel.csv` (`PHASE1_DAILY_INTEL_PATH`)  
  - `scripts/flows/A/A015_build_system_health_check.py:77`
- Supporting scope/parking inputs used to define required universe:
  - `out/phase1_sku_scope.csv` (`PHASE1_SCOPE_PATH`)  
    - `scripts/flows/A/A015_build_system_health_check.py:76`
  - `out/parking/parked_skus.csv` (`PARKED_SKUS_PATH`)  
    - `scripts/flows/A/A015_build_system_health_check.py:79`
