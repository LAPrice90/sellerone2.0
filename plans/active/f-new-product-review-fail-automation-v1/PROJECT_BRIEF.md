# Project Brief

## Ticket
- Ticket name: `f-new-product-review-fail-automation-v1`
- Date opened: `2026-04-23`
- Owner: Codex

## Business problem
- What is hurting today?
  - New Product Review has enough data to review, but fail handling is still too manual.
  - The current wave has very high fail volume and near-miss volume, so the user must repeatedly fail similar rows by hand.
- What decision or process is blocked?
  - We do not yet have one clear fail triage layer that separates:
    - data integrity or calculation issues
    - known policy fails we can auto-apply from stored evidence
    - unknown evidence gaps that need targeted rescan

## Goal
- What should exist when this is done?
  - A phase-owned fail automation path for New Product Review with 3 fail types:
    - Type 1: incorrect data pulled or miscalculation
    - Type 2: auto-fail from stored evidence we already have
    - Type 3: evidence missing, so queue targeted rescan only for relevant ASINs

## Why now
- Why is this worth doing now?
  - Current supplier-wave evidence is already large enough to justify automation:
    - pass review rows: `266`
    - near-miss review rows: `3056`
    - hard reject rows: `6665`
    - pending screening rows: `32869`
  - This is the right point to reduce manual review waste before the next commercial review rounds.

## Constraints
- Existing system boundaries:
  - Reuse the current F owner path and legacy scanner integration.
  - Keep one-off tools out of daily loops unless explicitly promoted.
  - No overlapping `F061` runs.
- Out of scope:
  - No new duplicate scraper path.
  - No Google Sheets writes.
  - No local DB alignment changes.
- Approval-sensitive areas:
  - Applying any queue rewrite (`--apply`) for targeted rescan.
  - Any change that alters release decisions beyond review-surface triage.

## Definition of success
- Observable result 1:
  - one fail triage output exists with explicit `fail_type` for each reviewed ASIN row.
- Observable result 2:
  - one auto-fail output exists that reduces repeated manual fail actions using stored evidence.
- Observable result 3:
  - one targeted rescan queue output exists for evidence-gap rows only, without restarting the full fail universe.

## Reference material
- Research notes:
  - live review summary and row-state fail distribution from `2026-04-23`
- Related repo files:
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
  - `scripts/one_off/F008_capture_full_bbp_evidence_pack.py`
  - `scripts/one_off/F018_build_live_price_file_launch_pack.py`
  - `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - `scripts/flows/F/_schemas.py`
- Prior tickets or plans:
  - `plans/active/f-feeder-commercial-test-launch-v1/*`
  - `plans/active/o-f-feeder-review-ui-v1/*`
  - `plans/active/h-f-feedback-learning-loop-v1/*`
