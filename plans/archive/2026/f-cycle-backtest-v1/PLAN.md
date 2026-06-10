# Plan

## Goal
- Final outcome:
  - keep the F backtest v1 tracked under the new active planning flow
  - preserve the completed execution history from Batches 001 to 003
  - make the next continuation point explicit without reopening completed work

## Non-goals
- Do not do:
  - rewrite replay mode and ROI ladder rules
  - change recommendation logic again
  - wire the backtest into H runtime ownership
  - treat one-off refresh scripts as daily loop scripts
  - change Google Sheets or local DB state

## Current state
- What exists already:
  - F070 to F075 exist in `scripts/flows/F/`
  - O operator UI includes backtest summary display, policy controls, and calibration review panel
  - guidebook exists in `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - latest live backtest outputs exist under `out/systems/F/live/`
  - latest calibration pack exists under `out/analysis_reports/`
  - `scripts/one_off/F003_refresh_backtest_after_policy_change.py` already exists as the historical refresh chain after a policy change
- Known pain points:
  - the durable plan lived only in `reference/Backtest Strategy Ideas/`
  - no active plan folder existed before this switch-over
  - central roadmap/current-state docs do not yet clearly mention this backtest phase
  - repo worktree is already very dirty, so this plan must stay tightly scoped
  - Monday raw F evidence has grown, but the latest backtest snapshot still reflects the earlier 2026-04-11 rerun
  - operator expectation-alignment work has not yet been written down as a durable batch with sample buckets and review notes
  - explicit simple decision state (`pass` / `fail` / `manual_review`) is not yet locked alongside the richer recommendation labels
  - historical result changes after policy updates are only partly proven and need to become an explicit operator-trust feature
  - future-scan mode behavior still needs clear proof in both `screening` and `data_collection`
  - BBP monthly sales demand can be overstated because replay currently prefers helper chosen units over the trusted past-month chart signal
  - current BBP sales chart handling does not yet explicitly separate completed months, current partial month, and future projected months for replay use
  - there is no full sampled-ASIN audit list yet, so operator review is still relying on one-at-a-time spot checks
- Known alerts or reliability concerns:
  - current global health snapshot check on 2026-04-13 showed no `warn` or `fail` rows in `out/system_health_checklist.csv`
  - latest backtest health snapshot at `2026-04-11T12:10:08Z` is all `ok`
  - Monday raw F evidence is fresher than the current backtest outputs, so the April 11 backtest proof is now stale for any new calibration conclusions
  - any future code change will require a fresh rerun

## Target state
- What changes:
  - plan tracking moves into `plans/active/f-cycle-backtest-v1/`
  - source plan and batch docs are copied into the active plan folder
  - current state, runbook, and contracts are written in the new format
  - a guided operator-review stage exists for representative scenario samples rather than ad hoc ASIN discussion
  - user expectation alignment is captured durably in the plan folder
  - policy changes can rerun past backtest outputs truthfully using the same raw evidence
  - summary and operator surfaces can show a simple decision state without losing the richer fit labels
  - future F scans are proven in both `screening` and `data_collection` modes
  - sampled ASIN review can use a single exported audit list with scraped BBP month history, replay demand basis, and mismatch visibility
- What stays the same:
  - original research and batch docs remain in `reference/Backtest Strategy Ideas/`
  - F and O ownership boundaries remain unchanged
  - backtest remains a controlled F/O feature, not a live H runtime feature

## Systems touched
- Flow(s):
  - F flow
  - O flow
- Shared dependencies:
  - F chart history
  - E demand signal outputs
  - product identity and economics inputs already reused by F071
- Runtime or scheduler ownership concerns:
  - none for this switch-over ticket
  - F003 is one-off only and must stay outside daily loops

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Policy snapshot | `F070_build_backtest_policy_snapshot.py` | output | `out/systems/F/live/feeder_backtest_policy_live.csv` | bootstrap active policy |
| Policy update inbox | `O400_operator_ui.py` producer, `F075_apply_backtest_policy_updates.py` consumer | handoff | `out/systems/F/inbox/feeder_backtest_policy_update_events.csv` | append-only staged control path |
| Input view | `F071_build_backtest_input_view.py` | output | `out/systems/F/live/feeder_backtest_input_view_live.csv` | one row per seller_sku + asin + policy_id |
| Replay daily | `F072_run_backtest_replay.py` | output | `out/systems/F/live/feeder_backtest_replay_daily_live.csv` | one row per seller_sku + asin + day + policy_id |
| Summary | `F073_build_backtest_summary.py` | output | `out/systems/F/live/feeder_backtest_summary_live.csv` | consumed by O |
| Health | `F074_build_backtest_health.py` | output | `out/systems/F/live/feeder_backtest_health.csv` | F-scoped checks |
| Calibration review pack | `F002_build_backtest_calibration_set.py` | output | `out/analysis_reports/f_backtest_calibration_set_latest.csv` | operator review artifact |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `feeder_backtest_policy_live.csv` | on-demand | on-demand | `f_backtest_policy_single_active_row` | exactly one active row |
| `feeder_backtest_input_view_live.csv` | on-demand | on-demand | `f_backtest_input_view_schema` | latest row count seen: 355 |
| `feeder_backtest_replay_daily_live.csv` | on-demand | on-demand | `f_backtest_replay_daily_schema` and `f_backtest_replay_row_coverage` | latest row count seen: 108388 |
| `feeder_backtest_summary_live.csv` | on-demand | on-demand | `f_backtest_summary_schema` and `f_backtest_summary_row_coverage` | latest row count seen: 355 |
| `feeder_backtest_health.csv` | after each refresh | stale after any code change | all checks must be `ok` (including share, attribution, and prior-dependency checks) | latest observed_utc `2026-04-11T12:10:08Z` |
| `f_backtest_calibration_set_latest.csv` | after each refresh | stale after any code change | review pack must rebuild successfully | latest observed_utc `2026-04-11T12:10:17Z` |

## Integration points
- APIs:
  - none in this ticket
- Sheets:
  - none
- Local DB:
  - none
- CSV or file handoffs:
  - O UI writes policy update events into the F inbox CSV
  - F summary feeds backtest columns into O restock views
  - calibration pack is read-only in the UI

## Risks and mitigations
- Risk:
  - old reference docs and new active plan drift apart
  - Mitigation:
    - keep source docs copied into the active plan folder and treat this folder as current ticket memory
- Risk:
  - future sessions assume the backtest is still only a research idea
  - Mitigation:
    - status file now states that build and operator control batches are already complete
- Risk:
  - future changes accidentally pull one-off refresh logic into loops
  - Mitigation:
    - runbook marks F003 as one-off only and keeps live runtime ownership out of scope
- Risk:
  - pass-accuracy tuning drifts into endless case-by-case debate
  - Mitigation:
    - Batch 008 must review representative scenario buckets and record pattern-level conclusions once they repeat
- Risk:
  - policy changes become future-only and do not reclassify past evidence consistently
  - Mitigation:
    - treat F003 historical refresh as the required path and prove it with fixtures and rerun evidence
- Risk:
  - `data_collection` mode and `screening` mode tell conflicting stories
  - Mitigation:
    - Batch 008 must define and test the exact behavior boundary for both modes
- Risk:
  - backtest profit can be overstated if BBP future bars or helper chosen demand leak into replay
  - Mitigation:
    - Batch 009 must lock a trusted past-month demand rule and add health visibility for demand-basis misuse
- Risk:
  - fixing one visible ASIN could still leave broader BBP chart extraction or basis-selection errors hidden across the sample set
  - Mitigation:
    - Batch 009 must build a full sampled-ASIN audit export so the operator can review the whole pack row by row

## Proof rules
- What counts as code fix applied:
  - relevant files are changed in the active plan folder or the owned F/O backtest files
- What counts as isolated verification passed:
  - for plan-tracking work: plan folder exists, source batches are copied, status files reflect actual current outputs
  - for backtest code work: required pytest pack passes and the canonical F refresh chain completes
- What counts as live loop verification confirmed:
  - not applicable for this v1 backtest plan because it is not a scheduler-owned live loop

## Batch list
- Batch 001:
  - complete
  - deterministic ASIN resolution, calibration mismatch artifact, guidebook, full rerun and proof
- Batch 002:
  - complete
  - critical Amazon recommendation cap, full rerun, full test pack, sign-off evidence
- Batch 003:
  - complete
  - operator policy inbox, apply script, UI controls, refresh runner, calibration review panel
- Batch 004:
  - complete in this ticket
  - active-plan switch into `plans/active/` and current-state alignment
- Batch 005:
  - complete in this ticket
  - measured per-scenario share rates in replay, plus new share-validity health check
- Batch 006:
  - complete in this ticket
  - attribution-confidence enrichment in input and summary flow plus attribution health check
- Batch 007:
  - complete in this ticket
  - governed measured-share caps, replay share-source tags, summary basis update, and prior-dependency health check
- Batch 008:
  - defined, not yet executed
  - operator expectation alignment, scenario review pack, historical result refresh proof, explicit decision-state lock, and dual-mode validation for `screening` vs `data_collection`
- Batch 009:
  - defined, not yet executed
  - BBP monthly sales demand cleanup, trusted completed-month selection, future-bar exclusion, replay demand-basis separation, sampled-ASIN audit export, and demand-basis health proof
- Next implementation batch:
  - Batch 008 remains the active user-alignment batch
  - Batch 009 is the next root-cause cleanup batch for demand-basis truth once Batch 008 review findings are captured enough to lock the rule

## Archive rule
- When this plan can move to archive:
  - after the next agreed continuation batch is complete and the active work moves to a newer ticket or a completed archived state
