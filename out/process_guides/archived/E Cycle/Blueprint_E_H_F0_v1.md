# Blueprint v1 - E (Decision) + H (History) + F0 (Manual Pricing Manager)

This blueprint assumes:
- E is built and runs daily.
- You (the operator) are Level F0 for now: you make pricing decisions manually, using E outputs and offer history.
- Profit Protector Pro (PPP) is used as the "actuator" when it can express the action. Manual price overrides are allowed when PPP cannot.

This document is written to be pasted into a fresh Codex chat as the operating plan.
Rule: Do not implement anything unless I explicitly say PROCEED.

---

## 0) Goals

Business goals:
- Maximize profit per day (value, not volume).
- Pick battles: only fight on SKUs where the prize is worth the cost.
- Prevent "death by 300 listings": low value SKUs must not drag capital/time into price wars.
- Use stock position and inbound timing as hard constraints on aggressiveness.
- Build a system that can be tuned with evidence (logs), not vibes.

System goals:
- E stays read-only: it produces facts and classifications (no pricing writes).
- F starts as manual (F0), then becomes semi-automated (F1 suggestions), then automated (F2) for a small subset.
- H stores daily offer/price/rank snapshots so decisions are history-aware.
- Every decision has a reason trail so we can improve without re-arguing old cases.

Compliance goals:
- Do not scrape sites or violate tool terms.
- Respect Amazon fair pricing policies and marketplace rules.
- Avoid behaviour that could be unlawful in your jurisdiction (example: collusion). This system is for competitive pricing based on your own costs and observed market conditions.

---

## 1) Roles and responsibility split

E (Decision layer):
- Reads Order_Master + inventory + token COGS + FX.
- Outputs: velocity, stock posture, projected ROI bounds, restock signals, and decision logs.
- Any realized ROI is reporting only and must not be used for decisions.

H (History layer):
- Captures "what the listing looked like" at a point in time.
- Outputs: daily offer snapshots and an append-only history file.
- Optionally backfills history from BuyBotPro/Keepa exports (if available and allowed).

F0 (You, manual pricing manager):
- Chooses a pricing posture (state) per SKU for a small training set.
- Sets PPP strategy or manual price.
- Logs actions and outcomes.

PPP (Actuator):
- Executes price changes within its constraints.
- Does not decide strategy.

---

## 2) Data flow (daily)

1) Run A + B cycles (health gate must be OK).
2) Run E cycle.
3) Run H snapshot (for the training SKUs first).
4) Review E + H for the training set (5-10 SKUs).
5) Execute F0 decisions using PPP/manual price.
6) Record decisions and outcomes.

---

## 3) The minimum outputs E must provide for F0

E must output per SKU (at least for the training set):
- v7, v30, v90 (units/day) and a blended velocity placeholder
- stock available, inbound (if known), days_of_cover
- current_token_cost_gbp
- break_even_price_gbp
- expected_refund_cost_per_unit_gbp
- roi_at_our_price_pct
- roi_at_buy_box_price_pct
- flags: missing_cogs, fx_missing, sparse_sales, windows_diverge, long_oos, gap_risk
- needs_review + reason_codes

Projected ROI definition (decision use):
- `current_token_cost_gbp` must already include inbound shipment allocation.
- `expected_refund_cost_per_unit_gbp` is included in projected ROI cost.
- Formula: `projected_profit_per_unit = price_point_gbp - expected_fees_gbp - current_token_cost_gbp - expected_refund_cost_per_unit_gbp`.
- Formula: `projected_roi_pct = (projected_profit_per_unit / current_token_cost_gbp) * 100`.
- Keep projected ROI separate from realized ROI reporting.

If E cannot compute a field yet, it must:
- output it as blank
- set needs_review=yes
- add a reason code like MISSING_SIGNAL_<NAME>

---

## 4) The minimum outputs H must provide

H must capture per SKU per snapshot:
- timestamp_utc
- marketplace
- sku, asin
- our_price (and optionally our min/max)
- buy_box_price
- buy_box_channel (FBA/FBM/Amazon/Unknown if available)
- lowest_fba_price, lowest_fbm_price (if available)
- offer counts (FBA and FBM if available)
- BSR + category (if available)
- notes/source field (SPAPI/BBP/Manual - emergency one-off only)

H must store:
- a daily snapshot file (overwritable for the day)
- an append-only history file (or a durable DB table)

---

## 5) The operating concept: do I act today, stock-gated behaviour

Key principles:
- E answers one question: "What do I do today?"
- Stock gates behaviour: if stock is tight or inbound is far away, you do not escalate.
- Pick battles: only a small number of SKUs should ever be in "pressure" states.

---

## 6) SKU states (postures) for F0

These are human-readable states you choose for each training SKU.

- COOPERATE
  - Compete politely; do not chase deep undercuts.
  - Prioritize stability and avoid unnecessary price wars.

- PROBE
  - Small controlled price moves to measure competitor reaction.
  - Time-boxed. Used to learn.

- PRESSURE
  - Hold price at an "attack band" (still within your allowed profit floor).
  - Do not chase endlessly lower.

- STARVE
  - Hold steady at a painful-but-viable level and wait for competitors to sell out.
  - Requires strong stock endurance and demand confidence.

- DEFENSIVE
  - Protect price and accept fewer sales while competitors burn.
  - Useful when you lack fulfilment advantages or stock depth.

- LIQUIDATE
  - Exit inventory on purpose (capital recovery).
  - No fighting; price to sell with a defined end date.

- HIBERNATE
  - Temporarily disengage due to missing data, tight stock, or unstable conditions.

Important:
- These states are not "forever". They are time-boxed behaviours with review points.

---

## 7) Battle qualification (who is allowed to fight)

A SKU is allowed to enter PRESSURE/STARVE only if all are true:
- Stock: days_of_cover is comfortably above lead time + buffer + expected fight duration.
- Confidence: the decision is not dominated by missing/estimated signals.
- Margin check: projected ROI fields from E are above your allowed floor.

If any fail:
- The SKU is not allowed to fight.
- Use COOPERATE/DEFENSIVE/HIBERNATE/LIQUIDATE instead.

---

## 8) Training loop (how we move from F0 to F1)

For 5-10 SKUs:
- Run daily for 2-4 weeks (or until you have enough examples).
- Each manual decision must be logged with:
  - what E said
  - what H showed
  - what you did
  - what happened

Promotion rule:
- If the same pattern repeats 3+ times and you can write it as a clear rule, it becomes a candidate for F automation.

---

## 9) What to paste into ChatGPT for decision support

When you want help choosing a state, paste a small snapshot for a SKU:

E snapshot (single SKU):
- sku
- v7, v30, v90, blended (if present)
- stock_available, inbound, days_of_cover
- current_token_cost_gbp
- break_even_price_gbp
- expected_refund_cost_per_unit_gbp
- roi_at_our_price_pct
- roi_at_buy_box_price_pct
- flags/reason_codes

H snapshot (latest):
- our_price
- buy_box_price
- lowest_fba_price/lowest_fbm_price
- offer counts
- bsr (optional)
- any fulfilment disadvantage notes (example: hazmat next-day limitation)

And tell me:
- your goal for that SKU (hold margin vs clear stock vs win box)

---

## 10) Backfilling history from BuyBotPro (optional)

If BuyBotPro (or Keepa) allows exporting price/rank history:
- backfill ONLY for the training SKUs at first (avoid complexity)
- store source=BBP and keep it separate from SP-API snapshots
- do not overwrite real daily snapshots with backfill data
- use backfill to set expectations (typical buy box range, typical rank), not as absolute truth

---

## 11) Definition of done for this phase (F0)

You are "ready to automate F" when:
- E runs daily with stable schemas and decision logs.
- H captures daily snapshots for the training SKUs.
- You have at least 30-50 logged decisions/outcomes across the training set.
- You can list your top 5 repeated scenarios with clear rules.
- You can identify 1-2 "strategic assets" that justify deeper logic (like your glue SKU).

End.
