# Self Healing Plan (End Game)

This plan turns the system into a self checking, self healing pipeline with clear alerts and no partial publishes.

## Current status (latest health check)
- FAIL: 0
- WARN: order_master_blank_cogs_lvl1plus > 0 (missing tokens for some orders)
- Missing L1 keys: 0
- Order_Master date gap: 0

Meaning: the Order_Master structure is now correct. Remaining gaps are token coverage only.

## End goal
- A and B never clash (run lock).
- Health check is the gate (no publish on FAIL).
- Outputs are staged, then published once per cycle (no partial data).
- Schemas are enforced (fail fast on column drift).
- Rollback is possible (last 3 snapshots).
- Alerts are visible immediately (no manual hunting).

## Phase 1 (done)
- Health check script A015 and alert summary after A.
- Shared run lock for A and B (out/run_cycle.lock).
- Runbooks updated with self healing rules.

## Phase 2 (next)
- Staged writes and publish gating.
- Build to out/staging/<run_id>/..., then publish only if A015 has no FAIL.
- Apply to Order_Master, Token_Ledger, Token_Allocations, PnL summary first.

## Phase 3
- Schema validation and data contracts.
- Required columns + types for:
  - out/orders_all.csv
  - out/order_items_all.csv
  - out/financial_events_level1.csv
  - out/order_master.csv
  - out/token_ledger_live.csv
  - out/token_cogs_ledger.csv
  - out/inventory_summaries.csv
- Fail fast if a schema changes.

## Phase 4
- Snapshots and rollback.
- Keep last 3 publishable snapshots of Order_Master, Token_Ledger, Token_Allocations, PnL summary.
- Add a restore command that republish from snapshot only.

## Phase 5
- Central retry logic and rate limit handling.
- One wrapper for retries with backoff, caps, and log of attempt + wait.

## Daily operating flow (target)
1) Run A once in the morning.
2) A015 health check runs and prints FAIL/WARN summary.
3) If FAIL: stop and fix before publishing.
4) B loop runs during the day.
5) B only publishes at the end of cycle (quiet publish) to avoid partial data.

## Token backdater decision rule
- Do NOT run full backdate unless token shortfall is widespread.
- Use the health check + token recon to decide.

Decision:
- If missing token COGS is isolated to a few SKUs -> run BACKDATE_SKU_FILTER for those SKUs only.
- If missing token COGS is widespread -> run one full backdate overnight with B stopped.

## Self healing rules (non negotiable)
- Any new feature must add a health check item and an alert rule.
- Any new output file must have a schema check.
- Any sheet write must be staged and published once complete.
- Any loop step must be idempotent.
- Runbooks must be updated when rules change.

## Success criteria
- A015 shows FAIL=0 for 3 consecutive runs.
- Token coverage WARN decreases or is explained by known in flight SKUs.
- No partial or blank Order_Master rows.
- A and B no longer clash.

End.
