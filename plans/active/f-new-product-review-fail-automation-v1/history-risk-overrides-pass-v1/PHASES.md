# Phases

## Phase 1 - Build Audit
- Status: planned
- Goal:
  - Create a read-only audit for clean Pass rows with contradictory history-risk evidence.
- Outputs:
  - `out/analysis_reports/f_history_risk_pass_conflict_audit_latest.csv`
- Proof:
  - tests pass
  - output exists
  - counts reconcile to current clean Pass rows

## Phase 2 - Decision Brief
- Status: draft complete
- Goal:
  - Avoid raw CSV review by summarizing the rule groups in plain language.
- Proof:
  - `DECISION_BRIEF.md` exists with recommended routing outcomes.

## Phase 3 - Triage Integration
- Status: planned
- Goal:
  - Add accepted history-risk evidence into F021 triage output.
- Non-goal:
  - No upstream enforcement in this phase.

## Phase 4 - F019 Upstream Routing
- Status: planned
- Goal:
  - Move accepted history-risk routing into F019 so future clean Pass packs exclude obvious history-risk conflicts.
- Proof:
  - clean Pass count changes
  - routed rows are visible in near-miss/manual-review output
  - summary counts reconcile

## Phase 5 - Upstream Backtest Review
- Status: optional
- Goal:
  - If F019 routing proves stable, inspect whether the earlier backtest qualification layer should produce a stricter decision state.
- Non-goal:
  - Do not change model policy until F019 evidence proves the rule groups.

