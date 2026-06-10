# Runbook

## Purpose
- What this plan or system does:
  - classify New Product Review rows into 3 fail types
  - auto-fail repeatable known issues from stored evidence
  - route missing-evidence cases into bounded targeted rescans

## Standard run order
```powershell
# 1) Read active planning documents
Get-Content plans\active\f-new-product-review-fail-automation-v1\PROJECT_BRIEF.md
Get-Content plans\active\f-new-product-review-fail-automation-v1\PLAN.md
Get-Content plans\active\f-new-product-review-fail-automation-v1\CODING_PLAN.md
Get-Content plans\active\f-new-product-review-fail-automation-v1\PLAN_STATUS.md

# 2) Read current source artifacts
Get-Content out\analysis_reports\f_live_price_file_review_summary_latest.csv -TotalCount 40
Get-Content out\analysis_reports\f_live_price_file_pass_review_latest.csv -TotalCount 5
Get-Content out\analysis_reports\f_live_price_file_near_miss_review_latest.csv -TotalCount 5
Get-Content out\systems\F\live\f_screening_row_state_live.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_legacy_first_checks_live.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_legacy_scrape_evidence_live.csv -TotalCount 5
Get-Content out\systems\F\live\feeder_backtest_summary_live.csv -TotalCount 5

# 3) Build fail triage pack (Phase 1)
python scripts\one_off\F020_build_new_product_review_fail_triage_pack.py

# 4) Build auto-fail pack (Phase 2)
python scripts\one_off\F021_build_new_product_review_auto_fail_pack.py

# 5) Build rescan plan pack (Phase 3)
python scripts\one_off\F022_build_new_product_review_rescan_plan.py

# 6) Optional dry-run queue planning only (no apply)
python scripts\one_off\F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --max-rows 25

# 7) Dashboard YES/NO rescan plan for old scraped review-pack rows
python scripts\one_off\F028_build_dashboard_yes_no_rescan_plan.py
```

## Day and evening mode
- Workday mode:
  - run Phase 1 and Phase 2 builders
  - review Type 1 and Type 2 outputs
  - do not apply queue rewrites
- Evening mode:
  - run Phase 3 planner output review
  - run bounded `F007` subset prep
  - if approved, run bounded `F061` data-collection rescan

## Validation steps
- Step 1:
  - confirm source files are present and readable
- Step 2:
  - run only current phase scripts and tests
- Step 3:
  - reconcile output row counts to source categories
- Step 4:
  - if a rescan is needed, use `F007` plus `F061` only
- Step 5:
  - if live proof can clash with an active owner, run `python scripts/one_off/P002_plan_forced_proof_window.py --flow f` first and follow the safe boundary

## Expected outputs
- Output:
  - `f_new_product_review_fail_triage_latest.csv`
- Path:
  - `out/analysis_reports/f_new_product_review_fail_triage_latest.csv`
- What good looks like:
  - each row has one fail type and explicit reason

- Output:
  - `f_new_product_review_auto_fail_latest.csv`
- Path:
  - `out/analysis_reports/f_new_product_review_auto_fail_latest.csv`
- What good looks like:
  - repeatable fails are auto-flagged with evidence source and timestamp

- Output:
  - `f_new_product_review_rescan_plan_latest.csv`
- Path:
  - `out/analysis_reports/f_new_product_review_rescan_plan_latest.csv`
- What good looks like:
  - only evidence-gap rows are queued for rescan with bounded batch guidance

- Output:
  - `f_dashboard_yes_no_rescan_plan_latest.csv`
- Path:
  - `out/analysis_reports/f_dashboard_yes_no_rescan_plan_latest.csv`
- What good looks like:
  - clean Pass rows with missing dashboard YES/NO are selected now
  - near-miss rows are counted but deferred unless explicitly included
  - every selected-now row has a queue match source

## Health checks
- Check:
  - fail-type classification coverage
- Pass condition:
  - all timeout and near-miss rows are classified into one of the 3 types
- Warning condition:
  - some rows are unclassified with explicit reason
- Fail condition:
  - unclassified rows are silent or counts do not reconcile

- Check:
  - auto-fail safety
- Pass condition:
  - every auto-fail row has stored evidence and reason
- Warning condition:
  - memory evidence sparse, fallback mode active
- Fail condition:
  - auto-fail applied without evidence source

- Check:
  - targeted rescan scope
- Pass condition:
  - rescan plan rows are bounded and traceable to Type 3 only
- Warning condition:
  - rescan plan larger than configured batch cap
- Fail condition:
  - rescan plan includes rows outside Type 3 scope

- Check:
  - dashboard YES/NO rescan scope
- Pass condition:
  - selected-now rows are clean Pass rows only and all selected rows have queue match evidence
- Warning condition:
  - near-miss rows are deferred because they are not current clean Pass blockers
- Fail condition:
  - selected-now rows include broad old scrape rows or rows with no ASIN/queue match

## Failure recovery
- If input is stale:
  - rebuild launch baseline and review packs first
- If output is missing:
  - stop and verify required source contracts before rerunning
- If tests fail:
  - fix the earliest failing rule first
- If runtime ownership is unclear:
  - do not run `F061` until owner state is confirmed
- If proof would clash with a live loop:
  - do not wait vaguely for the next cycle
  - use the forced proof planner and record the exact boundary required

## Archive note
- What to preserve when this plan is finished:
  - final fail-type rules
  - auto-fail reason taxonomy
  - targeted rescan batching policy and proof counts
