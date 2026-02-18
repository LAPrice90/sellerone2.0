# v9 Patch — Tree-Based Phased Rollout + Scenario Codes (2026-02-17)

Status: Proposed addendum (paste into Masterplan v9 as a new section)
Purpose: turn the “spider web” into a strict trunk→branches decision tree, and define the next staged rollout (Head first, then safe write expansion).

---

## 24) Trunk → Branches Runtime Tree (canonical decision order)

This tree is *orthogonal* to strategy. It is the routing layer that decides **what kind of situation we are in**, before any optimisation or probing happens.

### 24.1 Trunk gates (must pass in order)

**T0 — Writer gate**
- If `pricing_writer_mode != CODEX_H` → **READ_ONLY** (no writes, no learning updates).
- Log: `WRITER_LOCK_BLOCK`.

**T1 — Stock gate**
- If `available <= 0` → **PARKED** (no writes; cadence drops; weekly intel only unless restock-candidate).
- Log: `STOCKOUT_PARK`.

**T2 — Daily intel gate (A-cycle coverage)**
- If “today’s” daily intel row missing/stale → run A-cycle refresh.
- If still missing → **DEFENSIVE_HOLD** (no optimisation/probing; no learning).
- Log: `A_CYCLE_MISSING_DEFENSIVE_HOLD`.

**T3 — Outcome measurability gate**
- If Buy Box not present OR winner unknown → **HOLD_OBSERVE** (no learning windows).
- Log: `OUTCOME_UNKNOWN_HOLD`.

**T4 — Ceiling integrity gate**
- Compute `final_ceiling_landed_gbp`.
- If `final_ceiling_landed_gbp < hard_floor_price_gbp` → **FAIL_CEILING_BELOW_HARD_FLOOR** (no writes).
- Log and escalate.

Only after T0–T4 pass may we route into branches below.

---

### 24.2 Primary branch: Buy Box price zone vs our floors/ceilings

Let:
- `BB = buy_box_landed_price_gbp` (or best-rival landed if BB unavailable but rivals exist)
- `HF = hard_floor_price_gbp`
- `SF = soft_floor_price_gbp` (ROI floor / target band)
- `CEIL = final_ceiling_landed_gbp`

Define the zone:

**Z0 — Below hard floor**
- Condition: `BB < HF`
- Meaning: we cannot win BB profitably.
- Allowed actions:
  - hold at `HF` (accept low share)
  - park/exit decision
  - pressure *recommendation only* (manual approval required)

**Z1 — Between hard and soft floor**
- Condition: `HF <= BB < SF`
- Meaning: BB is “winnable” but below target ROI.
- Allowed actions (Supervisor chooses):
  - defend (win some share at thin margin) **or**
  - hold at `SF` (give up BB; protect margin)
- Requires buy box win-rate evidence + expected units/day estimate.

**Z2 — Between soft floor and ceiling**
- Condition: `SF <= BB <= CEIL`
- Meaning: normal competitive space.
- Allowed actions:
  - maximise profit (default)
  - bounded delta probing (if confidence low)
  - controlled share mode (Supervisor-only)

**Z3 — Above ceiling**
- Condition: `BB > CEIL`
- Meaning: market is willing to pay above what we allow (demand/compliance/eligibility clamp binds us).
- Allowed actions:
  - margin harvest up toward `CEIL` (slow ladder)
  - monitor for eligibility/compliance drift

---

### 24.3 Secondary branch: Buy Box ownership + win-rate

Let:
- `WIN_NOW ∈ {0,1}` (are we featured winner now?)
- `WIN_RATE_48H` (or 7d) from snapshot facts

Buckets:

- **B0 (Control):** `WIN_RATE >= 80%`
- **B1 (Shared/rotating):** `20% <= WIN_RATE < 80%`
- **B2 (Not winning):** `WIN_RATE < 20%` (or 0 if enough eligible snapshots)

This bucket governs whether we start with **harvest** (B0), **stabilise + learn deltas** (B1), or **defend/ignore decision** (B2).

---

## 25) Scenario Codes (lightweight “binary-ish” routing)

To prevent long conversations getting lost, every cycle emits one compact `scenario_code`.

Format:
`W{writer}S{stock}I{intel}O{outcome}Z{zone}B{bb_bucket}`

Where:
- `writer`: 1=CODEX_H, 0=not CODEX_H
- `stock`: 1=in stock, 0=out of stock
- `intel`: 1=today’s intel present, 0=missing/stale
- `outcome`: 1=winner known, 0=unknown
- `zone`: 0..3 (Z0..Z3 above)
- `bb_bucket`: 0..2 (B0..B2 above)

Example:
- `W1S1I1O1Z2B0` = “safe to act, in stock, intel OK, outcome OK, profitable zone, we control BB”.

This code becomes the *index key* for branching strategy docs and later binary encodings if desired.

---

## 26) Phased rollout — next stages (step-up plan)

### Phase 1.5 — Stabilise before expanding writes (mandatory hardening)
Goals:
- eliminate writer conflicts
- eliminate blind operation when daily intel missing
- stop unnecessary writes (no-change writes, write storms)

Deliverables:
1) Enforce `pricing_writer_mode` per SKU (`PPP | CODEX_H | READ_ONLY`) and hard-block conflicting writes.
2) Gate H-cycle to `DEFENSIVE_HOLD` if daily intel missing for the SKU.
3) Enforce `max_writes_per_day`, cooldown, and “no-change = no write”.
4) Align CPT handling to “pin-and-observe” (telemetry), not a ceiling clamp unless explicitly enabled.

### Phase 2 — Roll out the Head (portfolio configuration + data collection)
Goal: create a complete per-SKU config + evidence base, while staying mostly read-only.

Head outputs (daily):
- stock-gated candidate list (available > 0)
- per-SKU boundaries: `hard_floor`, `soft_floor`, `manual_cap` (demand proxy)
- strategy tag: `SNL` vs `STANDARD`
- writer mode: `PPP/CODEX_H/READ_ONLY`
- initial lane: `ignore/exploit/defend/fight` (coarse v0)

Supervisor evidence pack (daily/weekly):
- buy box win rate, price gap distributions, volatility flags, outcome-known %.

No repricing expansion yet except explicitly selected safe SKUs.

### Phase 3 — Enable writes only on BB-control SKUs (Harvest Mode)
Eligibility:
- scenario codes consistently `W1S1I1O1`
- bucket `B0` (>=80% BB win rate)
- stable market structure (low churn)
- not “bill payer / do-not-touch” category

Behaviour:
- **margin harvest ladder** upward in small steps (SNL 0.10–0.20; STANDARD 0.50–1.00) with longer observation windows.
- stop/step back if win-rate or velocity drops beyond tolerance.

### Phase 4 — Enable writes on profitable contested SKUs (Defend Mode)
Eligibility:
- zone `Z2` (BB within floors/ceiling)
- expected profit/day above threshold
- no pricing health issues
- budget tier assigned

Behaviour:
- regain + delta learning in effective-price space
- cautious ladder + volatility discounts when confidence low

### Phase 5 — Seller behaviour intelligence + pressure recommendations (no automation)
- implement variant-level seller memory (reaction speed, persistence, floor confidence)
- generate pressure *recommendations* only, with explicit economic model + kill conditions
- pressure execution remains manual

### Phase 6 — Scale hardening
- notifications (event-led runtime) + budgets + refresh orchestration
- portfolio governor fully enforced
- expand SKU coverage safely

---

End of patch.
