# Evidence Baseline

Date: 2026-04-23
Source artifacts:
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/inbox/feeder_review_events.csv`

## Current Counts
- Pass review rows: `266`
- Scrape evidence rows: `4397`
- Backtest summary rows: `2358`
- Review event rows: `1`

## Demand Note Distribution In Pass Rows
- `amazon_missing_bbp_under_50`: `219`
- `amazon_missing_bbp_capped_to_50`: `42`
- `bbp_above_amazon_cap`: `2`
- `bbp_within_amazon_band`: `2`
- `bbp_below_amazon_floor`: `1`

## First Issue Count
- Rule candidate: Amazon sold signal blank, `demand_confidence_note=amazon_missing_bbp_capped_to_50`, and `expected_units_next_30d > 50`.
- Affected pass rows: `17`

## Threshold Counts
- `expected_units_next_30d > 50`: `17`
- `expected_units_next_30d > 100`: `16`
- `expected_units_next_30d > 250`: `10`
- `expected_units_next_30d > 500`: `6`

## Highest Priority Examples
| ASIN | Supplier SKU | Expected units | BBP units | Demand note |
|---|---:|---:|---:|---|
| `B0B3VNQ94T` | `1274784` | `955` | `955` | `amazon_missing_bbp_capped_to_50` |
| `B0CDBW1JWY` | `1274544` | `953` | `953` | `amazon_missing_bbp_capped_to_50` |
| `B0B3VP5Q9D` | `1214910` | `937` | `937` | `amazon_missing_bbp_capped_to_50` |
| `B07MKPML4M` | `1187148` | `860.8` | `1076` | `amazon_missing_bbp_capped_to_50` |
| `B0C8C3JF9X` | `1236917` | `813.6` | `1017` | `amazon_missing_bbp_capped_to_50` |
| `B000L10VPW` | `1270645` | `745` | `745` | `amazon_missing_bbp_capped_to_50` |

## B0C8C3JF9X Evidence
- Amazon sold signal: blank in stored `monthly_sold`.
- Demand confidence note: `amazon_missing_bbp_capped_to_50`.
- Expected units next 30 days: `813.6`.
- BBP replay demand basis units: `1017`.
- User review decision: `fail`.
- Review memory event: `o-ui-f-review-bfc06f252e51`.

## Data Sufficiency
- Enough stored data exists to audit and flag Amazon blank plus BBP high demand.
- Seller stock count is not stored, so seller-stock based rules require future evidence capture.
- Review detail fields need next scoped F061 proof before parent/variant detail can be relied on in the current live CSV.

