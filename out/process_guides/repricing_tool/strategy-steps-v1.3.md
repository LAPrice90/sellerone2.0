Repricing Phase Engine Blueprint (v1.3)

CHANGELOG (v1.2 vs v1.1)
- Added implemented architecture details: single write gate (`evaluate_live_write_gate()`), unified writer/dashboard gating, contract tests, and `H_PHASE_ENGINE_*` runtime flags.
- Updated Phase 1 pricing behavior to match implementation: dynamic undercut bias, ROI floor around 7%, and no step-down cap.
- Added system guardrails section for single-source gating, contract enforcement, and health checklist alignment.
- Added planned section for suppressed Buy Box handling (current hold behavior and intended fallback behavior).
- Recorded solved audit contradictions: below-floor streak, recovery streak, grace-vs-fast-track behavior, and phase lock handling.
- Added explicit "do not reintroduce" list for removed step-down throttles and artificial daily move limits.
- Added known strategic gaps and operational rules for H/B loop operations and maintenance one-shots.
- Added strategy go-live clock support using `H_STRATEGY_GO_LIVE_UTC`, including conditional Phase 1 reseed (`PHASE_GO_LIVE_RESEED_APPLIED`) with no full history wipe.
- Added inbound-aware inventory activation and discovery behavior (`inventory_active`, `inbound_total`, `INBOUND_DISCOVERY`, `INBOUND_PRICE_DISCOVERY`) so inbound SKUs are monitored, not excluded.
- Added stock source priority order for per-SKU resolution (`inventory_summaries` -> latest dated `inventory_snapshot` -> `stock_snapshot_latest`) and stricter `STOCK_UNKNOWN` rule.
- Added scan-state writeback merge for `phase1_sku_scan_state.json` so `last_scan_utc` keeps newest timestamp per SKU.
- Added fixed-tab dashboard publishing support (`--view-tab`, `H_PHASE1_OBSERVATION_VIEW_TAB`, default `PRICING_DASHBOARD`) for normal non-dated operation.
- Added dashboard visibility updates: `PROBE` column and inbound-active row inclusion rule.
- Added confirmed non-issue note: no SKU key mismatch; inbound zero values can be feed freshness delay, not key-join failure.
- Added explicit "Do not revert (v1.3)" hard rules for implemented v1.3 behavior.

Purpose
Create a controlled stock-management and pricing-escalation system that:
- Prevents panic liquidation
- Prevents long-term capital stagnation
- Protects profitable SKUs
- Forces structured exit of weak SKUs
- Avoids resets from single random sales
- Prevents new stock from being penalised

This system is layered, mechanical, and policy-driven.

1. System Architecture (3 Layers)

Layer 1 - Diagnostics (facts only)
This layer does not choose strategy. It only calculates state metrics per SKU.

Required inputs per SKU
- days_since_last_sale (diagnostic only, not a phase trigger)
- days_since_last_restock
- strategy_start_date
- days_under_new_strategy = today - strategy_start_date
- rolling_14d_units
- rolling_30d_units
- best_competitor_price
- hard_floor_price
- current_stock_units
- estimated_storage_cost_per_day

Derived flags and metrics
- below_floor_market = best_competitor_price < hard_floor_price
- below_floor_streak_days (implemented)
- previous_price_gap_large = prior_price_gap_pct > price_gap_large_threshold
- low_velocity = rolling_14d_units < velocity_threshold
- in_grace_period = days_since_last_restock < grace_period_days
- inventory_risk = current_stock_units > stock_risk_threshold
- storage_cost_pressure = current_stock_units * estimated_storage_cost_per_day
- high_cost_pressure = storage_cost_pressure > cost_pressure_threshold
- recovery_streak_days (implemented)

This layer must not contain pricing logic. It produces structured diagnostics only.

Layer 2 - Phase Engine (time + pressure escalation)
This layer converts diagnostics into a phase. It does not decide price directly.
Phase triggers are based on days_under_new_strategy, not historical days_since_last_sale.

Strategy activation rule
- initial_phase = Phase 1 (Competitive Bias) on Day 1 of governance activation
- Do not start at Phase 0 on activation

Phase evaluation order (mandatory execution order)
1. If current_stock_units == 0 -> Freeze phase -> STOP
2. If in_grace_period == TRUE -> Escalation disabled
3. Check market-impossible fast track
4. Evaluate time-based trigger
5. If previous_price_gap_large == TRUE and days_under_new_strategy < competitive_test_window, lock in Phase 1
6. Apply inventory-pressure acceleration (+1 phase when allowed by guard rules)
7. Cap at Phase 4
8. Apply phase lock (no downgrade before minimum_days_in_phase)
9. Evaluate recovery downgrade

Phase definitions
- Phase 0 - Normal Optimisation
- Phase 1 - Competitive Bias
- Phase 2 - Margin Compression
- Phase 3 - Controlled Exit
- Phase 4 - Liquidation

Global constants (v1.2)
- grace_period_days = 14
- phase_1_trigger_days = 21
- phase_2_trigger_days = 35
- phase_3_trigger_days = 60
- phase_4_trigger_days = 90
- minimum_days_in_phase = 14
- below_floor_sustain_days = 14
- phase_4_manual_review_days = 30
- competitive_test_window = 14
- velocity_threshold = 2 units per 14 days
- recovery_velocity_threshold = 4 units per 14 days

Base escalation rules
Phase may escalate only if all are true:
- NOT in_grace_period
- days_under_new_strategy >= trigger_for_next_phase
- low_velocity = TRUE
- current_stock_units > 0

Additional structural rules (required)
1) Market-impossible fast track
If:
- below_floor_market = TRUE
- sustained for at least below_floor_sustain_days
Then:
- skip directly to at least Phase 3 (Controlled Exit)

2) Inventory-pressure acceleration
If high_cost_pressure = TRUE, accelerate escalation by one phase under phase-engine escalation constraints.

3) Phase 4 hard stop
If:
- current phase = 4
- days_in_current_phase > phase_4_manual_review_days
- no improvement (velocity and/or margin trend)
Then:
- flag SKU for manual intervention

4) Competitive-test protection (before escalation beyond Phase 1)
If:
- previous_price_gap_large = TRUE
- days_under_new_strategy < competitive_test_window
Then:
- lock in Phase 1

Safety rules
- Phase cannot escalate during grace period.
- Grace period blocks fast-track and acceleration upward moves.
- Phase cannot escalate while out of stock.

Phase lock rule
When entering a phase, days_in_current_phase must reach minimum_days_in_phase before any downgrade is allowed.

Recovery rule (no single-sale reset)
Phase may downgrade only if:
- rolling_14d_units >= recovery_velocity_threshold
- sustained for at least 14 days (tracked by `recovery_streak_days`)

Single sales do not reset phase.

Downgrade is stepwise:
- phase = max(phase - 1, 0)

No instant return to Phase 0.

Layer 3 - Pricing Behaviour by Phase
This layer consumes phase.

Phase 0 - Normal Optimisation
- Profit argmax
- Full ROI discipline
- Standard ladder
- Hard floor respected
- Phase 0 minimum ROI unchanged (10%)

Phase 1 - Competitive Bias (implemented)
- Dynamic undercut bias:
  - `undercut_bias = max(0.05, rival_price * 0.003)`
- Minimum ROI reduced versus Phase 0:
  - Phase 1 floor around 7% ROI
- No step-down cap:
  - direct move to `max(phase1_floor_price, rival_price - undercut_bias)`
- Hard floor and non-negative ROI protections remain enforced
- Floor-protected direct targeting (no artificial throttling)

Phase 2 - Margin Compression
- Soft floor reduced
- Accept 0-5% ROI
- Prioritise turnover
- No restocking allowed

Phase 3 - Controlled Exit
- Allow small controlled loss (-2% to -5%)
- Undercut aggressively within rules
- Capital recovery priority
- Restock blocked

Phase 4 - Liquidation
- Price to clear
- Hard floor redefined as capital-recovery floor
- Consider removal, bundle, or off-Amazon disposal
- Supplier flagged for review
- Hard stop: manual intervention if >30 days with no improvement

2. Restocking Governance
If SKU is in:
- Phase 2 or higher -> No restocking
- Phase 3 or 4 -> Block purchasing entirely

Dead stock must not reorder.

3. Grace-Period Protection
Newly restocked items must not escalate prematurely.

Rule:
if days_since_last_restock < grace_period_days:
    phase_escalation_disabled = TRUE

Prevents panic-selling new inventory.

4. Out-of-Stock Protection
If current_stock_units == 0, then:
- Freeze phase
- Freeze phase transitions
- Do not escalate

Out-of-stock must not trigger exit behaviour.

5. Maintenance and Governance
This is not a set-and-forget system.

Monthly review export per SKU
- avg_days_in_phase
- phase_transitions
- profit_per_sku
- units_sold
- storage_cost

Look for:
- SKUs stuck in Phase 2+ for extended periods
- SKUs escalating too quickly
- SKUs never escalating despite stagnation

Adjust thresholds quarterly, not daily.

6. What Is Correct in This Design
- Grace period
- Rolling-velocity recovery requirement
- No single-sale reset
- Stepwise downgrade
- Restock block in Phase 2+
- Out-of-stock freeze
- Unified write gate contract between decision output and sheet status

7. Scope Boundary (Strategic)
Current scope is a stock-governance engine with live-write gating controls.

Not connected yet to:
- Portfolio governor
- Capital allocation
- Supplier scoring

8. Expected Outcome
This policy system should:
- Reduce stagnation
- Reduce emotional decisions
- Reduce long-term storage bleed

This policy system will not:
- Magically fix bad buys
- Replace sourcing judgement

9. Future Enhancements (not v1.2)
Do not implement initially:
- Profit-per-day decay modelling
- Dynamic threshold learning
- Advanced elasticity modelling
- AI-driven exit predictions

Build v1.2 stable, observe, then iterate.

10. Implemented Architecture Notes

Single write-gate source of truth
- Write eligibility is centralized in `evaluate_live_write_gate()`.
- Writer path and dashboard/sheet status consume the same effective gate result.
- Prevents "writer says WRITE, dashboard says READ" drift.

Environment flags (runtime control)
- `H_PHASE_ENGINE_ENABLED`
- `H_PHASE_ENGINE_BEHAVIOR`
- `H_PHASE_ENGINE_LIVE_WRITES`
- Optional shadow and cohort controls remain runtime-configurable.

Contract tests
- Contract runner: `python scripts/tests/run_contracts.py`
- Includes write-gate consistency checks between writer eligibility and sheet status.
- Must pass before enabling or expanding live writes.

11. System Guardrails

- Single source of truth for write eligibility (`evaluate_live_write_gate()`).
- Contract test for write-gate consistency across writer and sheet outputs.
- Health checklist enforcement remains active to catch runtime/config drift.
- Legacy/stale gate checks must not override effective phase-engine write flags.


17. v1.3 Build Notes (Implemented)

1) Global go-live clock
- Env: `H_STRATEGY_GO_LIVE_UTC`.
- If set, `days_under_new_strategy` is anchored to go-live for all non-excluded SKUs.
- Conditional reseed only when stored `strategy_start_date < go-live`.
- Reseed sets `phase = 1` and `phase_entered_utc = go-live`.
- Reseed reason is `PHASE_GO_LIVE_RESEED_APPLIED`.
- No full history wipe.

2) Inbound-aware inventory activation
- `inventory_active = (available > 0) OR (inbound_total > 0)`.
- `inbound_total = inbound_working + inbound_shipped + inbound_receiving`.
- When `available = 0` and `inbound_total > 0`:
- state/probe is `INBOUND_DISCOVERY`.
- Reason includes `INBOUND_PRICE_DISCOVERY`.
- `target_price = min(competitor_price, ceiling_price)`.
- SKU is not excluded as OOS and remains in monitoring.

3) Stock source priority fix (prevents false `STOCK_UNKNOWN`)
- Per-SKU stock resolution order:
- `out/inventory_summaries.csv`
- latest `out/inventory_snapshot_YYYY-MM-DD.csv`
- `out/parking/stock_snapshot_latest.csv`
- Mark `STOCK_UNKNOWN` only when SKU is missing from all three sources.

4) Scan-state writeback merge
- On `phase1_sku_scan_state.json` write, re-read on-disk state and merge `last_scan_utc` by newest timestamp.
- Prevents last-writer-wins timestamp loss.

5) Dashboard publishing mode
- H130 supports fixed-tab publishing via `--view-tab`.
- H loop uses env `H_PHASE1_OBSERVATION_VIEW_TAB` (default `PRICING_DASHBOARD`).
- Dated tabs are not required for normal operation.

6) Dashboard visibility
- `PRICING_DASHBOARD` includes a `PROBE` column.
- `PROBE = "INBOUND"` only when `available = 0 AND inbound_total > 0`.
- Dashboard row inclusion now includes inbound-active SKUs:
- `(available > 0) OR (inbound_total > 0)`.

7) Confirmed non-issue (diagnostic note)
- SKU key mismatch check found no mismatch:
- H `sku` matches inventory `seller_sku`.
- ASIN values also match.
- Inbound totals may be zero at times because upstream inventory feeds may not reflect inbound immediately.
- This is a data freshness issue, not a key-join issue.


12. Suppressed Buy Box Handling (Planned)

Current behavior (implemented)
- When Buy Box/outcome is suppressed or unknown (`buy_box_missing` / unknown outcome), SKU is held.
- Decision state remains HOLD and no aggressive price action is taken.

Planned enhancement
- Add fallback competitor-price logic when Buy Box is suppressed but rival evidence exists.
- Fallback should remain floor-protected and respect phase, ROI, and guardrails.
- This is planned, not enabled in current v1.2 behavior.

13. Removed Behaviors (Do Not Reintroduce)

- Phase 1 step-down caps.
- Artificial daily price move limits for Phase 1 target descent.
- Any throttles that block direct floor-protected move to computed Phase 1 target.

14. Known Strategic Gaps

- Suppressed Buy Box policy still conservative (hold-first).
- Slow-bleed trap risk around ~2 units / 14 days needs stronger policy handling.
- `inventory_risk` is computed but not fully exploited in decision pressure policy.

15. Operational Rules

- B and H loops run from scheduler in normal operation.
- Use one-shot maintenance runs for safe refresh and diagnostics without starting continuous loops.
- Before enabling live writes:
  - verify lock/maintenance states,
  - verify write-gate config,
  - run `python scripts/tests/run_contracts.py`,
  - confirm health checklist is clean for relevant flow gates.

16. Audit Contradictions - v1.2 Status

Resolved in implementation
- `below_floor_market_streak_days` implemented.
- `recovery_streak_days` implemented.
- Phase lock behavior clarified and enforced.
- Grace period explicitly blocks fast-track upward moves.

Remaining strategic gaps
- Suppressed Buy Box fallback policy still pending.
- Slow-bleed boundary behavior remains a policy risk.
- Inventory risk acceleration can be expanded further.

18. Do not revert (v1.3)

- Hard rules:
- Global go-live anchoring (`H_STRATEGY_GO_LIVE_UTC`) and conditional Phase 1 reseed (`PHASE_GO_LIVE_RESEED_APPLIED`) without full history wipe.
- Inbound activation and discovery path: inbound-active inventory, `INBOUND_DISCOVERY`, `INBOUND_PRICE_DISCOVERY`, and floor-safe discovery targeting.
- Stock source priority order (`inventory_summaries` -> dated `inventory_snapshot` -> `stock_snapshot_latest`) with `STOCK_UNKNOWN` only after all three miss.
- Scan-state on-write merge for `last_scan_utc` using newest timestamp.
- Fixed-tab dashboard publishing via `--view-tab` and `H_PHASE1_OBSERVATION_VIEW_TAB` defaulting to `PRICING_DASHBOARD`.
- `PROBE` column behavior and inbound-active row inclusion on `PRICING_DASHBOARD`.

