# Project Brief

## Ticket
- Ticket name: `H and F feedback-learning loop`
- Date opened: `2026-04-17`
- Owner: `Codex`

## Business problem
- What is hurting today?
  - H repricer is producing live decisions and health data, but it is still mostly an error-monitoring system instead of a business-learning system.
  - F new product finder has structured review packs, but it still leans heavily on scraped BBP demand signals and does not learn enough from real H market behavior or our actual sales.
  - We are collecting real market and sales facts already, but they are not being joined into one repeatable learning loop.
- What decision or process is blocked?
  - We cannot confidently improve repricer settings, compare tactics, or sharpen product vetting while the evidence is split across H logs, E/B sales outputs, and F backtest packs.

## Goal
- What should exist when this is done?
  - one joined evidence layer that explains:
    - what market state H saw
    - what H decided to do
    - what happened next
    - how that compares with F demand and profit estimates
  - operator outputs that show:
    - undercut pressure
    - sharing behavior
    - seller reaction lag
    - actual sales versus expected sales
    - which tactic families are working and which are not
  - a 30-day alignment process that compares live facts, BBP estimates, and our actual results
  - a shadow-mode calibration path that can improve F scoring without silently changing live buy decisions

## Why now
- Why is this worth doing now?
  - H now has enough runtime evidence to move beyond simple "is it broken" monitoring.
  - F already has calibration and validation packs, so there is a clean place to absorb learning once the joined evidence exists.
  - The user wants genuine feedback from real operations, not just more scraped estimates or one-off reviews.

## Constraints
- Existing system boundaries:
  - Root-cause first: new learning must be built from owner-stage facts, not downstream output massage.
  - No Google Sheets changes unless explicitly asked.
  - No local DB rewrites unless explicitly approved.
  - No ad-hoc `A` runs unless explicitly asked.
  - One-off builders must stay outside daily loops until promoted deliberately.
- Out of scope for this ticket:
  - immediate repricer policy retune without evidence
  - auto-changing live buy rules from learning outputs
  - sheet dashboard work
  - unrelated H stability or scheduler redesign
- Approval-sensitive areas:
  - any manual `A` run
  - any sheet write
  - any DB write
  - any promotion of one-off learning builders into daily loops

## Dependency notes
- H scoped checklist is newer than the aggregate global checklist and is the correct proof base for this ticket.
- Current H scoped alerts are warnings, not a scoped hard fail:
  - `h_strategy_expired_share_multi_seller_ladder_cap = 90.36`
  - `h_strategy_sample_size_single_rival_reset = 1`
- F live backtest owner outputs currently exist but are empty, so current F evidence for this ticket comes from the analysis packs, not from the empty live CSVs.

## Definition of success
- Observable result 1:
  - operator can open one report and see market state, H action, result, and actual sales alignment by SKU or tactic family
- Observable result 2:
  - repricer feedback includes undercut/share/reaction facts, not just health faults
- Observable result 3:
  - F receives shadow-mode calibration inputs from live H and actual sales evidence
- Observable result 4:
  - a monthly alignment output exists and can explain estimate vs reality gaps with concrete factors

## Reference material
- Research notes:
  - `plans/active/h-f-feedback-learning-loop-v1/RESEARCH_REPORT_2026-04-17.md`
- Related repo files:
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/flows/H/H004_build_daily_market_snapshot.py`
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `scripts/flows/F/F072_run_backtest_replay.py`
  - `scripts/flows/F/F073_build_backtest_summary.py`
  - `scripts/flows/F/F074_build_backtest_health.py`
