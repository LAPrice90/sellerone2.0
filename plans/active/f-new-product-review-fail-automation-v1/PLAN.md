# Plan

## Goal
- Final outcome:
  - add a fail triage layer for New Product Review that classifies every reviewed row into 3 fail types
  - auto-fail repeatable known issues from stored evidence so the user does not re-fail the same pattern manually
  - route missing-evidence cases into targeted rescan batches for relevant ASINs only

## Non-goals
- Do not do:
  - do not start a new scraper stack outside current F owner tools
  - do not rescan the full thousands-row fail universe for each issue type
  - do not mask downstream outputs to look clean if upstream data is wrong
  - do not change Sheets or local DB alignment

## Current state
- What exists already:
  - active review packs are live:
    - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
    - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
  - current summary snapshot (`2026-04-23T09:38:25Z`):
    - `pass_review_rows=266`
    - `near_miss_review_rows=3056`
    - `near_miss_evidence_gap_rows=2153`
    - `near_miss_commercial_rows=903`
    - `hard_reject_rows=6665`
  - screening row-state distribution:
    - `pending=32869`
    - `timeout+OVER50K=3423`
    - `timeout+ROIFAIL=2207`
    - `timeout+SCRAPEFAIL=1856`
    - `timeout+NOASIN=1149`
    - `timeout+FAIL=784`
    - `timeout+RESCAN=170`
    - `timeout+NODATE=127`
    - `timeout+HAZMATFAIL=5`
  - targeted rescan routing already exists:
    - `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
    - latest reason counts in subset:
      - `missing_core_price_history=2225`
      - `scrape_not_successful=2220`
      - `missing_bbp_demand_basis=2198`
- Known pain points:
  - fail data is present but not normalized into one operator-facing fail taxonomy
  - repeat manual fail decisions are not yet fed back as durable auto-fail logic
  - targeted rescan exists but is not yet driven by New Product Review fail-type outputs
- Known alerts or reliability concerns:
  - near-miss evidence-gap volume is high, so manual review load is high
  - feeder review event contract exists, but no persisted file is present yet in live output

## Target state
- What changes:
  - one fail audit output maps reviewed rows to:
    - `type_1_data_or_calc`
    - `type_2_known_policy_or_memory`
    - `type_3_missing_evidence_rescan_needed`
  - one auto-fail output lists rows that can be failed without manual repeat action
  - one rescan queue output is generated from Type 3 rows only, with explicit batching guidance
  - one day-vs-evening operating guide is applied:
    - workday for easy deterministic fixes
    - evening for bounded rescan batches
- What stays the same:
  - `F061` remains scraper owner
  - `F007` remains targeted queue preparation owner
  - `F008` remains sampled deep-evidence owner

## Systems touched
- Flow(s):
  - F flow primary
  - O review UI read path for feeder review events
- Shared dependencies:
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
  - `out/systems/F/inbox/feeder_review_events.csv`
- Runtime or scheduler ownership concerns:
  - no overlapping `F061` runs
  - targeted queue rewrites only through explicit `--apply` action

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Screening row state | `F061_run_legacy_first_checks_local.py` | input | `out/systems/F/live/f_screening_row_state_live.csv` | primary fail truth |
| Scrape evidence | `F061_run_legacy_first_checks_local.py` | input | `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` | detailed scrape and demand basis fields |
| Pass review pack | `F019_build_live_price_file_near_miss_pack.py` | input | `out/analysis_reports/f_live_price_file_pass_review_latest.csv` | pass lane |
| Near-miss review pack | `F019_build_live_price_file_near_miss_pack.py` | input | `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv` | near-miss lane |
| Review decision memory | `O400_operator_ui.py` append path | input | `out/systems/F/inbox/feeder_review_events.csv` | stored pass or fail decisions |
| Targeted rescan subset | `F007_prepare_targeted_rescrape_subset.py` | input/output | `out/analysis_reports/f_targeted_rescrape_subset_latest.csv` | existing batch queue output |
| Planned fail triage pack | new one-off in this ticket | output | `out/analysis_reports/f_new_product_review_fail_triage_latest.csv` | row-level fail type classification |
| Planned auto-fail pack | new one-off in this ticket | output | `out/analysis_reports/f_new_product_review_auto_fail_latest.csv` | rows to fail without manual repeat |
| Planned rescan planner pack | new one-off in this ticket | output | `out/analysis_reports/f_new_product_review_rescan_plan_latest.csv` | pass-only or near-miss-only rescan routing |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `f_screening_row_state_live.csv` | older than current active run evidence | missing active supplier rows | fail-code integrity and status distribution | primary fail source |
| `feeder_legacy_scrape_evidence_live.csv` | stale versus row-state latest update | missing scrape rows for active supplier | demand-basis and price-history completeness | drives Type 1 and Type 3 |
| `f_live_price_file_near_miss_review_latest.csv` | older than launch baseline | missing near-miss file | near-miss coverage by fail code | review lane source |
| `feeder_review_events.csv` | file missing after UI usage | schema mismatch or unreadable append history | review memory availability | drives Type 2 memory fails |
| `f_targeted_rescrape_subset_latest.csv` | older than latest Type 3 classification | missing after trigger | reason coverage and selection status | controls bounded rescans |

## Integration points
- APIs:
  - none new, reuse current SP-API and legacy scrape path through `F061`
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - fail triage outputs into review workflows and rescan planning

## Risks and mitigations
- Risk:
  - Type 2 auto-fail could over-block if stale evidence is treated as current
  - Mitigation:
    - require evidence-age and active-run checks before applying auto-fail
- Risk:
  - Type 3 can still grow too large if reasons are not batched
  - Mitigation:
    - cap by batch size and run in evening windows by default
- Risk:
  - manual decision memory may be sparse at first
  - Mitigation:
    - fallback to deterministic fail families and backtest evidence until decision logs mature

## Proof rules
- What counts as code fix applied:
  - new one-off scripts and tests exist for fail triage, auto-fail, and rescan planning
- What counts as isolated verification passed:
  - tests pass and outputs are created with expected columns and reconciled counts
- What counts as live loop verification confirmed:
  - if queue apply is used, bounded `F061` run confirms targeted rows move through screening without full-wave restart

## Batch list
- Batch 001:
  - build baseline fail audit and lock the 3-type taxonomy with real row counts
- Batch 002A:
  - count submitted noise-cut rules across pass-review rows before broad automation
- Batch 002:
  - implement Type 1 data or calculation fail rules from existing artifacts only
- Batch 003:
  - implement Type 2 stored-evidence auto-fail logic and confidence guardrails
- Batch 004:
  - implement Type 3 targeted rescan planner and connect to existing `F007` path
- Batch 005:
  - apply day-vs-evening operating mode and capture first bounded proof run

## Archive rule
- When this plan can move to archive:
  - after the 3 fail types are live, verified on current supplier-wave data, and the first targeted rescan cycle is proven without full-wave restart
