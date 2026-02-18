# Pricing Strategy Rulebook (Draft)

## Purpose
This rulebook defines the pricing engine behavior so it makes money safely and does not thrash prices.

## Non-negotiable guardrails (always on)
- Hard floor and ceiling per SKU.
- Max change per step (default: max 2% or GBP 0.30).
- Max price updates per SKU per 24h (default: 6).
- Cooldown after price change and after Buy Box flip.
- Kill switch that stops all price updates immediately.
- Shadow mode (log-only) before any live updates.

## Required state machine
Each SKU must be in one of these states:
- Acquire: try to win or regain Buy Box.
- Hold: keep price steady; do not undercut.
- Harvest: profit climb in small steps while Buy Box is stable.
- Cooldown: no changes for a set time.
- Floor-Hold: at min price; stop fighting.
- Clearance: aged stock; price down within guardrails.
- Exit/Unsavable: do not compete; review list.

## When not to chase Buy Box
- If Buy Box price is below floor -> Floor-Hold.
- If volatility or manipulation suspected -> Cooldown.
- If COGS missing -> Hold (no pricing changes).
- If inventory risk is low (few days of cover) -> Hold or Harvest.

## UK-specific rules
- Use landed price for comparisons (price + shipping).
- Allow FBA premium over FBM (do not auto-match FBM).
- Do not climb into Buy Box suppression.

## Profit climbing (safe only)
- Only climb when Buy Box is held for a stable window.
- Small bounded steps.
- Store last-known-good price; revert if BB lost.

## Required outputs (daily)
- Per SKU state
- Price change count (24h)
- BB status
- ROI tier
- Alerts: floor-hold, price war, missing COGS, BB suppressed

## Inputs required
- E cycle: ROI + velocity + restock signals
- C cycle: storage fees (monthly + long-term)
- B cycle: Order_Master + token COGS

## Deployment order
- Shadow mode only
- Review logs for 3-7 days
- Enable live updates with caps

