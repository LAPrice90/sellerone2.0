# Evidence Baseline

Timestamp UTC: `2026-04-23T15:52:55Z`

## Baseline Row Check
- ASIN: `B0B7298QN6`
- Candidate: `70215661ab3af8a951a00b3c517bb404f4d6648b`
- Supplier SKU: `1204860`

From `out/systems/F/live/feeder_legacy_first_checks_live.csv`:
- `cost=10.01`
- `fba_fee=2.07`
- `referral_fee=3.61`
- `digital_fee=0.11`
- `est_shipping=0.02`
- `vat=20`
- `api_live_price=24.09`
- `bbp_live_sell_price=24.89`
- `bbp_30d_avg_price=24.28`
- `break_even=17.36`

From `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`:
- `avg_30_day_price=24.28`
- `profit_per_unit_30d=6.92`
- `estimated_monthly_profit=138.40`
- Current inflation pattern appears as `24.28 - 17.36 = 6.92`.

From `out/analysis_reports/f_live_price_file_pass_review_latest.csv`:
- `expected_units_next_30d=40`
- `profit_per_unit_30d_gbp=6.92`
- `expected_profit_next_30d_gbp=210.6`
- `estimated_monthly_profit_gbp=138.4`

## Baseline Interpretation
- Stored per-unit profit currently follows break-even subtraction.
- Fee-based net profit is expected to be materially lower for this row.
- Full impact count pending `F027` audit output.
