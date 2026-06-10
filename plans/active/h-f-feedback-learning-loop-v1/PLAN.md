# Plan

## Goal
- Final outcome:
  - turn H and F into a closed-loop learning system instead of two mostly separate decision systems
  - absorb real repricer evidence into product-finding and product-vetting logic
  - create operator outputs that explain what is working, what is not, and why
  - add a monthly alignment process that compares expected demand and profit with real outcomes

## Non-goals
- Do not do:
  - silently auto-tune live pricing rules from learning outputs
  - write to Google Sheets
  - rewrite the local DB
  - add one-off builders into daily loops before proof exists
  - hide H warnings or F evidence gaps by downstream smoothing

## Current state
- What exists already:
  - H already writes rich event, daily, listing, seller, history, and market-snapshot outputs.
  - F already has replay, summary, calibration, and validation design.
  - F already reads at least one H-owned source: `out/listing_offer_snapshot_latest.csv`.
  - H already has operator-friendly scenario buckets and response windows in code.
  - F already has a live scrape owner path:
    - `scripts/flows/F/F061_run_legacy_first_checks_local.py` owns screening plus scrape writes
    - current scrape contracts already exist:
      - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
      - `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`
  - F already has one-off scrape support tools:
    - targeted rescrape subset preparation in `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
    - sampled full BBP capture in `scripts/one_off/F008_capture_full_bbp_evidence_pack.py`
  - F already has lineage files strong enough to support a better starting foundation:
    - `out/systems/F/live/f_screening_row_state_live.csv` -> `42784` rows
    - `out/systems/F/live/feeder_approval_queue_live.csv` -> `9552` rows
    - `out/systems/F/history/feeder_approval_decisions_log.csv` -> `9552` rows
- Known pain points:
  - H feedback is fragmented across many files and is not surfaced as one business report.
  - H has very little persistent seller-delta learning so far.
  - F learns from backtest logic and scrape audits, but not enough from live H outcomes or actual post-buy sales.
  - F live owner CSVs are currently empty, so current usable truth is sitting in analysis packs instead of the live backtest path.
  - `out/systems/F/live/feeder_po_handoff_ready_live.csv` is currently `0` rows, so buy-time learning cannot rely on PO handoff alone yet.
  - There is no shared mart linking:
    - market context
    - H action
    - post-action result
    - actual sales/profit
    - F estimate at decision time
- Known alerts or reliability concerns:
  - newer H-scoped checklist (`out/cycle_alerts/checklist_H.csv`) is the authoritative H proof source for this ticket and currently shows warning-only status:
    - `h_strategy_expired_share_multi_seller_ladder_cap = warn`
    - `h_strategy_sample_size_single_rival_reset = warn`
  - aggregate global checklist (`out/system_health_checklist.csv`) still carries an older contradictory H fail and must be treated as stale aggregate context for this ticket, not as fresh scoped proof
  - F live backtest owner files are empty as of `2026-04-14T15:19:33Z`

## Target state
- What changes:
  - one joined learning layer explains:
    - which candidate, supplier row, ASIN, and SKU are the same commercial item
    - what F believed at approval or handoff time
    - what market H saw
    - what H chose
    - whether a write was attempted
    - whether a write applied
    - what happened next
    - how actual sales/profit compared with expected sales/profit
  - frozen assumption snapshots exist so we never compare actual outcomes against a later rewritten estimate
  - outcome windows are fixed before analysis:
    - H tactic windows: `15m`, `2h`, `24h`, `72h`
    - F product windows: `30d`, `60d`, `90d`
  - operator feedback exists for:
    - undercut frequency
    - share behavior
    - seller reaction lag
    - tactic performance by competitor shape
    - estimate-vs-reality drift
  - a 30-day alignment pack exists and can be rerun without manual archaeology
  - scrape refresh logic is explicit:
    - no new duplicate scraper is introduced
    - the learning task reuses current F scrape owner outputs
    - rescrape is triggered through the existing F owner path when coverage or freshness thresholds fail
  - F receives shadow-mode calibration factors from live H and actual sales evidence
  - later H tactic work can use measured evidence instead of intuition alone
- What stays the same:
  - H remains the owner of live repricer writes
  - F remains the owner of sourcing/backtest decisions
  - no sheet writes are added
  - no DB ownership changes are added

## Systems touched
- Flow(s):
  - H primary
  - F primary
  - E and B as read-only evidence sources for actual sales/profit truth
  - A health only for scoped checks once new outputs exist
- Shared dependencies:
  - `out/listing_offer_snapshot_latest.csv`
  - `out/listing_offer_seller_snapshot_latest.csv`
  - `out/listing_offer_history.csv`
  - `out/listing_offer_seller_observation_history.csv`
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/hos_daily_market_snapshot_latest.csv`
  - `out/sku_performance_summary.csv`
  - `out/sku_sales_velocity.csv`
  - current F analysis packs under `out/analysis_reports/`
- Runtime or scheduler ownership concerns:
  - Batch 001 through Batch 004 should be one-off/read-only builders first
  - no daily-loop promotion until outputs, contracts, and health checks are proven

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Identity bridge | planned one-off in Batch 000 | output | `out/analysis_reports/hf_learning_identity_bridge_latest.csv` | ties `candidate_id`, `supplier_sku`, `asin`, and `sku` into one explicit bridge |
| Frozen assumption snapshots | planned one-off in Batch 000 | output | `out/analysis_reports/hf_learning_assumption_snapshots_latest.csv` | freezes what F believed at approval or handoff time |
| Foundation metrics | planned one-off in Batch 000 | output | `out/analysis_reports/hf_learning_foundation_metrics_latest.csv` | explicit bridge coverage and stage coverage metrics for deterministic proof |
| Joined market facts | `scripts/one_off/HF001_build_learning_baseline.py` | output | `out/analysis_reports/hf_learning_market_facts_latest.csv` | per SKU or per observation market context from H and E/B truth anchors |
| Joined action outcomes | `scripts/one_off/HF001_build_learning_baseline.py` | output | `out/analysis_reports/hf_learning_action_outcomes_latest.csv` | H decision, write, response window, and later outcome link |
| Scrape gap report | `scripts/one_off/HF001_build_learning_baseline.py` | output | `out/analysis_reports/hf_learning_scrape_gap_report_latest.csv` | identifies missing, stale, or thin scrape coverage without changing scanner state |
| 30-day alignment pack | `scripts/one_off/HF002_build_learning_alignment.py` | output | `out/analysis_reports/hf_learning_alignment_30d_latest.csv` | expected vs actual vs market-fact comparison |
| Factor impact summary | `scripts/one_off/HF002_build_learning_alignment.py` | output | `out/analysis_reports/hf_learning_factor_impacts_latest.csv` | explain which factors shift estimate error or tactic results |
| Health checklist | `scripts/one_off/HF003_build_learning_health_checks.py` | output | `out/analysis_reports/hf_learning_health_checklist_latest.csv` | schema, freshness, and trigger-consistency checks in one file |
| Shadow calibration factors | `scripts/flows/F/F080_build_feedback_calibration_shadow.py` | output | `out/systems/F/live/feeder_feedback_calibration_live.csv` | shadow-only until signed off |
| Operator report | `scripts/one_off/HF005_build_learning_operator_report.py` | output | `out/reports/hf_learning_operator_report_latest.csv` | plain-English metric pack for operators |
| Health and schema checks | `scripts/one_off/HF003_build_learning_health_checks.py` | output | `out/analysis_reports/hf_learning_health_checklist_latest.csv` | every new output has schema and freshness truth |
| Existing scrape evidence | existing F owner | input | `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` | current shared scrape fact file that scanner and learning must both reuse |
| Existing chart daily raw | existing F owner | input | `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv` | daily chart point history for demand and pricing context |
| Targeted rescrape subset | existing one-off F tool | input/output | `out/analysis_reports/f_targeted_rescrape_subset_latest.csv` | controlled way to request fresh scrape through the current scanner path |
| Full BBP evidence pack | existing one-off F tool | input/output | `out/analysis_reports/f_full_capture_manifest_latest.csv` | sampled deep-capture path for monthly validation and root-cause review |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `hf_learning_identity_bridge_latest.csv` | after any lineage or bridge-rule change | if joined marts use older bridge truth | new bridge coverage and ambiguity checks | foundation layer first |
| `hf_learning_assumption_snapshots_latest.csv` | after any approval or handoff lineage change | if alignment compares actuals to unfrozen estimates | new snapshot coverage and stage-truth checks | approval-stage anchor allowed when PO handoff rows are zero |
| `hf_learning_foundation_metrics_latest.csv` | after each Batch 000 rebuild | if operator or phase scoring uses stale coverage facts | metric schema + deterministic value checks | keeps unresolved and stage coverage explicit |
| `hf_learning_market_facts_latest.csv` | after any H or E/B source-contract change | if operator report is newer than facts | new schema + row-reconcile checks | one-off first |
| `hf_learning_action_outcomes_latest.csv` | after any H strategy contract change | if alignment uses older action facts | new schema + terminal-state checks | must separate eligible / decided / attempted / applied |
| `hf_learning_scrape_gap_report_latest.csv` | after any baseline build | if rescrape decisions rely on older gap report | new coverage and freshness checks | should explain exactly why scrape is needed |
| `hf_learning_alignment_30d_latest.csv` | 30 days | when monthly review depends on older alignment | new discrepancy and coverage checks | monthly process |
| `hf_learning_factor_impacts_latest.csv` | after each alignment rebuild | if shadow calibration uses older factor report | new factor-bucket sanity checks | no silent bucket drops |
| `feeder_feedback_calibration_live.csv` | after each factor refresh | if F summary cites older calibration | new F-scoped schema and staleness checks | shadow mode first |
| operator report output | after facts or alignment change | if review relies on older report | report manifest + source timestamp checks | report is never the only truth |
| `feeder_legacy_scrape_evidence_live.csv` | existing F cadence | if learning builder expects rows that are stale or empty | existing F runtime checks plus new learning coverage checks | scanner-owned shared source |
| `feeder_legacy_chart_daily_raw_live.csv` | existing F cadence | if monthly alignment relies on stale chart rows | existing F runtime checks plus chart-point coverage checks | scanner-owned shared source |

## Integration points
- APIs:
  - none new in this planning ticket
  - later monthly alignment reuses the existing F scrape owners instead of creating a second scraper
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - H outputs feed the joined facts
  - E/B outputs provide actual sales and economics truth
  - F analysis packs provide estimate baselines and validation structure
  - later F shadow calibration consumes factor outputs
  - scrape start path for fresh evidence:
    - prepare a controlled subset through `scripts/one_off/F007_prepare_targeted_rescrape_subset.py`
    - let `scripts/flows/F/F061_run_legacy_first_checks_local.py` own the actual scrape and contract writes
    - use `scripts/one_off/F008_capture_full_bbp_evidence_pack.py` only for sampled deep capture, not routine queue ownership
  - direct `Webscrape.py` runs are not the default owner path for this ticket

## Risks and mitigations
- Risk:
  - we build another report layer without fixing the missing joins
  - Mitigation:
    - Batch 001 is blocked on explicit key mapping and row reconciliation
- Risk:
  - operator sees blended numbers that hide whether H wrote, matched, or merely observed
  - Mitigation:
    - keep separate states for eligible to write, decision to change price, write attempted, and write applied successfully
- Risk:
  - monthly alignment gets mixed into daily loops too early
  - Mitigation:
    - keep it one-off first, then promote only after proof
- Risk:
  - F starts trusting H evidence that is still thin or biased
  - Mitigation:
    - shadow calibration only, with sample-size and confidence fields
- Risk:
  - stale aggregate health output creates false block or false confidence
  - Mitigation:
    - use scoped health and source timestamps in proof, call stale aggregate outputs stale
- Risk:
  - we compare actual outcomes with rewritten or later-stage estimates instead of true buy-time assumptions
  - Mitigation:
    - Batch 000 must freeze assumption snapshots from approval or PO-handoff lineage before alignment work starts
- Risk:
  - `candidate_id`, `supplier_sku`, `asin`, and `sku` do not bridge cleanly, causing false joins
  - Mitigation:
    - Batch 000 must build an explicit identity bridge and report unresolved rows before any factor analysis is trusted
- Risk:
  - tactic analysis over-credits or misreads outcomes because the result window is undefined
  - Mitigation:
    - lock H and F outcome windows before building success metrics

## Success monitoring
- Build and join truth:
  - identity bridge coverage is reported explicitly
  - frozen assumption snapshot coverage is reported explicitly
  - joined market-facts rows are nonzero
  - joined action-outcome rows are nonzero
  - join-rate by `sku + asin` and `candidate_id` is reported explicitly
  - no builder mutates scanner-owned source files in Batch 001 and Batch 002
- Initial quality thresholds:
  - F lineage bridge coverage on `candidate_id + asin` should be `>= 99%`
  - `candidate_id -> sku` bridge coverage should be reported and unresolved rows must remain explicit
  - assumption snapshot coverage should be `>= 95%` of in-scope approval-decision rows
  - factor buckets with fewer than `30` rows must be marked thin-sample and must not drive shadow calibration
- Scrape coverage:
  - scrape coverage rate for in-scope F candidates is measured
  - stale scrape share is measured
  - missing completed-month BBP share is measured
  - rescrape recommendation list is produced only when a threshold is failed
- Strategy learning:
  - undercut frequency by SKU and tactic family
  - rival reaction lag after our price move
  - share-hold retention after no-write decisions
  - reset-up outcome after single-rival and multi-seller cases
  - applied-write success rate and later outcome rate
- Estimate accuracy:
  - units bias and profit bias
  - median absolute error by factor bucket
  - overestimate vs underestimate share
  - error direction under Amazon pressure, high seller count, and compressed ladders
- Scanner sharing:
  - same scrape evidence row is readable by current scanner outputs and by the new learning builder
  - targeted rescrape must update queue state without deleting unrelated supplier rows
  - sampled full-capture validation must remain one-off and must not become hidden daily behavior
- Window definitions:
  - H tactic metrics must be reported against fixed windows: `15m`, `2h`, `24h`, `72h`
  - F product-learning metrics must be reported against fixed windows: `30d`, `60d`, `90d`

## Proof rules
- Execution prep gate:
  - before any coding phase starts, lock the source set for this ticket
  - later phases must reuse that frozen evidence only
- H runtime handoff rule:
  - for any Phase 5 runtime-owned H edit, request controlled restart drain using:
  - `requested_by=controlled_restart_gate|reason=overnight_restart_eval`
  - wait for `out/systems/H/live/H_restart_drain.ready` before editing
  - restart only via `run_H_cycle.bat` after isolated proof completes
- What counts as code fix applied:
  - new active plan exists
  - research report, plan, data contracts, runbook, and coding plan exist
  - later batches only claim code changes when owned scripts or tests are edited
- What counts as isolated verification passed:
  - for this planning reset:
    - new plan folder exists with the required documents
  - for later coding batches:
    - scoped pytest pack passes
    - one-off builder completes
    - row counts and joins reconcile
- What counts as live loop verification confirmed:
  - not applicable until later promotion batches
  - no batch may claim live-loop success until a loop-owned path exists and its scoped health proves the new outputs

## Batch list
- Execution prep gate:
  - complete
  - freeze input set, open phase scorecard, and lock no-new-input mode before Batch 000
- Batch 000:
  - complete
  - foundation lock
  - build identity bridge, frozen assumption snapshots, and fixed measurement-window rules before joined marts
- Batch 001:
  - complete
  - joined evidence baseline and scrape-owner wiring
  - build read-only market-facts and action-outcomes marts from existing H, E/B, and F artifacts
  - emit scrape gap report and explicit coverage stats
- Batch 002:
  - complete
  - monthly alignment, rescrape trigger, and factor-impact pack
  - compare BBP/F estimates, live H market facts, and actual 30-day outcomes
  - when scrape coverage thresholds fail, prepare a targeted rescrape subset through the existing F owner path
- Batch 003:
  - complete
  - F shadow calibration feed
  - create factor outputs that F can consume without changing live buy decisions
- Batch 004:
  - complete
  - operator reporting and scoped health checks
  - produce plain-English output and alerts for learning quality, not just runtime faults
- Batch 005:
  - complete
  - H strategy experiment hooks
  - add cohort-friendly evidence so future tactic changes can be judged honestly
- Batch 006:
  - complete
  - sign-off and promotion decision
  - decide what stays one-off, what becomes scheduled, and what remains advisory only

## Archive rule
- When this plan can move to archive:
  - identity bridge and frozen assumption snapshots are built and trusted
  - joined evidence outputs are built and reconciled
  - scrape gap reporting and rescrape trigger rules are documented and proven
  - monthly alignment output exists and is checkable
  - F shadow calibration exists with explicit health truth
  - operator can judge H and F learning from one durable report pack
  - any runtime promotion decision is documented clearly

## Active execution document
- Use `plans/active/h-f-feedback-learning-loop-v1/CODING_PLAN.md` as the durable phase-by-phase execution sequence.
- It must hold:
  - current phase
  - allowed files
  - scoped tests
  - proof rules
  - next automatic step
