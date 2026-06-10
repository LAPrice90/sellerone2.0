# Plan

## Goal
- Final outcome:
  - replace the fragmented backtest-only planning path with one business-first sales history truth system
  - answer the real sourcing question in plain language:
    - if we buy this now, what monthly sales and profit should we expect at our economics
    - is the item seasonal, stable, drifting, or too new to trust
    - is the item underperforming or overperforming recently
    - should the system say `pass`, `fail`, or `manual_review`
  - keep the design open for later improvement by capturing buy-time assumptions and checking them against the next 90 days of reality

## Non-goals
- Do not do:
  - treat current partial month as trusted demand
  - use future predicted months in pass/fail logic
  - let old strong months rescue weak current economics
  - build a full optimizer before the demand truth model is stable
  - hand-edit past outputs to make results look right
  - rewrite H runtime, Sheets, or local DB behavior in this ticket

## Current state
- What exists already:
  - F071 to F074 and related one-off audits already exist
  - BBP sales chart extraction now captures completed/current/future separation from `estSalesMonthlyChart`
  - user sample review has already established a working commercial floor:
    - expected monthly profit below `GBP 20` should normally fail
  - sampled ASIN audit export exists and can be used as the operator check pack
- Known pain points:
  - scrape coverage is still incomplete and needs targeted recovery before full-estate confidence is representative
  - decision confidence is now explicit, but high-confidence coverage has not yet been benchmarked against operator truth
  - operator sold-30d checks are now formalized, but current sample still needs operator inputs completed
  - weekend evidence collection is now strong enough to move from scraping into model work:
    - `4580` scrape-evidence rows exist
    - `4556` unique ASINs have been seen
    - `2342` ASINs have a latest successful scrape record
    - latest successful captures already include:
      - `1918` ASINs with `6+` observed completed months
      - `1528` ASINs with `9+` observed completed months
      - `1012` ASINs with `12+` observed completed months
  - scrape coverage is still incomplete, but it is no longer the blocking task for decision-model work:
    - `2214` ASINs still have a latest non-success scrape state
    - fresh targeted recovery subset exists:
      - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
      - selected rows: `2207`
  - current plan history is split across:
    - old active backtest folder
    - reference idea docs
    - user review notes
  - post-purchase learning loop now exists, but outcome checkpoints are still mostly unfilled:
    - learning rows: `266`
    - pending outcomes: `266`
- Known alerts or reliability concerns:
  - refreshed `2026-04-20` rebuild shows:
    - `f_backtest_demand_basis_integrity = ok`
    - `f_backtest_price_qualified_demand_integrity = ok`
    - `f_backtest_qualification_source_alignment = ok`
    - `f_backtest_health_staleness = ok`
    - `f_backtest_decision_floor_integrity = ok`
    - `f_backtest_decision_confidence_integrity = ok`
    - `f_backtest_manual_review_share = ok` (`manual_review_share=0.088634`)
  - one-off sampled audit still reports `mismatch_rows=2` and remains visible for follow-up root-cause review

## Target state
- What changes:
  - one active plan folder defines the decision model, data contracts, runbook, and implementation order
  - trusted sales history uses completed months only
  - raw demand is split from price-qualified demand
  - history maturity is explicit:
    - no history
    - recent only
    - developing
    - stable
    - full-year seasonal read available
  - seasonality and stability are scored separately
  - recent performance is compared to both recent baseline and full-history context
  - monthly expected profit is calculated at our economics and compared to a configurable floor
  - post-purchase 90-day review is designed into the system rather than left as ad-hoc checking
- What stays the same:
  - existing F data capture and replay pipeline remains the implementation base unless a batch proves a cleaner owner path is needed
  - reference files under `reference/Backtest Strategy Ideas/` remain reference-only
  - one-off audit/export scripts remain one-off and outside daily loops

## Systems touched
- Flow(s):
  - F flow
  - later O flow only if/when decision outputs are surfaced to operators
- Shared dependencies:
  - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - sampled-ASIN audit outputs in `out/analysis_reports/`
- Runtime or scheduler ownership concerns:
  - none for plan cleanup itself
  - broad weekend scrape has now served its purpose and is intentionally stopped for this ticket
  - targeted replay remains a one-off recovery path and must not become a background default
  - future audit/validation work must stay one-off unless a later batch explicitly promotes it into a loop

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| BBP raw sales history evidence | `Webscrape.py` | output | `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` | existing truth source for completed/current/future monthly chart fields |
| Sales history feature view | `F071_build_backtest_input_view.py` | output | `out/systems/F/live/feeder_backtest_input_view_live.csv` | existing view to be extended with price-qualified demand features |
| Daily replay and share context | `F072_run_backtest_replay.py` | output | `out/systems/F/live/feeder_backtest_replay_daily_live.csv` | existing daily replay remains the share and path engine |
| Decision summary | `F073_build_backtest_summary.py` | output | `out/systems/F/live/feeder_backtest_summary_live.csv` | existing summary to be upgraded into buy-now sales-history decision output |
| F-scoped health | `F074_build_backtest_health.py` | output | `out/systems/F/live/feeder_backtest_health.csv` | existing health must prove demand basis, price qualification, and join truth |
| Validation audit | planned one-off owner in Batch 001 | output | `out/analysis_reports/f_sales_history_validation_latest.csv` | compare trusted completed month and decision output against sampled operator checks |
| Post-purchase learning log | `F012_build_sales_history_learning_pack.py` | output | `out/systems/F/live/feeder_sales_history_learning_live.csv` | buy-time assumption snapshot versus actual 90-day result |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `feeder_legacy_scrape_evidence_live.csv` | after any scrape logic change | when sample validation uses older schema/evidence | existing schema checks plus batch-specific sample audit | completed/current/future month fields are the trust root |
| `feeder_backtest_input_view_live.csv` | after any demand, pricing, or decision-rule change | when summary/health are older than input | `f_backtest_input_view_schema` plus new price-qualified-demand checks | existing file will carry new monthly-demand features |
| `feeder_backtest_replay_daily_live.csv` | after any share or path logic change | when summary uses stale replay | existing replay schema/coverage checks | replay still provides share and path behavior |
| `feeder_backtest_summary_live.csv` | after any decision logic change | when operator review relies on stale summary | existing summary checks plus new decision-state checks | summary becomes the main business output |
| `feeder_backtest_health.csv` | after any code change in owned path | if newer input/replay/summary files exist without rebuilt health | existing health rows plus new sales-history truth checks | stale health must be called stale, not treated as proof |
| `f_sales_history_validation_latest.csv` | after any demand or decision rule change | if operator sign-off relies on older validation sample | new validation accuracy checks from Batch 001 | one-off audit, not daily-loop output |
| `feeder_sales_history_learning_live.csv` | weekly or after new purchase events in learning scope | if a review depends on missing buy-time snapshots | one-off learning checks from Batch 007 | active one-off learning output |

## Integration points
- APIs:
  - none in this planning ticket
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - BBP chart evidence flows into F071
  - replay share/path evidence flows into F073
  - validation audit flows from summary plus sampled-ASIN source pack
  - learning log compares buy-time assumption snapshot with actual outcome evidence

## Risks and mitigations
- Risk:
  - a random spike gets misread as seasonality
  - Mitigation:
    - require history maturity thresholds before calling seasonality with confidence
    - keep `possible_seasonal` separate from `seasonal_confirmed`
- Risk:
  - new items with only a few months of history get unfairly rejected
  - Mitigation:
    - use maturity classes and lower-confidence forecasts instead of pretending new listings have full-year proof
- Risk:
  - sales are overstated because the chart saw demand that existed only below our floor
  - Mitigation:
    - split raw observed demand from price-qualified demand and only let the qualified figure drive pass/fail
- Risk:
  - the model becomes another backtest abstraction layer and loses contact with operator reality
  - Mitigation:
    - keep sampled-ASIN validation and Amazon sold-30-day checks in the proof path
- Risk:
  - the system never learns from real purchases
  - Mitigation:
    - make 90-day post-purchase review part of the planned model, not optional cleanup
- Risk:
  - stale health or join ambiguity hides structural issues
  - Mitigation:
    - Batch 001 must refresh health truth and explain the current input-view count mismatch before later scoring work is trusted

## Proof rules
- What counts as code fix applied:
  - the new active plan exists
  - the old active backtest plan is archived
  - later batches only claim code changes when owned F files or tests are actually edited
- What counts as isolated verification passed:
  - for this planning reset:
    - new plan folder exists with filled brief, plan, status, contracts, runbook, and first execution batch
    - old active plan exists under archive with a clear archive note
  - for later coding batches:
    - scoped pytest pack passes
    - required F rebuild or one-off audit completes
    - row counts and health are captured after the change
- What counts as live loop verification confirmed:
  - not applicable yet
  - no batch may claim live-loop success until a later scheduled owner path exists and is proven separately

## Batch list
- Batch 001:
  - ready
  - demand truth contract and audit baseline
  - lock raw vs price-qualified monthly demand, maturity states, `GBP 20` monthly profit floor handling, and fresh validation proof against sampled ASINs
- Batch 002:
  - ready
  - scrape coverage recovery and live validation
  - validate a handful of ASINs, recover completed-month BBP coverage on the current supplier list, and restore the normal overnight scan path on the correct supplier runner
- Batch 003:
  - complete (`2026-04-19`)
  - price-qualified monthly demand engine hardening
  - refine how completed-month observed demand becomes addressable monthly demand using stronger per-month price and share evidence
- Batch 004:
  - complete (`2026-04-20`)
  - seasonality, stability, and recent-performance classifier
  - detect full-year seasonality, possible seasonality, spikes, drift, and recent under/over performance using the frozen weekend dataset rather than waiting for more broad scrape coverage
- Batch 005:
  - complete (`2026-04-20`)
  - business decision summary and confidence engine
  - output `pass` / `fail` / `manual_review`, expected monthly units/profit now, confidence, and reason tags
- Batch 006:
  - complete (`2026-04-20`)
  - validation and accuracy pack
  - compare the model with Amazon sold-in-last-30-days checks and sampled operator reviews, then expose error buckets honestly
- Batch 007:
  - complete (`2026-04-20`)
  - post-purchase 90-day learning loop
  - record buy-time assumptions, compare them with actual outcome, and classify why the model was right or wrong

## Archive rule
- When this plan can move to archive:
  - after the sales-history decision model is implemented, validated, and either:
    - fully handed into a newer active plan
    - or proven stable enough that only routine tuning remains

## Active execution document
- Use `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md` as the durable phase-by-phase execution sequence.
- It must hold:
  - current phase
  - tests and isolated proof
  - monitored validation window
  - next automatic phase trigger
