# Plan

## Goal
- Final outcome:
  - make H strategy work from truthful inputs and truthful outputs
  - remove invalid ceiling/floor states from live H artifacts
  - repair result reporting so we can judge strategy quality without manual CSV archaeology
  - tune the crowded-ladder, suppression, and controlled-exit paths using live evidence instead of assumptions

## Non-goals
- Do not do:
  - Google Sheets changes
  - local DB rewrites
  - scheduler ownership redesign
  - new one-off tools inside daily loops
  - broad H masterplan expansion outside the current repricer decision path

## Current state
- What exists already:
  - H runtime is producing fresh strategy and floor artifacts.
  - The prior alignment slice is complete and ready to archive.
  - Latest evidence used for this plan:
    - `out/h_ceiling_events.csv` latest run `20260416T211441Z`
    - `out/phase1_runtime_floor_snapshot_latest.csv` at `2026-04-16T21:14:41Z`
    - `out/h_strategy_outcome_daily.csv` latest date `2026-04-16`
    - `out/system_health_checklist.csv` latest snapshot `2026-04-16T20:00:10Z`
- Known pain points:
  - Ceiling contract is still broken in live data:
    - `8 / 58` latest ceiling-event rows have `true_binding_ceiling_gbp < hard_floor_gbp`
    - `11 / 89` current runtime-floor rows have `true_binding_ceiling_gbp < trace_floor_total_gbp`
    - all latest ceiling conflicts are `COMPLIANCE`-bound conflicts
  - Ceiling input quality is weak:
    - `37 / 58` latest ceiling-event rows carry `CEILING_RULE_INPUTS_MISSING`
  - Strategy conversion is still weak even after false-fail cleanup:
    - `multi_seller_ladder_cap`: `1181` decisions, `6` success, `512` expired, `663` aborted, `0` failed
    - `suppression_reactivation`: `126` decisions, `1` success, `78` expired, `45` aborted, `0` failed
    - `controlled_exit`: `11` decisions, `11` applied, `0` success, `11` expired
    - `raise_find_loss / RAISE_FIND_LOSS_LADDER_CAP`: `588` decisions, `137` success, `1` failed
  - Operator metrics are not fully trustworthy:
    - latest `h_strategy_outcome_daily.csv` contains rows where `at_floor_rows > decision_rows`
    - examples:
      - `multi_seller_ladder_cap / MULTI_SELLER_LADDER_CAP`: `decision_rows=19`, `at_floor_rows=605`
      - `suppression_reactivation / SUPPRESSION_REACTIVATION`: `decision_rows=126`, `at_floor_rows=189`
- Known alerts or reliability concerns:
  - Health was last clean at `2026-04-16T19:59:56Z` (`OK fail=0 warn=0`), but that snapshot is older than the latest H strategy slice and cannot be used as fresh confirmation for the new phase.
  - Current live H data contains a real logic/data alert:
    - invalid binding ceilings are still present in latest outputs
    - rollup integrity is not yet decision-grade

## Target state
- What changes:
  - The ceiling contract becomes two-stage and truthful:
    - raw ceiling evidence can still be logged
    - effective live binding ceiling must never land below the hard floor
  - Strategy daily rollups become internally consistent and health-checked.
  - Tactic optimisation is based on clean operator evidence:
    - crowded ladder regain
    - single-rival reset
    - suppression reactivation
    - controlled exit
    - seller-detail hold
- What stays the same:
  - hard floor remains absolute
  - H remains the owner of repricer writes
  - no sheet writes are added
  - no DB ownership changes are added

## Systems touched
- Flow(s):
  - H primary
  - A health for scoped checks only
- Shared dependencies:
  - `A016` / daily intel inputs already consumed by H
  - `A018` / floor table
  - listing offer snapshots
  - seller-detail snapshots
- Runtime or scheduler ownership concerns:
  - keep all logic inside the owned H path
  - do not add manual overlap with B or new sidecar loops

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Ceiling decision source logic | `phase1_probe_engine.py` | logic | `scripts/phase1/phase1_probe_engine.py` | Earliest known owner for ceiling-below-floor decision fallback |
| Strategy rollup and runtime contract | `phase1_main_loop.py` | logic/output | `scripts/phase1/phase1_main_loop.py` | Owns strategy outcome rows, daily rollup increments, and ceiling-event append path |
| CSV schema and upsert rules | `phase1_storage.py` | output contract | `scripts/phase1/phase1_storage.py` | Owns H output schemas and normalisation |
| H scoped health checks | `A015_build_system_health_check.py` | health/output | `scripts/flows/A/A015_build_system_health_check.py` | Must gate new ceiling truth and rollup integrity checks |
| Current ceiling event log | H runtime | output | `out/h_ceiling_events.csv` | Must preserve raw source evidence and safe effective binding ceiling |
| Current runtime truth slice | H runtime | output | `out/phase1_runtime_floor_snapshot_latest.csv` | Main live truth view for ceiling vs floor |
| Strategy outcome daily rollup | H runtime | output | `out/h_strategy_outcome_daily.csv` | Must become internally consistent before optimisation decisions |
| Strategy outcome event log | H runtime | output | `out/h_strategy_outcome_log.csv` | Used for sample review and scenario conversion checks |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `out/phase1_runtime_floor_snapshot_latest.csv` | existing H cadence | existing H cadence | existing freshness check | Existing truth slice |
| `out/h_ceiling_events.csv` | 1 H cycle | 3 H cycles | existing `h_ceiling_events_current` plus new integrity check | Add scoped check for effective ceiling below floor |
| `out/h_strategy_outcome_daily.csv` | 24h | 48h | existing `h_strategy_outcome_daily_current` plus new integrity check | Add impossible-count check |
| `out/h_strategy_outcome_log.csv` | 1 H cycle | 3 H cycles | existing freshness checks | Used for scenario proof after tuning |
| `out/phase1_floor_table_latest.csv` | existing A cadence | existing A cadence | existing floor-table checks | Used as floor truth reference |

## Integration points
- APIs:
  - no new APIs planned
  - continue using existing listing-offer and seller-detail inputs
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - H reads floor and offer inputs
  - H writes ceiling events, runtime floor snapshot, and strategy outcome outputs
  - A reads H outputs for health and alerting

## Risks and mitigations
- Risk:
  - We keep clamping downstream while leaving the ceiling source invalid.
  - Mitigation:
  - Fix the effective binding ceiling contract at the owner stage and preserve raw evidence separately.
- Risk:
  - We optimise tactics on top of broken daily rollups.
  - Mitigation:
  - Phase 1 blocks optimisation work until rollup integrity checks pass.
- Risk:
  - Controlled exit looks ineffective because the success contract is wrong, not because the tactic is wrong.
  - Mitigation:
  - Review controlled-exit success semantics as part of the conversion phase.
- Risk:
  - Missing seller-detail continues to trap SKUs in hold states with no clear operator action.
  - Mitigation:
  - Add explicit conversion review and escalation rules for `SELLER_DETAIL_HOLD`.

## Proof rules
- What counts as code fix applied:
  - required files are patched and targeted tests pass locally
- What counts as isolated verification passed:
  - unit and targeted contract tests pass for the touched H logic and storage code
- What counts as live loop verification confirmed:
  - latest H artifacts show no effective ceiling below floor
  - latest strategy daily rollup passes integrity checks
  - post-change scenario samples meet the exact thresholds stated in `CODING_PLAN.md`
  - forced H proof window reflects the new checks as healthy

## Batch list
- Batch 001:
  - repair truth and measurement
  - define the effective ceiling contract
  - repair daily rollup integrity
  - add H-scoped health checks for both
- Batch 002:
  - fix earliest-stage ceiling source selection and conflict handling
  - preserve raw conflict evidence without letting invalid ceilings drive runtime state
- Batch 003:
  - optimise crowded-ladder, suppression, seller-detail hold, and controlled-exit conversion using the cleaned evidence layer
- Batch 004:
  - monitored validation, result scoring, sign-off, archive

## Archive rule
- When this plan can move to archive:
  - predecessor plan is archived
  - effective ceiling-below-floor conflicts are `0` in live proof windows
  - strategy daily rollup integrity check is green
  - post-change scenario thresholds in `CODING_PLAN.md` are met or explicitly parked with exact remaining proof
  - operator output is good enough to judge what is working and what is not without manual reconstruction
