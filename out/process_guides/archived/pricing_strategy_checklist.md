# Pricing Strategy Checklist (Execution)

## Phase 1 - Guardrails
- Floors/ceilings set for all SKUs.
- Max step and max/day limits set.
- Cooldown timers set.
- Kill switch tested.
- Shadow mode enabled (no updates).

## Phase 2 - State machine
- SKU state assigned (Acquire/Hold/Harvest/Cooldown/Floor-Hold/Clearance/Exit).
- State transitions logged.
- No pricing changes when COGS missing.

## Phase 3 - Inputs
- E cycle outputs exist (ROI + velocity).
- C cycle storage fees available (if month is ready).
- B cycle Order_Master + token COGS present.

## Phase 4 - Shadow run
- Run for 3-7 days.
- Review daily summary and alerts.
- Fix any false alerts or missing inputs.

## Phase 5 - Live switch
- Enable updates for a small SKU set.
- Watch price change counts.
- Expand only if stable.

## Success criteria
- No FAIL alerts.
- Price changes per SKU remain under max/day.
- ROI-negative SKUs are flagged, not chased.

