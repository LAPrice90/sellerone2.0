# User Alignment Notes

## Purpose
- Record the agreed plain-English judgment from guided sample reviews.
- Keep this focused on patterns and expectation alignment, not on reviewing every ASIN.

## Review buckets
- `certain_fail`
- `almost_pass`
- `just_passed`
- `on_the_line`
- `manual_review_or_unclear`
- `demand_or_profit_inflation_risk`
- `amazon_or_compression_edge_case`

## Agreed outcome labels
- `rightful_fail`
- `rightful_pass`
- `too_harsh`
- `too_soft`
- `unclear_due_to_data`

## Decision capture template

| Reviewed UTC | Scenario bucket | seller_sku | asin | Current result | User expectation | Agreed outcome | Plain-English reason |
|---|---|---|---|---|---|---|---|

## Pattern summary
- Add one short note each time a pattern becomes clear enough that we do not need more similar ASINs.

## Working rule
- Review representative cases only.
- If a pattern repeats clearly, stop opening more rows from that same pattern and record the expectation instead.
- Working commercial floor for this review pass:
  - minimum expected monthly profit = `GBP 20`
  - if estimated monthly profit is below that floor, the row should normally fail even if price sits above break-even

## Reviewed rows

| Reviewed UTC | Scenario bucket | seller_sku | asin | Current result | User expectation | Agreed outcome | Plain-English reason |
|---|---|---|---|---|---|---|---|
| 2026-04-13T13:00:00Z | `manual_review_or_unclear` | `1014543` | `B01MR725H2` | `Manual review` | fail on low turnover and low profit | `too_soft` | Estimated demand looks about 1 sale per month and about GBP 3.61 monthly profit, so this should fail rather than sit in manual review. |
| 2026-04-13T13:05:00Z | `certain_fail` | `1014338` | `B01N5OORGV` | `Avoid` | hard fail because Amazon sits below break-even and still owns Buy Box | `rightful_fail` | Amazon sits well below break-even, only recent FBA sits above break-even, and Amazon still owns the Buy Box on used, so this remains a hard fail. |
| 2026-04-13T13:10:00Z | `manual_review_or_unclear` | `1090790` | `B07BHGT42W` | `Manual review` | hard fail because Amazon and most FBA pricing sit below break-even and profit is too weak | `too_soft` | Despite decent sales history, market price is below break-even, Amazon sits below break-even, most FBA pricing is below break-even, and the row should fail instead of waiting for manual review. |

## Pattern summary notes
- Weak-confidence rows should not hide low-demand commercial failure. If the row still points to about 1 sale per month and materially below GBP 20 monthly profit, user expectation is fail, not manual review.
- Hard fail remains correct when Amazon sits below break-even and still controls Buy Box, even if some recent FBA pricing appears above break-even.
- Weak Buy Box coverage and legacy attribution should not force manual review when the broader commercial picture already shows break-even failure against Amazon/FBA pricing.
