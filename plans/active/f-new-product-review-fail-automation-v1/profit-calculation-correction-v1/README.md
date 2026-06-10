# Profit Calculation Correction V1

Ticket: `F New Product Review - fix inflated profit calculation`
Parent plan: `f-new-product-review-fail-automation-v1`
Date opened: 2026-04-23
Status: implemented with isolated proof and local rebuild artifacts

## Purpose
- Remove inflated profit logic that treats `break_even` as if it were product cost.
- Correct profit at the earliest safe owner stage in flow F.
- Prove impact with a read-only audit before and after correction.

## Scope
- Flow owner code only:
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `scripts/flows/F/F071_build_backtest_input_view.py`
- New one-off audit:
  - `scripts/one_off/F027_build_profit_formula_conflict_audit.py`
- Review/triage compatibility:
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - `scripts/one_off/F021_build_new_product_review_fail_triage.py`

## Guardrails
- No Google Sheets writes.
- No local DB alignment changes.
- No scraper run.
- No A script run.
- No full F061 rescan.
- No WORK_LOG update in this ticket.
