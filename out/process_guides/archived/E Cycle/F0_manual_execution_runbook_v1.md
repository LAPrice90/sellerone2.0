# F0 Manual Execution Runbook v1 (You are the Pricing Manager)

This runbook is for the manual phase where:
- E produces decision-ready outputs.
- H provides listing history context.
- You execute decisions (F0) for 5-10 SKUs only.
- PPP is used as the actuator when possible.

---

## 0) The hard rules (do not break these)

- Do not fight on every SKU. Only act on the training set.
- Stock posture overrides everything:
  - If stock is TIGHT/CRITICAL, no aggression.
- Never chase a competitor downward indefinitely.
- Every manual price action must be logged the same day.
- If the data is missing or confusing, use HIBERNATE and log why.

---

## 1) Daily sequence

### Step 1 - Run E cycle

**User Task**
- Run the E scripts in order (local build first).
- Confirm the run produced:
  - sku_sales_velocity.csv
  - sku_restock_signals.csv
  - sku_performance_summary.csv
  - e_decision_log.csv
  - e_run_log.jsonl

Evidence:
- Record row counts (or screenshot) for each output.
- Spot check 3 SKUs: fast, slow, non-UK.

### Step 2 - Run H snapshot (training set only)

**User Task**
- Capture a listing snapshot for each training SKU:
  - our price
  - buy box price
  - lowest offer prices if available
  - offer counts
  - BSR trend if available

Write the snapshot to:
- out/listing_offer_snapshot_YYYY-MM-DD.csv
And append to:
- out/listing_offer_history.csv

If you cannot automate H yet:
- export a CSV manually (from your tool) and store it with the same schema.
- set source=MANUAL_TOOL.

### Step 3 - Build today's "F0 board"

Your board is a short table of the 5-10 SKUs:
- sku
- days_of_cover
- buy_box_gap (our_price - buy_box_price)
- flags (missing_cogs, long_oos, etc.)
- current_token_cost_gbp (from E)
- break_even_price_gbp (from E)
- expected_refund_cost_per_unit_gbp (from E)
- roi_at_our_price_pct (from E)
- roi_at_buy_box_price_pct (from E)

You can do this in Sheets or locally in Excel.

### Step 4 - Decide a state per SKU (F0)

For each training SKU, follow this order:

1) Stock gate (hard stop)
- If days_of_cover is low OR inbound is far away:
  - choose DEFENSIVE or HIBERNATE
  - do not PROBE/PRESSURE/STARVE

2) Value check
- If velocity is low for this SKU:
  - do not fight
  - choose COOPERATE or DEFENSIVE

3) Margin check (forward ROI from E)
- If current_token_cost_gbp is missing:
  - choose HIBERNATE (or LIQUIDATE if exit is the plan)
  - do not fight
- If expected_refund_cost_per_unit_gbp is missing:
  - choose HIBERNATE
  - do not fight until refund signal is restored
- If roi_at_our_price_pct or roi_at_buy_box_price_pct is below your acceptable floor:
  - choose DEFENSIVE or LIQUIDATE
  - do not fight

4) Competition reality check (from H)
- If buy box is consistently below your floor:
  - mark UNSAVABLE for now (HIBERNATE)
- If fulfilment disadvantage exists (example: hazmat next-day issue):
  - you may need a larger discount than PPP can express
  - that is allowed only if value and stock gates pass

5) Choose the state (one of)
- COOPERATE
- PROBE
- PRESSURE
- STARVE
- DEFENSIVE
- LIQUIDATE
- HIBERNATE

Time-box aggressive states:
- PROBE: 1-2 days
- PRESSURE: 3-7 days
- STARVE: 7-14 days

(These are starting defaults, not permanent laws.)

### Step 5 - Execute using PPP or manual override

Execution rules:
- Prefer PPP if it can express the behaviour with min/max and strategy.
- If PPP cannot express the needed discount (example: you need -30p but PPP only does -5p):
  - set the price manually
  - log the reason code: PPP_LIMITATION
  - set a review time (example: 24h)

### Step 6 - Log the decision (must be done same day)

Write one log row per SKU per day:
- state chosen
- target price/band
- action taken (PPP strategy or manual)
- reason codes
- notes (short)

Use the template:
- out/f0_decision_log.csv

### Step 7 - Outcome check (next day)

For each SKU, record:
- units sold (or change in sales)
- buy box change (if known)
- price movement
- any new competitor behaviour

Log outcomes in:
- out/f0_outcome_log.csv
(or additional columns in the same log if you keep it simple)

---

## 2) How to handle common scenarios (manual rules)

### Scenario A - Stock is low, inbound is weeks away
Goal: preserve box position if possible, but do not trigger a sell-out.

Action:
- DEFENSIVE
- raise price slightly (within max) if demand is strong
- avoid aggressive undercutting
- log: STOCK_TIGHT

### Scenario B - High value SKU, competitor undercuts constantly
Goal: test if they are a dumb repricer or weak stock.

Action:
- PROBE for 1-2 days
- hold price steady after a move (do not thrash)
- if they mirror instantly, consider STARVE (not deeper undercut)
- log: AGGRESSIVE_SELLER|PROBE

### Scenario C - Fulfilment disadvantage (hazmat next-day / Prime speed mismatch)
Goal: compensate for delivery disadvantage with a controlled price delta.

Action:
- Only if value + stock gates pass
- Manual price override may be required
- Record "required_discount_to_win" in notes
- log: FULFILMENT_DISADVANTAGE|PPP_LIMITATION

### Scenario D - Low margin, high volume commodity
Goal: do not burn capital.

Action:
- COOPERATE or DEFENSIVE
- accept fewer sales when price wars start
- only LIQUIDATE if exit is intentional
- log: LOW_VALUE

---

## 3) Weekly review (turn outcomes into rules)

Once per week:
- review the decision log and outcomes
- list:
  - top 5 scenario patterns
  - which actions worked
  - where PPP failed
  - where data was missing

Promote repeat patterns into:
- Strategy Rulebook v1 (update)
- F automation candidates (future)

End.
