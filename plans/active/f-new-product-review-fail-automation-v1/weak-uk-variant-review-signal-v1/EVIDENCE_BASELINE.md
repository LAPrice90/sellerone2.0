# Evidence Baseline

Date: 2026-04-23
Source artifacts:
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`

## Pre-Proof Baseline Counts
- Clean Pass rows after demand and history routing: `79`
- Near-miss rows after demand and history routing: `3243`

## Pre-Proof UK Review Distribution In Clean Pass
| Bucket | Count |
|---|---:|
| `uk_lt3` | `22` |
| `uk_3_to_5` | `10` |
| `uk_6_to_9` | `7` |
| `uk_10_plus` | `40` |

## Pre-Proof Issue 3 Count
- Rule candidate: clean Pass row has weak UK review evidence.
- `historical_uk_reviews < 6`: `32`
- `historical_uk_reviews < 3`: `22`

## Post-Proof Counts (after F019 rebuild)
- Clean Pass rows after demand and history routing: `47`
- Near-miss rows after demand and history routing: `3275`

## Post-Proof UK Review Distribution In Clean Pass
| Bucket | Count |
|---|---:|
| `uk_reviews_lt3` | `0` |
| `uk_reviews_3_to_5` | `0` |
| `uk_reviews_6_to_9` | `7` |
| `uk_reviews_10_plus` | `40` |
| `uk_reviews_missing` | `0` |

## Post-Proof UK Routing Counts
- `uk_review_routed_remove_from_clean_pass_rows`: `22`
- `uk_review_routed_manual_review_rows`: `10`
- `uk_review_routed_targeted_rescan_needed_rows`: `0`

## Priority Examples
| ASIN | Supplier SKU | UK reviews | Variant reviews | Expected units | Expected profit |
|---|---:|---:|---:|---:|---:|
| `B0BZK5M9TD` | `1311425` | `0` | `6867` | `0.8` | `44.248` |
| `B09QT7B4WW` | `1309918` | `0` | `647` | `4` | `33.12` |
| `B07DJZB398` | `1279621` | `0` | `506` | `6` | `26.79` |
| `B08GQV69PT` | `1226599` | `0` | `515` | `4` | `26.28` |
| `B07XG3TLVW` | `1279804` | `0` | `1431` | `2` | `19.38` |

## B0C8C3JF9X Context
- `B0C8C3JF9X` is already routed out by demand and history rules.
- Its current triage still carries weak UK review supporting evidence:
  - `weak_uk_review_confirms_demand_risk`
- Original user evidence:
  - parent/global reviews were high
  - selected variant and UK reviews were weak

## Data Sufficiency
- Enough stored data exists for a first UK-review audit using `historical_uk_reviews` and `variant_reviews`.
- Current live evidence may not yet include propagated parent review detail fields for all rows.
- If parent/variant/global distinction is required beyond existing fields, stop and request a scoped evidence run instead of inventing data.
