# Decision Brief

Date: 2026-04-23
Purpose: make the Phase 2 demand-range review usable without reading raw CSV data.

## Simple Decision Needed
- Should we stop products entering clean Pass when BBP demand is much higher than Amazon's visible demand signal?

Recommended answer:
- Yes, for the two strongest cases:
  - `amazon_blank_bbp_high`
  - `amazon_50_bbp_inflated`

## What The Data Says
- Sample pack rows: `131`
- Rows currently recommended to remove from clean Pass: `92`
- The two clear remove-from-clean-pass groups are:
  - `amazon_blank_bbp_high`: `82` sample rows
  - `amazon_50_bbp_inflated`: `10` sample rows

## Plain-English Rule Groups

### Group 1 - Amazon blank, BBP high
- Code: `amazon_blank_bbp_high`
- Count in sample pack: `82`
- Meaning:
  - Amazon shows no visible sold signal.
  - That means we should treat demand as `0-49`.
  - BBP is claiming more than 49 units.
- Why this causes noise:
  - BBP may be reading parent or wider variation demand.
  - The product can look like a clean Pass even though Amazon does not show enough demand.
- Recommended decision:
  - `hard_fail` or at minimum `remove_from_clean_pass`.
- Suggested system behavior:
  - Do not allow clean Pass.
  - Move to fail or manual-review lane with reason `amazon_blank_bbp_high`.

### Group 2 - Amazon 50+, BBP inflated
- Code: `amazon_50_bbp_inflated`
- Count in sample pack: `10`
- Meaning:
  - Amazon shows `50+ bought in past month`.
  - BBP is far above that.
- Why this causes noise:
  - BBP may be confusing the selected ASIN with parent or variation volume.
- Recommended decision:
  - `hard_fail` or `remove_from_clean_pass`.
- Suggested system behavior:
  - Do not allow clean Pass unless stronger UK-specific evidence exists.

### Group 3 - Amazon 50+, BBP warning range
- Code: `amazon_50_bbp_warn`
- Count in sample pack: `10`
- Meaning:
  - Amazon shows demand.
  - BBP is above the reasonable range but not extreme.
- Recommended decision:
  - `manual_review`.
- Suggested system behavior:
  - Keep out of clean Pass for now, but do not hard fail until thresholds are reviewed.

### Group 4 - Weak UK review confirms demand risk
- Code: `weak_uk_review_confirms_demand_risk`
- Count in sample pack: `10`
- Meaning:
  - UK review evidence is weak.
  - Demand estimate may be coming from parent, global, or non-UK variation evidence.
- Recommended decision:
  - Use as a confidence reducer.
  - Make it a hard fail only when combined with Group 1 or Group 2.
- Suggested system behavior:
  - Strengthen existing demand-risk action.

### Group 5 - Seller stock missing
- Code: `seller_stock_missing_for_demand_check`
- Count in sample pack: `10`
- Meaning:
  - Seller stock would help judge demand, but the system does not store it.
- Recommended decision:
  - `rescan_needed`, not fail.
- Suggested system behavior:
  - Do not invent stock data.
  - Add to targeted rescan requirements if stock count becomes an approved scanner field.

### Group 6 - Amazon 50+, BBP reasonable
- Code: `amazon_50_bbp_reasonable`
- Count in sample pack: `9`
- Meaning:
  - Amazon shows `50+`.
  - BBP is close to that range.
- Recommended decision:
  - `allow_if_other_checks_pass`.

## Recommended Approval For Phase 3
- Approve these as immediate triage outcomes:
  - `amazon_blank_bbp_high` -> `remove_from_clean_pass`
  - `amazon_50_bbp_inflated` -> `remove_from_clean_pass`
  - `amazon_50_bbp_warn` -> `manual_review`
  - `weak_uk_review_confirms_demand_risk` -> confidence reducer only
  - `seller_stock_missing_for_demand_check` -> `targeted_rescan_needed`
  - `amazon_50_bbp_reasonable` -> allowed if other checks pass

## B0C8C3JF9X
- Current classification:
  - `amazon_blank_bbp_high`
  - `weak_uk_review_confirms_demand_risk`
  - `seller_stock_missing_for_demand_check`
- Plain-English decision:
  - This should not have been a clean Pass.
- Recommended decision:
  - `hard_fail` or `remove_from_clean_pass`.

## User-Friendly Approval Sentence
Use this sentence if you agree:

`Approved: apply Phase 3 triage integration for demand range rules. Use amazon_blank_bbp_high and amazon_50_bbp_inflated as remove_from_clean_pass, amazon_50_bbp_warn as manual_review, weak_uk_review_confirms_demand_risk as a confidence reducer, seller_stock_missing_for_demand_check as targeted_rescan_needed, and keep amazon_50_bbp_reasonable allowed if other checks pass.`

## Not Approved Yet
- Upstream pass-gate enforcement is not approved by this brief.
- Full scraper rescan is not approved by this brief.
- Google Sheets changes are not approved by this brief.
- Local DB changes are not approved by this brief.

