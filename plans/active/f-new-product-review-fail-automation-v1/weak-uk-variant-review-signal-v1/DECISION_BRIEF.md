# Decision Brief

Date: 2026-04-23
Purpose: approve initial handling of weak UK review evidence without raw CSV review.

## Simple Decision Needed
- Should clean Pass rows be removed or reviewed when UK review evidence is weak?

Recommended answer:
- Yes.
- Use a stronger action for `0-2` UK reviews.
- Use manual review for `3-5` UK reviews.

## What The Data Says
- Current clean Pass rows: `79`
- Rows with fewer than 6 UK reviews: `32`
- Rows with fewer than 3 UK reviews: `22`

## Plain-English Rule Groups

### Group 1 - No or almost no UK review proof
- Code: `uk_reviews_lt3`
- Current count: `22`
- Meaning:
  - The selected ASIN has 0, 1, or 2 UK reviews.
  - Parent or variant review volume may be misleading for a UK-selling decision.
- Recommended decision:
  - `remove_from_clean_pass`.

### Group 2 - Weak UK review proof
- Code: `uk_reviews_3_to_5`
- Current count: `10`
- Meaning:
  - The ASIN has 3 to 5 UK reviews.
  - This is not enough confidence for clean Pass unless other evidence is very strong.
- Recommended decision:
  - `manual_review`.

### Group 3 - Low but usable UK review proof
- Code: `uk_reviews_6_to_9`
- Current count: `7`
- Meaning:
  - The ASIN has 6 to 9 UK reviews.
  - This is still weak, but not an automatic blocker by itself.
- Recommended decision:
  - `supporting_evidence_only`.

### Group 4 - Enough UK review proof
- Code: `uk_reviews_10_plus`
- Current count: `40`
- Meaning:
  - UK reviews are not the main concern.
- Recommended decision:
  - `allow_if_other_checks_pass`.

## Recommended Approval For Implementation
- Approve these initial routing outcomes:
  - `uk_reviews_lt3` -> `remove_from_clean_pass`
  - `uk_reviews_3_to_5` -> `manual_review`
  - `uk_reviews_6_to_9` -> supporting evidence only
  - `uk_reviews_10_plus` -> allowed if other checks pass

## Not Approved Yet
- Full scraper rescan is not approved by this brief.
- Seller stock capture is not approved by this brief.
- Google Sheets changes are not approved by this brief.
- Local DB changes are not approved by this brief.

