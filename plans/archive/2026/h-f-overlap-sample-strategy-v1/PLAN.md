# Plan

## Goal
- Final outcome:
  - turn the cleaned H/F evidence stack into an execution-ready optimisation program
  - expand H/F overlap through the current F capture owner path
  - grow tactic evidence into a scorecard that clearly separates mature tactics from thin-sample tactics
  - create a shadow-only strategy experiment queue before any future live H logic change

## Non-goals
- Do not do:
  - live repricer rule changes in this planning ticket
  - Google Sheets edits
  - local DB edits
  - a new scraper or duplicate scrape ownership path
  - downstream smoothing to hide missing overlap or missing baseline evidence
  - presenting thin-sample tactic results as strategy truth

## Current state
- What exists already:
  - Cleanup ticket `h-f-data-cleanup-2026-04-18` is signed off.
  - H runtime is live, owned, and safe on the current floor/ceiling integrity checks.
  - H/F learning health is clean:
    - `hf_fail=0`
    - `hf_warn=0`
    - `hf_scrape_gap_missing_rate=0.0636`
  - The joined H/F evidence layer already exists:
    - `hf_learning_action_outcomes_latest.csv` -> `12738` rows
    - `hf_learning_alignment_30d_latest.csv` -> `95` rows
    - `hf_learning_factor_impacts_latest.csv` -> `5` rows
- Known pain points:
  - H/F overlap is still effectively zero where it matters for resolved identity:
    - `identity_rows_with_asin=6979`
    - `identity_rows_asin_in_h_scope=0`
    - `identity_asin_h_scope_overlap_rate=0.0000`
  - Alignment still has a large no-source block:
    - `missing_expected_baseline=65`
    - `underperform_vs_expected=24`
    - `aligned=2`
  - H tactic evidence is still uneven:
    - `multi_seller_ladder_cap=87/150`
    - `single_rival_reset=5/30`
    - `suppression_reactivation=62/20`
  - Latest H daily tactic mix still shows weak maturity in the tactics we want to tune:
    - `multi_seller_ladder_cap`: `88` decisions, `29` failed, `55` expired
    - `single_rival_reset`: `5` decisions, still provisional
  - There is still no durable scorecard that tells the operator:
    - which tactics are sample-mature
    - which tactics are expiring without useful response
    - which SKUs are blocked by no-source baseline vs true underperformance
- Known alerts or reliability concerns:
  - H scoped checklist still shows `0 FAIL / 2 WARN` on sample-size maturity.
  - H remains `Needs Stabilising` on the roadmap, so any future runtime phase stays proof-gated.
  - The global aggregate checklist is stale context for H and must not be used as current proof for this plan.

## Target state
- What changes:
  - a new overlap expansion pack identifies exactly which F items should be routed into existing capture paths
  - a tactic scorecard measures:
    - eligible-to-write to decision-to-change to attempted to applied chain
    - expiry and fail mix
    - seller-count pressure
    - 30-day realised units and profit where available
    - sample maturity status
  - a monthly strategy review pack explains:
    - what is working
    - what is failing due to thin sample
    - what is failing due to missing baseline
    - what deserves shadow experimentation next
  - a shadow experiment queue exists before any H runtime strategy phase starts
- What stays the same:
  - H remains the owner of live price writes.
  - F remains the owner of screening and scrape-routing contracts.
  - No sheet or DB ownership changes are introduced.
  - No live H tactic change is promoted without explicit proof and a later ticket.

## Systems touched
- Flow(s):
  - H primary
  - F primary
  - E and B read-only for realised sales and economics truth
- Shared dependencies:
  - `out/h_pricing_cycle_state.json`
  - `out/h_strategy_outcome_daily.csv`
  - `out/analysis_reports/hf_learning_foundation_metrics_latest.csv`
  - `out/analysis_reports/hf_learning_action_outcomes_latest.csv`
  - `out/analysis_reports/hf_learning_alignment_30d_latest.csv`
  - `out/analysis_reports/hf_learning_factor_impacts_latest.csv`
  - `out/reports/hf_learning_operator_report_latest.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`
- Runtime or scheduler ownership concerns:
  - No ad-hoc A run unless the user explicitly requests it.
  - No overlapping manual B work.
  - No new scrape owner path; reuse `F007`, `F061`, and `F008` only.
  - Any later H runtime phase must use controlled restart-drain plus forced proof planning.

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Scope expansion candidates | planned `scripts/one_off/HF010_build_scope_expansion_candidates.py` | output | `out/analysis_reports/hf_scope_expansion_candidates_latest.csv` | candidate-level route pack for ASIN-bearing rows missing H scope |
| Scope expansion summary | planned `scripts/one_off/HF010_build_scope_expansion_candidates.py` | output | `out/analysis_reports/hf_scope_expansion_summary_latest.csv` | top-line overlap and route-bucket counts |
| Strategy scorecard | planned `scripts/one_off/HF011_build_strategy_scorecard.py` | output | `out/analysis_reports/hf_strategy_scorecard_latest.csv` | tactic-level maturity, outcome, and economics scorecard |
| Strategy review pack | planned `scripts/one_off/HF012_build_strategy_review_pack.py` | output | `out/reports/hf_strategy_review_pack_latest.csv` | operator pack for tactics, SKUs, and blockers |
| Shadow experiment queue | planned `scripts/one_off/HF013_build_strategy_experiment_queue.py` | output | `out/analysis_reports/hf_strategy_experiment_queue_latest.csv` | shadow-only next-action queue for future H tests |
| Current overlap foundation | `scripts/one_off/HF000_build_learning_foundation.py` | input | `out/analysis_reports/hf_learning_foundation_metrics_latest.csv` | current overlap and unresolved bucket truth |
| Current alignment pack | `scripts/one_off/HF002_build_learning_alignment.py` | input | `out/analysis_reports/hf_learning_alignment_30d_latest.csv` | expected vs actual anchor for review pack |
| Existing calibration shadow output | `scripts/flows/F/F080_build_feedback_calibration_shadow.py` | input/output | `out/systems/F/live/feeder_feedback_calibration_live.csv` | optional downstream shadow consumer only |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `hf_scope_expansion_candidates_latest.csv` | after any new foundation or alignment rebuild | if execution relies on an older pack than the latest foundation/alignment truth | explicit route buckets, unique key, and overlap-count checks | overlap phase first |
| `hf_strategy_scorecard_latest.csv` | 1 day | 7 days or older than current H strategy outputs used by downstream review | tactic schema, nonzero rows, and maturity-flag checks | no live changes from thin sample |
| `hf_strategy_review_pack_latest.csv` | 1 day | 7 days or older than scorecard/alignment inputs | summary/source timestamp checks | report is never the only truth |
| `hf_strategy_experiment_queue_latest.csv` | after each scorecard rebuild | if any shadow consumer is newer than the queue | shadow-only flags, cohort cap, and risk-gate checks | no auto-live application |

## Integration points
- APIs:
  - none new
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - overlap routing must reuse:
    - `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
    - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
    - `scripts/one_off/F008_capture_full_bbp_evidence_pack.py`
  - strategy review pack may feed shadow-only fields into:
    - `out/systems/F/live/feeder_feedback_calibration_live.csv`
  - any later H experiment phase must read from the new queue, not a manual spreadsheet or chat note

## Risks and mitigations
- Risk:
  - we treat no-source baseline rows as strategy failure
  - Mitigation:
    - keep overlap recovery, no-source review, and tactic outcome scoring as separate outputs
- Risk:
  - we optimise on thin-sample tactics
  - Mitigation:
    - no tactic enters the experiment queue unless it passes explicit sample-maturity gates or is marked as pilot-safe by rule
- Risk:
  - a second scrape owner path gets introduced accidentally
  - Mitigation:
    - reuse the current F routing path only and make owner-path columns explicit in every overlap output
- Risk:
  - H runtime changes arrive before the scorecard and queue are trustworthy
  - Mitigation:
    - put runtime work in the last phase only, behind controlled restart-drain and forced proof rules
- Risk:
  - stale aggregate health files are mistaken for current H proof
  - Mitigation:
    - use H scoped checklist, H runtime state, and latest owned artifacts only

## Proof rules
- What counts as code fix applied:
  - for this planning ticket:
    - new plan pack written
    - research report written
    - cleanup task sign-off recorded
  - for later execution:
    - only owned scripts, tests, and plan docs are changed inside the phase scope
- What counts as isolated verification passed:
  - targeted `py_compile` and pytest pack pass
  - one-off builders rerun deterministically against the same inputs
  - row counts and key buckets reconcile across repeat runs
- What counts as live loop verification confirmed:
  - only relevant for a later H runtime phase
  - requires:
    - forced proof window planned
    - H owner drained through the approved path if code changed
    - isolated tests passed first
    - post-change H terminal marker shows finalized success
    - scheduler ownership restored and fresh owner process observed

## Batch list
- Batch 001:
  - overlap expansion and routing pack
- Batch 002:
  - tactic scorecard and sample-maturity builder
- Batch 003:
  - strategy review pack and operator outputs
- Batch 004:
  - shadow experiment queue and optional F shadow handoff
- Batch 005:
  - H runtime cohort hooks only if earlier phases justify a controlled runtime ticket

## Archive rule
- When this plan can move to archive:
  - overlap pack exists and makes the zero-overlap problem actionable
  - tactic scorecard exists with maturity gates and health checks
  - strategy review pack exists and can explain missing baseline vs true underperformance
  - experiment queue exists in shadow-only mode
  - any H runtime follow-up is either:
    - proven in a later ticket, or
    - explicitly deferred with reasons and thresholds
