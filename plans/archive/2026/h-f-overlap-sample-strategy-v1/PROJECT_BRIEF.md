# Project Brief

## Ticket
- Ticket name:
  - `H/F overlap, sample growth, and strategy optimisation v1`
- Date opened:
  - `2026-04-18`
- Owner:
  - `Codex`

## Business problem
- What is hurting today?
  - The cleanup ticket proved H safety and H/F health, but the optimisation layer is still blocked by missing overlap and thin tactic samples.
  - Current evidence says `65/95` alignment rows still have `expected_units_source=no_source`, and `6979/6979` ASIN-bearing identity rows are outside current H scope.
- What decision or process is blocked?
  - We cannot justify live repricer strategy changes yet because we still lack:
    - recovered H/F overlap for affected ASINs
    - a tactic scorecard that separates thin-sample tactics from mature tactics
    - a shadow experiment queue with explicit gates before any H runtime change

## Goal
- What should exist when this is done?
  - A research-backed execution plan that:
    - expands H/F overlap through the existing F capture path
    - scores H tactics on sample maturity and outcome quality
    - produces operator review packs for what is working and what is not
    - gates any future live H strategy change behind shadow evidence and forced runtime proof

## Why now
- Why is this worth doing now?
  - The cleanup ticket is sign-off ready, so the next work should use the cleaned evidence instead of reopening integrity issues.
  - H is live and safe enough for planning, but still sample-thin in the tactics we care about most:
    - `multi_seller_ladder_cap = 87/150`
    - `single_rival_reset = 5/30`

## Constraints
- Existing system boundaries:
  - H owns live repricer writes.
  - F owns supplier screening and scrape-routing paths.
  - E and B remain read-only evidence sources here.
- Out of scope:
  - Google Sheets changes
  - local DB rewrites
  - a new scraper path
  - auto-tuning live repricer rules
- Approval-sensitive areas:
  - Any H runtime change must use controlled restart-drain and forced proof windows.
  - No ad-hoc A run unless the user explicitly asks.

## Definition of success
- Observable result 1:
  - A new active plan pack exists with researched phases, concrete outputs, and explicit proof thresholds.
- Observable result 2:
  - The next execution batch is clear enough to start without re-researching overlap, sample, or runtime boundaries.
- Observable result 3:
  - The closed cleanup ticket is signed off in both plan docs and `WORK_LOG.md`.

## Reference material
- Research notes:
  - `plans/archive/2026/h-f-data-cleanup-2026-04-18/SIGNOFF_2026-04-18.md`
  - `plans/active/h-f-feedback-learning-loop-v1/RESEARCH_REPORT_2026-04-17.md`
  - `plans/archive/2026/h-f-overlap-sample-strategy-v1/RESEARCH_REPORT_2026-04-18.md`
- Related repo files:
  - `out/h_pricing_cycle_state.json`
  - `out/h_strategy_outcome_daily.csv`
  - `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
  - `out/analysis_reports/hf_learning_action_outcomes_latest.csv`
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
  - `out/reports/hf_learning_operator_report_latest.csv`
- Prior tickets or plans:
  - `plans/archive/2026/h-f-data-cleanup-2026-04-18`
  - `plans/active/h-f-feedback-learning-loop-v1`
