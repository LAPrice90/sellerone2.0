# Decision Brief

Date: 2026-04-23
Purpose: make Issue 2 approval possible without reading raw CSV data.

## Simple Decision Needed
- Should clean Pass rows be removed when they already have strong history-risk evidence?

Recommended answer:
- Yes, for the strongest conflicts:
  - `history_fail_phase_avoid`
  - `backtest_avoid_commercial_avoid_or_exit`
  - `exit_only_clean_pass`

## What The Data Says
- Current clean Pass rows: `226`
- Rows with at least one direct history-risk conflict: `149`
- This is bigger than the demand issue that removed 40 rows from clean Pass.

## Plain-English Rule Groups

### Group 1 - History FAIL and phase AVOID
- Code: `history_fail_phase_avoid`
- Current count: `109`
- Meaning:
  - The review pack says Pass, but historical behavior says Fail and Avoid.
- Recommended decision:
  - `remove_from_clean_pass`.
- Suggested system behavior:
  - Route to a history-risk review lane or fail-style near-miss lane with explicit reason.

### Group 2 - Backtest Avoid plus commercial Avoid or Exit-only
- Code: `backtest_avoid_commercial_avoid_or_exit`
- Current count: `99`
- Meaning:
  - The product is being surfaced as clean Pass while the commercial summary already says Avoid or Exit-only.
- Recommended decision:
  - `remove_from_clean_pass`.
- Suggested system behavior:
  - Do not show as clean Pass until the contradiction is resolved upstream.

### Group 3 - Exit-only clean Pass
- Code: `exit_only_clean_pass`
- Current count: `38`
- Meaning:
  - The system is saying clean Pass even though the recommendation says this is only safe as an exit or sell-off strategy.
- Recommended decision:
  - `remove_from_clean_pass`.

### Group 4 - Heavy failure history
- Code: `failure_events_100_plus`
- Current count: `66`
- Meaning:
  - The product has at least 100 recorded failure events in the historical replay.
- Recommended decision:
  - `manual_review` unless it also matches Group 1, 2, or 3.

### Group 5 - Sell-off days exceed normal days
- Code: `selloff_days_exceed_normal_days`
- Current count: `58`
- Meaning:
  - Historical replay spends more time in sell-off state than normal selling state.
- Recommended decision:
  - `manual_review` unless it also matches Group 1, 2, or 3.

## Recommended Approval For Later Implementation
- Approve these initial routing outcomes:
  - `history_fail_phase_avoid` -> `remove_from_clean_pass`
  - `backtest_avoid_commercial_avoid_or_exit` -> `remove_from_clean_pass`
  - `exit_only_clean_pass` -> `remove_from_clean_pass`
  - `failure_events_100_plus` -> `manual_review`
  - `selloff_days_exceed_normal_days` -> `manual_review`

## Not Approved Yet
- Upstream enforcement is not approved by this brief.
- Full scraper rescan is not approved by this brief.
- Google Sheets changes are not approved by this brief.
- Local DB changes are not approved by this brief.

