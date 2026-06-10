# Hometime Prompt

Use this prompt in a new Codex chat to execute Batch 004 in hometime mode.

## Prompt

Ticket: `f-cycle-sales-history-truth-v2`

Mode:
- Hometime mode
- quiet execution
- carry work end to end without routine checkpoint messages
- interrupt only for contradiction, new/worse alert, blocked proof boundary, or approval-required scope change

Goal:
- Complete Phase 4 / Batch 004 of `plans/archive/2026/f-cycle-sales-history-truth-v2`.
- Add explicit seasonality, stability, and recent-performance classifier truth.
- Do not start Batch 005 confidence-engine work in this ticket.

Read first:
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_004.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_003_REPLY.md`

Why this is the next task:
- Batch 003 proved qualification truth and source alignment on READY rows.
- The next root cause is missing explicit seasonality/stability/recent classifier states.
- Batch 004 is the execution-ready classifier hardening step before confidence expansion.
- Weekend evidence review on `2026-04-20` confirmed the dataset is already sufficient for this phase.
- Do not restart broad scrape collection as part of this ticket.

Root-cause order:
1. Lock a controlled proof boundary so classifier proof is not mixed with moving live evidence.
2. Implement seasonality/stability/recent classifier outputs at the earliest owner stage.
3. Carry classifier truth through replay and summary with explicit source and reason path.
4. Extend F health and validation so classifier integrity can be proven directly.
5. Run bounded rebuild proof and leave owner path in final truthful state.

Hard boundaries:
- no Google Sheets changes
- no local DB changes
- no H runtime changes
- no confidence-model implementation
- no manual per-ASIN CSV patching as truth
- no restarting a broad `stocklist_supplier` scrape loop just to gather more of the same dataset

Working baseline:
- use the frozen rebuild outputs from `2026-04-20`
- targeted cleanup exists separately at:
  - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
- only use targeted retry if a known Phase 4 proof gap requires it

Ownership and safety checks:
- Before rebuild proof, verify if live owner movement would create stale-proof ambiguity.
- If yes, use one truthful boundary:
  - frozen unchanged-input proof window
  - or safe owner pause boundary
- If ownership is paused, resume and confirm loop owner returns on `stocklist_supplier`.

Execution rules:
- stay inside Batch 004 allowed files and scope
- keep root-cause fixes at earliest owner stage
- write factual proof into plan docs before ending ticket

Required proof:
- classifier proof:
  - seasonality, stability, and recent states present with explicit reason tags
  - maturity-gated seasonality behavior proven on fixtures
- source-alignment proof:
  - READY summary rows have non-blank classifier states and reason path
  - no READY row silently defaults to optimistic classifier state
- health proof:
  - `f_backtest_demand_basis_integrity = ok`
  - `f_backtest_price_qualified_demand_integrity = ok`
  - classifier-integrity checks = `ok`
  - target `f_backtest_health_staleness = ok`
- validation proof:
  - `f_sales_history_validation_latest.csv` shows classifier states/reason path plus raw-vs-qualified context

Required final status language:
- `code fix applied`
- `isolated verification passed`
- `controlled Phase 4 proof completed` or `parked pending controlled F proof window`
