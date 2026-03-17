Repricing Phase Engine Blueprint (v1.1)

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
- previous_price_gap_large = prior_price_gap_pct > price_gap_large_threshold
- low_velocity = rolling_14d_units < velocity_threshold
- in_grace_period = days_since_last_restock < grace_period_days
- inventory_risk = current_stock_units > stock_risk_threshold
- storage_cost_pressure = current_stock_units * estimated_storage_cost_per_day
- high_cost_pressure = storage_cost_pressure > cost_pressure_threshold

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
6. Apply inventory-pressure acceleration (+1 phase)
7. Cap at Phase 4
8. Apply phase lock (no downgrade before minimum_days_in_phase)
9. Evaluate recovery downgrade

Phase definitions
- Phase 0 - Normal Optimisation
- Phase 1 - Competitive Bias
- Phase 2 - Margin Compression
- Phase 3 - Controlled Exit
- Phase 4 - Liquidation

Global constants (v1.1)
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

Rationale: do not spend 60+ days descending when the market is below hard floor from the start.
This fast track is structural and applies regardless of strategy_start_date.

2) Inventory-pressure acceleration
If high_cost_pressure = TRUE, accelerate escalation by one phase.

Implementation note:
- Evaluate normal phase from time-based trigger first.
- Then apply +1 phase acceleration when high_cost_pressure = TRUE.
- Cap at Phase 4.

Rationale: heavy inventory with meaningful storage bleed should decay faster than low-unit stock.

3) Phase 4 hard stop
If:
- current phase = 4
- days_in_current_phase > phase_4_manual_review_days
- no improvement (velocity and/or margin trend)
Then:
- flag SKU for manual intervention

Rationale: prevent open-ended zombie liquidation.

Phase 4 improvement definition (mechanical)
improvement = TRUE if either condition is met:
- rolling_14d_units >= velocity_threshold
- avg_margin_last_14d >= break_even

4) Competitive-test protection (before escalation beyond Phase 1)
If:
- previous_price_gap_large = TRUE
- days_under_new_strategy < competitive_test_window
Then:
- lock in Phase 1

Rationale: every SKU gets a fair competitive attempt window under the new strategy.

Safety rules
- Phase cannot escalate during grace period.
- Phase cannot escalate while out of stock.

Phase lock rule
When entering a phase, days_in_current_phase must reach minimum_days_in_phase before any downgrade is allowed.

Recovery rule (no single-sale reset)
Phase may downgrade only if:
- rolling_14d_units >= recovery_velocity_threshold
- sustained for at least 14 days

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

Phase 1 - Competitive Bias
- Slight undercut bias (-0.05 to -0.10)
- Maintain positive ROI
- Narrower profit band
- Encourage movement without damage

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
- Exit loss reference uses blended landed cost:
  exit_loss_reference = cost_per_unit (inbound + prep included)
  exit_floor_price = cost_per_unit * (1 - max_loss_pct)

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
- Freeze velocity decay
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

7. Scope Boundary (Strategic)
Current scope is a stock-governance engine.

Not connected yet to:
- Portfolio governor
- Capital allocation
- Supplier scoring

Future direction (not for v1.1 build):
- supplier_score decreases if SKUs hit Phase 3+

Do not add this in current implementation.

8. Expected Outcome
This policy system should:
- Reduce stagnation
- Reduce emotional decisions
- Reduce long-term storage bleed

This policy system will not:
- Magically fix bad buys
- Replace sourcing judgement

9. Future Enhancements (not v1.1)
Do not implement initially:
- Profit-per-day decay modelling
- Dynamic threshold learning
- Advanced elasticity modelling
- AI-driven exit predictions

Build v1.1 simple, observe for 30-60 days, then iterate.


RESEARCH UPDATES 

## Full structural contradiction audit (v1.1)

### Critical contradictions / “cannot be implemented as written” points

1. **“Sustained below-floor” requires state you do not define**
   You require: `below_floor_market = TRUE sustained for at least below_floor_sustain_days` to trigger the market-impossible fast track (≥ Phase 3). But Layer 1 does not define any variable that tracks a streak (e.g., `below_floor_market_streak_days`). Without that, “sustained” cannot be computed mechanically. 
   **Failure mode:** fast-track never triggers or triggers inconsistently depending on how a dev guesses “sustained.”
   **Minimal fix:** add `below_floor_market_streak_days` (increments daily while in-stock; resets to 0 if condition false; freezes while out of stock).

2. **Out-of-stock “freeze velocity decay” contradicts how rolling windows behave**
   You state: “Freeze phase” and “Freeze velocity decay” when `current_stock_units == 0`. But `rolling_14d_units` and `rolling_30d_units` will naturally decay over time if they’re computed as true rolling windows. Freezing phase does not automatically freeze velocity metrics unless you explicitly override them. 
   **Failure mode:** SKU goes OOS for weeks, comes back with `rolling_14d_units = 0`, and gets aggressively escalated after grace (even if it sold fine when in stock).
   **Minimal fix options (choose one):**

* Add `effective_rolling_14d_units` that is held constant while OOS, **or**
* Add `days_in_stock_under_strategy` and base triggers on that instead of raw `days_under_new_strategy`, **or**
* Accept decay but explicitly state: “we freeze phase only; velocity may decay; grace period is the protection.”

3. **“Hard floor” is used as a diagnostic constant, but you later redefine it by phase**
   Layer 1 treats `hard_floor_price` as a diagnostic input used by `below_floor_market = best_competitor_price < hard_floor_price`. Later, Phase 4 says “Hard floor redefined as capital-recovery floor.” That makes `hard_floor_price` phase-dependent, which breaks your layer separation and can introduce circular dependency (phase depends on below-floor; below-floor depends on phase). 
   **Failure mode:** ambiguous implementation; different engineers will implement different “floors,” producing different phases.
   **Minimal fix:** split floors explicitly:

* `profit_hard_floor_price` (constant profitability floor; used for the “market impossible” diagnosis)
* `phase_floor_price` (computed in Layer 3 per phase for pricing actions)

4. **Grace period vs fast-track and cost-pressure is undefined (and can violate the whole purpose)**
   Step 2: “If in_grace_period == TRUE -> Escalation disabled.”
   But Step 3 (fast-track) and Step 6 (inventory-pressure acceleration) occur afterward in the evaluation order. You do not explicitly state whether those are blocked during grace. 
   **Failure mode (worst):** newly restocked item gets fast-tracked to Phase 3/4 during grace if below-floor persists, contradicting “Prevents panic-selling new inventory.”
   **Minimal fix:** explicitly define:

* “During grace, **no upward phase movement of any kind** (including fast-track and cost-pressure). Only freeze/hold or downgrade via recovery is allowed.”

5. **Phase 4 manual review rule depends on inputs not defined in Layer 1**
   You define Phase 4 “improvement” using `avg_margin_last_14d` and `break_even`, but neither appears in the required Layer 1 inputs. 
   **Failure mode:** Phase 4 hard stop cannot be evaluated mechanically; manual review becomes subjective again.
   **Minimal fix:** add to Layer 1 required inputs:

* `avg_margin_last_14d` (or `avg_contribution_margin_last_14d`)
* `break_even_margin` (or `break_even_price` and derive margin)

---

### High-risk ambiguities (implementation will vary materially)

6. **Time trigger meaning is ambiguous given “start at Phase 1 Day 1”**
   You specify `initial_phase = Phase 1 on Day 1`, but also define `phase_1_trigger_days = 21`. Those conflict unless `phase_1_trigger_days` is only for Phase 0 → 1 re-escalation after a downgrade. 
   **Failure mode:** some implementations will “compute phase from days” (Phase 0 until day 21), others will force Phase 1 immediately. Outcomes differ.
   **Minimal fix:** redefine triggers as “eligibility to move beyond Phase 1” or rename:

* `phase_2_eligible_day = 35`, `phase_3_eligible_day = 60`, `phase_4_eligible_day = 90`
  and remove/ignore `phase_1_trigger_days` if always starting at Phase 1.

7. **Inventory-pressure acceleration is unclear: does it apply only when escalation is already happening?**
   Wording: “accelerate escalation by one phase,” evaluated after time-based trigger. But it’s not explicit whether +1 applies:

* **Only if** the SKU is already escalating upward today, or
* **Always** if `high_cost_pressure == TRUE` (which would push phases up even on day 1). 
  **Failure mode:** if applied “always,” you can escalate early and punish new stock; if applied “only on escalation,” it may not solve slow-bleed stagnation.
  **Minimal fix:** specify:
* “Apply +1 **only if** base logic would raise phase today (including fast-track).”

8. **Recovery “sustained for at least 14 days” is ambiguous and can make recovery extremely slow**
   Because recovery is based on a rolling 14-day number, “sustained for 14 days” can mean either:

* (A) “rolling_14d_units >= 4 once” (already a 14-day measure), or
* (B) “rolling_14d_units >= 4 on 14 consecutive daily evaluations.” 
  Those are wildly different. (B) can easily delay downgrades by weeks even after genuine recovery.
  **Minimal fix:** define explicitly as a streak counter: `recovery_streak_days`.

---

### Structural vulnerabilities (system can behave “correctly” but still fail the objective)

9. **The “2 units / 14d” boundary creates a “slow bleed trap”**
   You define `low_velocity = rolling_14d_units < 2`. That means at exactly **2 units per 14 days**, a SKU is **not** low velocity, and therefore can become stuck in its current phase (no escalation), while also failing recovery (needs ≥4). 
   **Failure mode:** a SKU with huge inventory selling exactly 2 units/14d may never be forced into exit phases by the engine. Capital stagnation and storage bleed continue indefinitely unless a human catches it in monthly review.
   **Minimal fix options:**

* Change low velocity to `<= 2`, **or**
* Use `inventory_risk` (already computed) to force escalation when stock is high, **or**
* Add a “days of cover” style metric (stock / velocity) as an additional trigger.

10. **You compute `inventory_risk` but never use it**
    Given your stated goals (“Prevent long-term capital stagnation”, “Avoid storage bleed”), ignoring `inventory_risk` removes the engine’s ability to treat 10 units vs 500 units differently at the same velocity. 
    **Failure mode:** identical phase outcomes for small and huge inventory despite very different risk.

---

## Phase transition truth table

This is the *mechanically implementable* decision table implied by your evaluation order, with the minimum extra state variables required for rules like “sustained” and “recovery sustained.” 

### Required state additions (to make your rules computable)

* `current_phase` (0–4)
* `days_in_current_phase`
* `below_floor_market_streak_days`
* `recovery_streak_days` (based on rolling_14d_units >= recovery_velocity_threshold)

### Trigger thresholds (as written)

* Phase 0 → 1 eligible when `days_under_new_strategy >= 21`
* Phase 1 → 2 eligible when `days_under_new_strategy >= 35`
* Phase 2 → 3 eligible when `days_under_new_strategy >= 60`
* Phase 3 → 4 eligible when `days_under_new_strategy >= 90` 
  (And **activation override**: on Day 1 set `current_phase = 1`.)

### Decision table (priority order)

**Legend:**
OOS = `current_stock_units == 0`
GRACE = `days_since_last_restock < 14`
LOW = `rolling_14d_units < 2`
REC = `rolling_14d_units >= 4`
REC_STREAK = `recovery_streak_days >= 14`
BF_STREAK = `below_floor_market_streak_days >= 14`
LOCK = `days_in_current_phase < 14`
HCP = `high_cost_pressure == TRUE`
PPG = `previous_price_gap_large == TRUE` and `days_under_new_strategy < 14`

1. **If OOS:**
   → `next_phase = current_phase` (freeze; do not escalate; do not downgrade)

2. **Else (in stock): set** `next_phase = current_phase`

3. **If GRACE:**
   → Upward moves disabled (no time escalation, no fast-track, no HCP acceleration)
   → Proceed only to recovery check (step 7)

4. **Market-impossible fast track:**
   If BF_STREAK:
   → `next_phase = max(next_phase, 3)`

5. **Time-based step escalation (one step):**
   If LOW and `days_under_new_strategy >= trigger_for_next_phase(current_phase)`
   → `next_phase = current_phase + 1`

6. **Competitive-test protection:**
   If `next_phase > 1` and PPG:
   → `next_phase = 1`

7. **Inventory-pressure acceleration (+1 only if already moving up today):**
   If HCP and `next_phase > current_phase`:
   → `next_phase = min(next_phase + 1, 4)`

8. **Cap:**
   → `next_phase = min(next_phase, 4)`

9. **Phase lock + recovery downgrade (one step):**
   If `next_phase == current_phase` (i.e., no upward change today) and not LOCK and REC_STREAK:
   → `next_phase = max(current_phase - 1, 0)`

10. **Phase 4 hard stop flag (not a phase change):**
    If `current_phase == 4` and `days_in_current_phase > 30` and not improved: flag for manual intervention 

This “truth table” resolves the biggest ambiguity: **HCP acceleration only applies when an upward move already happened** (otherwise you can accidentally climb phases just because inventory is expensive).

---

## Escalation timing stress test

All scenarios assume:

* Strategy starts Day 1 at Phase 1 (your activation rule). 
* Daily evaluation.
* “Step escalation” is one phase per day unless fast-track / HCP acceleration creates a bigger jump (as your rules allow). 

### Scenario A — Dead stock, market viable, no HCP, never in grace

Inputs:

* In stock continuously
* `rolling_14d_units = 0` (LOW = true)
* Not below-floor (no fast-track)
* HCP = false

**Expected phase timeline**

* Day 1–34: Phase 1
* Day 35: Phase 2 (eligible at 35 + LOW)
* Day 60: Phase 3 (eligible at 60 + LOW)
* Day 90: Phase 4 (eligible at 90 + LOW)
* Day 121: Phase 4 manual review condition becomes true (`>30` days in Phase 4) if no improvement 

**Stress result:** baseline path gives ~90 days to liquidation, ~121 days to forced manual attention.

---

### Scenario B — Market-impossible from Day 1 (below-floor sustained), normal cost

Inputs:

* In stock continuously
* `below_floor_market = TRUE` every day
* BF_STREAK reaches 14
* HCP = false
* If restock happened Day 0, GRACE blocks upward moves for Days 1–13

**Expected timeline (with grace blocking upward moves)**

* Day 1–13: Phase 1 (grace holds you)
* Day 14: Fast-track to Phase 3 (BF_STREAK hits 14; grace ended)
* Day 14+: Phase 3 pricing behavior starts immediately (controlled exit) 

**Stress result:** the engine exits “market impossible” SKUs by Day 14 instead of waiting to Day 60.

---

### Scenario C — Market-impossible + HCP (worst pressure)

Inputs:

* Same as Scenario B
* HCP = true

If HCP is applied as “+1 only when already moving up today” (recommended truth table above):

* Day 14: fast-track creates an upward move (to Phase 3), so HCP accelerates to **Phase 4** immediately (3 → 4)
* Day 45: Phase 4 manual review flag (Phase 4 for >30 days) if no improvement 

**Stress result:** this is your most aggressive auto-clear path: **Phase 4 by Day 14**, human attention by ~Day 45.

---

### Scenario D — Long out-of-stock period then restock (the “time jump” problem)

Inputs:

* Day 10: SKU goes OOS and stays OOS until Day 70
* Phase frozen during OOS (per your rule)
* Day 70: restock → GRACE Days 70–83
* Due to OOS, velocity is likely LOW on return unless you truly “freeze velocity decay” (which is currently ambiguous)

**What happens under the written rule set**

* Days 10–69: Phase frozen (likely Phase 1), but `days_under_new_strategy` continues climbing. 
* Days 70–83: grace blocks upward moves
* Day 84: grace ends; now `days_under_new_strategy ≈ 84` (≥60)

  * If LOW is true, escalation can happen rapidly:

    * Day 84: Phase 1 → Phase 2 (eligible at 35)
    * Day 85: Phase 2 → Phase 3 (eligible at 60)
    * Day 90: Phase 3 → Phase 4 (eligible at 90)

**Stress result:** a SKU can return from long OOS and be forced toward exit **almost immediately after grace**, even though it had no selling opportunity while out of stock. This is not a “logic bug,” but it is a major behavior risk for seasonal or supply-constrained SKUs.

**Hard recommendation (if you want fairness):** triggers should use `days_in_stock_under_strategy`, not raw `days_under_new_strategy`, or you need explicit wording that “OOS time counts.” 

---

### Scenario E — Slow bleed trap (the most dangerous path)

Inputs:

* Large inventory
* `rolling_14d_units = 2` exactly
* Not below-floor
* Not recovering (needs ≥4)
* HCP false or HCP only applied on upward moves

Because LOW is defined as `<2`, **LOW is false** at exactly 2. 
**Result:** no escalation and no downgrade. The SKU can sit in whatever phase it is currently in indefinitely.

This is the single biggest structural “capital stagnation” loophole in v1.1.

---

## Recovery lock stress test

Assumption (because your spec is ambiguous):
“Sustained for at least 14 days” = `rolling_14d_units >= 4` for **14 consecutive daily evaluations**, tracked by `recovery_streak_days`. 

### Case R1 — Strong recovery after entering Phase 3

* Day 60: SKU enters Phase 3
* From Day 60 onward: sells 1 unit/day continuously (very strong)

Key mechanics:

* `rolling_14d_units >= 4` becomes true quickly (after 4 sales), but downgrade requires:

  * `days_in_current_phase >= 14` (phase lock), AND
  * `recovery_streak_days >= 14` 

**Earliest downgrade estimates (with the “streak” interpretation):**

* Phase 3 → Phase 2: around Day 76
* Phase 2 → Phase 1: around Day 90
* Phase 1 → Phase 0: around Day 104

**Stress result:** even with strong, consistent recovery, returning to Phase 0 can take ~6 weeks after Phase 3 entry. This is consistent with your “no instant reset” intent, but it is slow.

### Case R2 — “Spiky” sales (the streak keeps resetting)

* SKU sells 4 units in one week, then nothing for a week, repeating.

Because the rolling window may dip below 4 frequently, `recovery_streak_days` resets and the SKU may **never** downgrade, even though it sometimes sells well.
**Stress result:** this prevents single spikes from “forgiving” a SKU, but it can also trap borderline-good SKUs in higher phases.

### Case R3 — Interaction with phase lock

Even if recovery is clearly happening, a SKU entering a new phase cannot downgrade for 14 days. That’s intended.
**But** if your system allows large upward jumps (fast-track or HCP), you can land in a harsher phase and be forced to sit there for at least 14 days before any downgrade is possible. 

---

## Capital bleed worst-case simulation

Because you did not supply actual storage costs, unit costs, or thresholds, this is a parametric “worst-case” simulation using your own variables (`current_stock_units`, `estimated_storage_cost_per_day`, and phase timing). 

### Definitions

Let:

* `U` = current_stock_units
* `c` = estimated_storage_cost_per_day (per unit)
* `T` = days until you either clear stock or force manual action
* `L` = landed cost per unit
* `loss_pct` = max controlled loss (Phase 3 says -2% to -5%) 

**Worst-case storage bleed (no sales):**
`storage_bleed = U * c * T`

**Worst-case exit loss (if you liquidate all units at a controlled loss):**
`exit_loss = U * L * loss_pct`

**Total worst-case (simplified):**
`total_bleed ≈ U*c*T + U*L*loss_pct`

### Worst-case “bounded” by your Phase 4 hard stop (only for LOW velocity path)

If a SKU is dead stock (LOW true) and keeps escalating to Phase 4:

* It reaches Phase 4 at Day 90 (Scenario A)
* It gets flagged for manual review after >30 days in Phase 4: ~Day 121 

So a bounded “time-to-human-attention” worst case is **~121 days** from Day 1.

Thus:

* `T ≈ 121` days (if nothing sells even in liquidation)

### Example numbers (hypothetical, for scale only)

Assume:

* U = 500 units
* c = 0.005 currency units per unit per day
* L = 10 currency units per unit
* loss_pct = 0.05 (5%)

Then:

* storage_bleed = 500 * 0.005 * 121 = **302.5**
* exit_loss = 500 * 10 * 0.05 = **250**
* total ≈ **552.5** (plus Amazon fees, removals, etc.)

### The true worst-case in v1.1 is actually unbounded (because of the slow-bleed trap)

If a SKU sits at `rolling_14d_units = 2–3` indefinitely:

* It does **not** escalate (LOW is false)
* It does **not** recover (REC is false)
* Therefore, it can sit in Phase 1/2/3 indefinitely unless caught in monthly review 

That means worst-case `T` is “as long as you ignore it,” and storage bleed can grow linearly without an engine-enforced stop.

---

## Bottom line findings (brutally direct)

* The architecture is strong, but **v1.1 has a few spec holes that will produce materially different implementations** (grace vs fast-track/HCP, definition of “sustained,” floor definition, OOS velocity freeze). 
* The **single biggest economic loophole** is the **2 units/14d trap**: it can prevent both escalation and recovery, causing indefinite capital stagnation unless manually caught. 
* If you fix only one thing before building: **resolve the “slow bleed trap” and define the streak counters** (below-floor streak + recovery streak).
