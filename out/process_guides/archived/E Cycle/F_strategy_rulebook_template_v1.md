# Strategy Rulebook Template v1 (for F)

Purpose:
- This is the owner-controlled rulebook that defines how pricing postures work.
- Start conservative. Only tighten rules after real examples and logs.

How to use:
- Do not let Codex invent rules. Update this file first, then implement.
- Version this file. When behaviour changes, bump the version and record why.

---

## 0) Owner settings (fill these in)

These are starting placeholders. Tune after real samples.

### ROI floors (from projected ROI fields)
- ROI_FLOOR_NORMAL_PCT =
- ROI_FLOOR_ATTACK_PCT =
- ROI_TARGET_NORMAL_PCT =

### Stock gates
- STOCK_TIGHT_DAYS_OF_COVER =
- STOCK_CRITICAL_DAYS_OF_COVER =
- SAFETY_BUFFER_DAYS =

### Battle selection (pick fights)
- VELOCITY_FIGHT_THRESHOLD_UNITS_PER_DAY =
- STRATEGIC_ASSET_VELOCITY_THRESHOLD_UNITS_PER_DAY =

### Time boxes (default)
- PROBE_MAX_DAYS = 2
- PRESSURE_MAX_DAYS = 7
- STARVE_MAX_DAYS = 14

---

## 1) Definitions (make the maths explicit)

- Velocity windows:
  - v7, v30, v90 = units/day over those windows
  - v_blended = weighted mix (owner chosen)

- Projected ROI (from E for decisions):
  - current_token_cost_gbp includes inbound shipment allocation
  - expected_refund_cost_per_unit_gbp is included as a projected cost
  - roi_at_our_price_pct = projected ROI at our current price
  - roi_at_buy_box_price_pct = projected ROI at buy box price
  - do not use historical ROI for decisions

- Stock posture:
  - SURPLUS: days_of_cover >= lead_time + buffer + 30
  - BALANCED: days_of_cover >= lead_time + buffer + 14
  - TIGHT: days_of_cover < lead_time + buffer + 14
  - CRITICAL: days_of_cover < lead_time + buffer + 7

(Exact numbers are owner settings.)

---

## 2) State machine (pricing postures)

Each SKU must be in exactly one state at any time.

### 2.1 COOPERATE
Intent:
- Keep sales flowing without chasing deep undercuts.
Allowed actions:
- Match buy box within a small delta if ROI target is met.
- Raise price when you own the box and competitors are stable.
Forbidden:
- Deep undercutting below ROI_FLOOR_NORMAL_PCT.

### 2.2 DEFENSIVE
Intent:
- Protect margin when conditions are unstable (stock tight, noisy competition).
Allowed actions:
- Sit above buy box if needed.
- Reduce repricing frequency to avoid thrash.
Forbidden:
- Entering PRESSURE/STARVE.

### 2.3 PROBE
Intent:
- Learn competitor reaction speed and depth with small controlled moves.
Allowed actions:
- Small price dips (bounded by ROI_FLOOR_ATTACK_PCT).
- Hold price steady after a move to observe.
Exit:
- If competitor mirrors instantly -> candidate for STARVE (not deeper undercut).
- If competitor does not react -> return to COOPERATE at better margin.
Time box:
- PROBE_MAX_DAYS.

### 2.4 PRESSURE
Intent:
- Sustain a low-but-viable price band to squeeze weak sellers.
Allowed actions:
- Hold price at "attack band" (not below ROI_FLOOR_ATTACK_PCT).
- No frequent micro-adjustments.
Forbidden:
- Chasing below attack floor.
Exit:
- If competitor undercuts below attack floor -> disengage (DEFENSIVE).
Time box:
- PRESSURE_MAX_DAYS.

### 2.5 STARVE
Intent:
- Hold steady and let competitors sell out.
Preconditions:
- Stock posture not TIGHT/CRITICAL.
- Value_velocity above fight threshold.
Allowed actions:
- Hold price at painful-but-viable level.
- Raise price after competitors disappear.
Forbidden:
- Endless price chasing.
Time box:
- STARVE_MAX_DAYS.

### 2.6 LIQUIDATE
Intent:
- Exit inventory intentionally (capital recovery).
Allowed actions:
- Set exit price and keep it stable.
- Do not engage in wars.
Exit:
- When stock reaches target level (example: zero) or date reached.

### 2.7 HIBERNATE
Intent:
- Pause automation when data is missing or conditions are not safe.
Triggers:
- missing_cogs
- fx_missing
- projected ROI missing
- expected refund cost missing
- listing anomalies
Exit:
- When data is fixed and confidence returns.

---

## 3) Battle qualification rules (who is allowed to fight)

A SKU is allowed to enter PRESSURE/STARVE only if all are true:
- v_blended >= VELOCITY_FIGHT_THRESHOLD_UNITS_PER_DAY
- stock posture not TIGHT/CRITICAL
- roi_at_our_price_pct >= ROI_FLOOR_ATTACK_PCT or roi_at_buy_box_price_pct >= ROI_FLOOR_ATTACK_PCT
- confidence not LOW

Otherwise:
- COOPERATE/DEFENSIVE/HIBERNATE/LIQUIDATE only

---

## 4) Special scenario rules (write only after real examples)

Add rules here as they are proven by logs:
- Fulfilment disadvantage (hazmat next-day mismatch)
- Amazon Retail present below your floor
- Suppressed buy box / listing issue
- Competitor stock appears low (inferred)
- Seasonal shifts

Each rule must specify:
- trigger signals
- allowed actions
- stop conditions
- reason codes

---

## 5) Logging requirement (non-negotiable)

Every state change must write:
- from_state -> to_state
- reason_codes
- key inputs used (v_blended, days_of_cover, roi_at_our_price_pct, roi_at_buy_box_price_pct)

Reason codes must be stable strings.

End.
