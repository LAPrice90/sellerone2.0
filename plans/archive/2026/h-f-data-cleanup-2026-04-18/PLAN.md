# Plan

## Goal
- Final outcome:
  - make the H and H/F data layer truthful, fresh, and easy to judge
  - clear the current warning state where that is realistically fixable today
  - separate "safe but messy" data from real blocking data defects
  - leave a clean operator view that shows what still needs more sample or more coverage

## Non-goals
- Do not do:
  - Google Sheets changes
  - local DB rewrites
  - ad-hoc A runs without explicit user approval
  - overlapping manual B runs
  - strategy tuning based on dirty measurement
  - silent downstream smoothing to make outputs look clean

## Today snapshot
- Evidence time window used for this plan:
  - `out/cycle_alerts/checklist_H.csv` at `2026-04-18T05:06:22Z`
  - `out/h_strategy_outcome_daily.csv` at `2026-04-18T07:02:35Z`
  - latest H ceiling-event run id: `20260418T065507Z`
  - H live lock heartbeat: `2026-04-18T07:02:25Z`
  - B live lock heartbeat: `2026-04-18T07:02:25Z`
- Clean areas:
  - A scoped health: `0 FAIL`, `0 WARN`
  - B scoped health: `0 FAIL`, `0 WARN`
  - E scoped health: `0 FAIL`, `0 WARN`
  - H live runtime currently has `0` rows where effective ceiling is below floor in:
    - `out/phase1_runtime_floor_snapshot_latest.csv`
    - latest run slice from `out/h_ceiling_events.csv`
- Dirty areas that still need work:
  - H sample-size status is directionally true but the checklist counts are stale:
    - checklist still shows `multi_seller_ladder_cap = 51` and `single_rival_reset = 1`
    - fresh H outcome data shows:
      - `multi_seller_ladder_cap = 67 / 150`
      - `single_rival_reset = 5 / 30`
  - H ceiling data is safe but still messy:
    - latest ceiling-event run has `32` rows
    - `8` rows have `ceiling_conflict_flag = 1`
    - `17` rows carry `CEILING_RULE_INPUTS_MISSING`
    - latest floor snapshot has `89` rows and `25` rows with `CEILING_RULE_INPUTS_MISSING`
  - H/F learning data is still the main cleanup problem:
    - `identity_resolution_rate = 0.0000`
    - `hf_scrape_gap_missing_rate = 0.9484` (`warn`)
    - `hf_alignment_expected_coverage = 0.3158` (`ok`)
  - F shared scrape owner files are live, so the biggest remaining issue is not "no scraper output":
    - `feeder_legacy_scrape_evidence_live.csv` -> `4261` rows
    - `feeder_legacy_chart_daily_raw_live.csv` -> `831298` rows

## Root-cause view
- H warning problem:
  - root cause is not a broken H decision counter
  - root cause is a freshness boundary problem between H live strategy outputs and the last A-built checklist snapshot
- H ceiling mess:
  - root cause is mostly incomplete ceiling-rule inputs, not unsafe floor protection
  - the clamp is working, but the raw evidence still carries too many conflict and missing-input rows
- H/F learning gap:
  - root cause is identity bridging and scope matching
  - live scrape evidence now exists, but the bridge still resolves `0` rows, so most of the learning stack cannot connect F expectations to H reality

## Target state for today
- H strategy status can be read without stale-count confusion
- H latest live slice remains safe:
  - `effective ceiling below floor = 0`
  - no impossible daily rollup rows
- H conflict and missing-input rows are either reduced or clearly classified
- H/F learning outputs rebuild from either:
  - a nonzero identity bridge, or
  - explicit no-overlap proof where ASIN-bearing rows are truthfully out of current H scope
- `hf_scrape_gap_missing_rate` drops below the current warning threshold if the bridge fix exposes existing evidence
- operator report can explain:
  - what is healthy
  - what is still sample-thin
  - what is coverage-thin
  - what still needs new evidence rather than code changes

## Systems touched
- Flow(s):
  - H primary
  - F primary for learning outputs
  - A scoped health only where freshness or checklist wording needs repair
- Shared dependencies:
  - `out/h_strategy_outcome_daily.csv`
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/analysis_reports/hf_learning_identity_bridge_latest.csv`
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
  - `out/analysis_reports/hf_learning_health_checklist_latest.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`
- Runtime or scheduler ownership concerns:
  - no ad-hoc A run unless explicitly requested
  - no overlapping manual B run
  - if H runtime code is touched later, use the controlled restart-drain path before edits

## Phases
- Phase 1 - Freshness boundary cleanup
  - confirm the exact owner boundary between H live outputs and A health outputs
  - add or repair freshness truth so stale H checklist counts cannot be mistaken for current live H counts
  - decide whether the right fix is:
    - H-owned live sample-status output
    - A-owned stale-data warning
    - or both
  - proof:
    - the latest H status output shows the same `asof_date` or a clear stale marker
    - checklist wording no longer implies a current live count when it is older than H data

- Phase 2 - H ceiling and rollup cleanup
  - inspect the `ceiling_conflict_flag` and `CEILING_RULE_INPUTS_MISSING` rows from the latest H slice
  - split them into:
    - acceptable clamped rows
    - actionable input defects
    - measurement-only noise
  - keep the current safety floor intact
  - proof:
    - `effective ceiling below floor = 0`
    - `at_floor_rows <= decision_rows` on all daily rows
    - conflict and missing-input reasons are explicitly bucketed

- Phase 3 - H/F identity bridge repair
  - trace why `identity_resolution_rate = 0.0000` despite live scraper evidence existing
  - repair the earliest join stage, not the downstream report
  - rebuild foundation outputs after the bridge fix
  - proof:
    - one of:
      - `identity_rows_resolved > 0`
      - explicit no-overlap proof path:
        - `identity_rows_with_asin > 0`
        - `identity_rows_asin_in_h_scope = 0`
        - `identity_rows_asin_not_in_h_scope = identity_rows_with_asin`
        - `identity_asin_h_scope_overlap_rate = 0.0000`
    - unresolved rows are split into concrete named buckets
    - rebuilt foundation outputs are deterministic across repeat runs

- Phase 4 - Scrape-gap rebuild and rescoring
  - rebuild baseline, alignment, health, and operator outputs from the repaired bridge
  - measure whether the missing-rate warning was mostly a bridge problem or a real scrape-coverage problem
  - only produce a rescrape ask if the remaining gap is genuinely scraper-owned
  - proof:
    - `hf_scrape_gap_missing_rate <= 0.80` to clear the current warning
    - or explicit proof that the remaining gap is upstream identity scope, not missing scraper data

- Phase 5 - Sign-off pack
  - update the active plan status and evidence summary
  - list what is clean, what is still thin-sample, and what needs more live time rather than more coding
  - proof:
    - pass/fail result written against the criteria below

## Pass criteria
- Required for "data clean enough to sign off today":
  - H live runtime remains safe with `0` effective ceiling-below-floor rows
  - H sample-size status is no longer presented through stale counts without a stale marker
  - H daily outcome rollups have `0` impossible rows
  - H/F identity bridge either:
    - resolves at least some rows, or
    - proves a no-overlap state explicitly while naming unresolved remainder truthfully
  - `hf_scrape_gap_missing_rate` is either:
    - reduced to `<= 0.80`, or
    - proven to be dominated by explicit non-scraper identity-scope gaps
- Not required for this ticket:
  - strategy optimisation perfection
  - clearing sample-size warnings by magically creating more live decisions
  - PO handoff population

## What success should look like in plain English
- After this work, we should be able to say:
  - H is safe right now
  - these tactics are still sample-thin
  - these rows are messy because ceiling inputs are missing
  - this part of the H/F learning gap is fixed in code
  - this remaining part needs more matching data or more live evidence
