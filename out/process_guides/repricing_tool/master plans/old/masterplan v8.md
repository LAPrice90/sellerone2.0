# Masterplan v8 — Unified Repricing Intelligence + Delivery Value Engine + Three-Ceiling Governance + Pressure State + Dual-Identity Offer Model + Outcome Admissibility + Event-Led Runtime + Eligibility Ceiling Ladder

Status: Active Draft (Unified v8)  
Date: 2026-02-12  
Owner: Luke (business intent), Codex (execution support)

## 0) What Changed vs v7 (diff guide)
1. **Notifications are now a core dependency (not a “pre-scale enhancement”)**
   - The runtime is event-led by default: notification intake → dedupe → refresh orchestration → targeted snapshot → decision.
   - Polling is now explicitly fallback/heartbeat only.
2. **`PRICING_HEALTH` is elevated to a portfolio risk interrupt**
   - Health events pre-empt normal optimisation: they trigger risk overrides (`defensive_hold` / `parked`) and can freeze actions until resolved.
   - Health events also hard-fail learning windows via Outcome Admissibility (OAS).
3. **API budgets are formalised and enforceable**
   - Global hard-stop and per-SKU rolling budgets are mandatory.
   - Noisy/chaotic SKUs cannot starve the rest of the catalogue.
4. **Eligibility ceiling is now a deterministic ladder with explicit FOEP failure modes**
   - FOEP is used only when present, sane, and eligible.
   - When FOEP is missing/ineligible/untrusted, the system falls back in a reason-coded order (CPT → manual → historical wins → conservative market proxy).
5. **Eligibility diagnostics + health checks are expanded**
   - `eligibility_source`, `eligibility_reason_codes[]`, FOEP/CPT staleness, and source distribution reporting are required outputs.
6. **Expansion gate is upgraded**
   - No SKU expansion unless: notifications are reliable, budgets prevent starvation, pull volume drops vs baseline polling, **and** there are no missed pricing-health interrupts in the validation window.
   - Additionally: eligibility ceiling coverage must be complete (no null source; fallbacks reason-coded).

---

## 1) Canonical Rule (Single Source of Truth)
- This file is the only authoritative repricing plan going forward.
- Any other plan files are reference/archive unless their content is explicitly copied into this file.

---

## 2) Goal
Build a repricing system that:
- **Maximises expected sustainable profit per day** under competitive constraints (default).
- Supports **aggressive tactics** (share capture / floor discovery / pressure) only when rational, never as default.
- Learns from **real Buy Box outcomes** and **seller behaviour**, not just visible “lowest price”.
- Prices the economic reality that:
  - **Delivery speed has monetary value** (Delivery Value Engine).
  - **Eligibility signals (FOEP/CPT) constrain feasible pricing**.
  - **Demand has a ceiling** even when eligible and compliant.
- Scales from one pilot SKU to broad coverage with strict guardrails and explainability.

---

## 3) Non-Negotiables
1. **Default objective is profit optimisation**: never “lowest winning price” by default.
2. **Hard floor is sacred**: never breached, for any mode.
3. **Effective price is mandatory**: competitiveness comparisons use *effective price* (landed + delivery penalty).
4. **Three ceilings must remain separate**:
   - Compliance (policy)
   - Eligibility (Buy Box feasibility)
   - Demand (conversion realism)
5. **Ceilings clamp before optimisation**: the optimiser never sees “forbidden” price space.
6. **Identity must be structurally continuous**:
   - snapshot rows are **append-only** (no dedupe-by-price, no overwrite)
   - behavioural identity is **variant-based** and excludes dynamic fields (price, delivery SLA)
7. **Strategy unit**
   - **Behavioural modelling unit:** `SKU + offer_variant_id`
   - **Capital/portfolio unit:** `SKU` (and seller rollups via `seller_id_canonical`)
8. **Learning is behaviour-triggered**: re-enter learning on drift/unknowns; calendar checks are only backup.
9. **Market structure integrity**: if market changes during a test, learning confidence must be invalidated.
10. **Execution must be explainable**: reason codes + confidence + logged pre/post estimates.
11. **Aggression is an explicit override**: gated, time-boxed, measurable, with kill conditions.
12. **Eligibility intelligence never writes prices**: FOEP/CPT constrain or warn; they do not set targets.
13. **No "delivery = stock" inference**: delivery windows are competitiveness signals only and must not be treated as inventory truth.
14. **Portfolio Governor is mandatory daily**: SKUs must pass a fight-worthiness gate before high-cadence tactics.
15. **Seller priority is mandatory weighting**: `ignore/exploit/neutral/defend/pressure_candidate` must affect cadence and ladder behaviour.
16. **Pressure state is manual-execution only**:
    - system can recommend
    - Supervisor can recommend
    - **Head must approve**
    - no autonomous extensions

---

## 4) Operating Model (Roles)

### Head (Boundaries + Intent + Capital Allocation)
Sets per-SKU boundaries and intent **before** any optimisation runs.

Minimum set:
- `hard_floor_price_gbp`
- `soft_floor_price_gbp`
- `target_roi_band_pct`
- `today_intent` (default: `maximize_profit`)
- `api_budget_tier` / cadence limits
- Optional: `manual_cap_price_gbp` (only if explicitly reason-coded)

Pressure-specific authority:
- approves `OBJ_PRESSURE_MANUAL` activations (pressure is capital strategy).

### Supervisor (Mode + Plan Approval)
Chooses objective state (default profit; optional overrides).  
Approves ladder depth, max move, cooldown, probe style.  
May recommend pressure, but cannot activate without Head approval.

### Optimiser (Profit Engine)
Builds candidate ladder within boundaries + ceilings.  
Uses seller-game learning + Delivery Value Engine (effective-price space) to estimate:
- win probabilities / share
- expected units/day
- profit per unit
- expected profit/day per candidate

Recommends the price that maximises expected profit/day subject to constraints.

### Pressure Analyst (Recommendation Engine)
Produces pressure candidates and a pressure feasibility score.
It may:
- classify opponent type
- estimate probability of exit
- estimate margin loss during pressure
- estimate post-exit uplift and expected gain
- propose a time-boxed plan and kill conditions

It may **not**:
- write prices
- extend a pressure campaign

### Executioner (Write + Observe + Log)
Executes only approved actions.
- normal states: executes Optimiser-selected action (Supervisor-approved)
- pressure state: executes the **pre-approved pressure plan** (time-boxed)
Logs actions + response windows + measured outcomes.  
Updates learning memory only when market structure is stable and confidence rules allow.

---

## 5) System Architecture (Modules + Cadence)

### 5.1 Data Layers (must be physically separate)

#### 5.1.1 Offer Snapshot Fact Layer (event-level truth, append-only)
This layer exists to preserve raw reality.

Each row represents **one observed offer instance at one timestamp**.

Mandatory fields (minimum):
- keys:
  - `offer_snapshot_id` (unique per observed row)
  - `sku`
  - `timestamp_utc`
  - `seller_id_raw`
  - `seller_id_canonical` (derived; see §5.1.3)
  - `offer_variant_id` (derived; see §5.1.2)
- offer facts:
  - `listing_price_gbp`, `shipping_gbp`, `landed_price_gbp`
  - delivery window (`min_days`, `max_days`)
  - fulfilment channel (FBA/FBM/Amazon/etc.), Prime flag if available
  - condition (new/used/etc.)
  - shipping template / shipping profile (if you can infer it)
  - promo/coupon suspected flags
- snapshot context:
  - Buy Box winner fields (if measurable)
  - market structure fields (see §14)

Rules:
- **Never dedupe by `seller_id` only.**
- **Never include price or delivery days in any “identity key”.**
- Snapshot rows are **never deleted** and **never overwritten**.

#### 5.1.2 Offer Variant Dimension Layer (stable behavioural entity)
A variant represents a *structural version* of an offer that can change price many times while remaining the same behavioural entity.

Variant uniqueness should include structural attributes only:
- `sku`
- `seller_id_canonical`
- `fulfilment_channel` (FBA/FBM/Amazon/etc.)
- `condition`
- `shipping_template` (or nearest stable proxy)
- optionally: `marketplace_id` / region

Variant uniqueness must NOT include:
- `listing_price_gbp` / `landed_price_gbp`
- `min_days`, `max_days` (delivery SLA often shifts dynamically)

Recommended variant-id generation:
```text
offer_variant_id =
  hash(
    marketplace_id,
    sku,
    seller_id_canonical,
    fulfilment_channel,
    condition,
    shipping_template
  )
```

Variant dimension fields (minimum):
- `offer_variant_id`
- `sku`
- `seller_id_canonical`
- `fulfilment_channel`
- `condition`
- `shipping_template`
- `variant_first_seen_utc`
- `variant_last_seen_utc`
- `variant_active_flag`

#### 5.1.3 Canonical seller identity (required)
Some sources represent the same seller with multiple identifiers (or inconsistent formatting).
You must maintain:
- `seller_id_raw` (exact scraped value)
- `seller_id_canonical` (normalised)

Rules:
- All behaviour learning keys off `seller_id_canonical` + structural attributes.
- If canonical mapping changes, **do not rewrite history**: store mapping version and re-link at query time if needed.

#### 5.1.4 Persistent Seller Memory Layer (behavioural model)
Two connected levels are allowed, but **variant-level is mandatory**.

A) **Variant-level behavioural memory (primary)**
Per `SKU + offer_variant_id`:
- delta learning:
  - `learned_delta_effective_gbp`
  - `highest_delta_win_effective_gbp`
  - `lowest_delta_loss_effective_gbp`
  - `delta_confidence`
  - `valid_delta_test_count`
  - `contaminated_delta_test_count`
  - `last_valid_delta_test_utc`
  - `last_delta_test_utc`
  - `delta_confidence_source` (`learned|heuristic|degraded_fallback`)
- behaviour:
  - `reaction_speed_minutes`
  - `persistence_score`
  - `capital_depth_score`
  - `margin_tolerance_estimate`
  - `seller_floor_confidence`
  - `non_reactive_score`
  - `opponent_type` (`amazon_retail | brand_direct | distributor_clearance | low_stock | normal_unknown`)
- integrity:
  - `promo_suspected_flag`
  - `variant_integrity_score` (new: mapping stability & data cleanliness)

B) **Seller rollup memory (optional, secondary)**
Per `SKU + seller_id_canonical`:
- rollups of reaction speed / floor behaviour across variants
- used for portfolio, priority, and human-readable summaries
- must not overwrite variant-level detail

#### 5.1.5 Delivery Model Layer (SKU-level)
Per `SKU` (or SKU-cluster if needed):
- `delivery_penalty_curve_version`
- `delivery_penalty_multiplier_sku` (default 1.00)
- `delivery_confidence`
- `last_delivery_model_update_utc`

#### 5.1.6 Eligibility Intelligence Layer (SKU-level, daily)
Per `SKU` (A-cycle baseline, persisted as first-class intelligence):

**Raw signal fields**
- `foep_price_gbp` (Featured Offer Expected Price; may be null)
- `foep_status` (e.g. `OK|MISSING|ASIN_NOT_ELIGIBLE|ERROR|LOW_CONFIDENCE`)
- `foep_last_refresh_utc`
- `competitive_price_threshold_gbp` (CPT; may be null)
- `cpt_last_refresh_utc`

**Derived ladder output (source-of-truth eligibility ceiling)**
- `eligibility_ceiling_landed_gbp`
- `eligibility_source` (`FOEP|CPT|MANUAL|HIST_WIN|RIVAL_PLUS_DELTA|LAST_KNOWN_SAFE`)
- `eligibility_confidence`
- `eligibility_reason_codes[]`
- `eligibility_last_refresh_utc`

Rule:
- Eligibility intelligence **never writes prices**. It only constrains feasible price space and provides diagnostics.


#### 5.1.7 Compliance Intelligence Layer (SKU-level, daily)
Per `SKU`:
- `external_reference_price_gbp` (optional)
- `policy_buffer_pct`
- `compliance_confidence`
- `compliance_last_refresh_utc`

#### 5.1.8 Demand Model Layer (SKU-level, slow)
Per `SKU`:
- `demand_ceiling_effective_gbp` (defined in effective-price space)
- `demand_confidence`
- `demand_model_version`
- `demand_last_refresh_utc`
- Optional interim fields:
  - `bbp_max_sold_price_gbp` (temporary safe-mode proxy)
  - `historical_price_band_edges_gbp`
  - `conversion_inflection_effective_gbp`

#### 5.1.9 Ceiling Engine Output Layer (SKU-level, computed)
Per `SKU` per day (A-cycle baseline) and per H-cycle snapshot (event-level):
- `compliance_ceiling_landed_gbp`
- `eligibility_ceiling_landed_gbp` (combined)
- `eligibility_ceiling_landed_signal_gbp`
- `eligibility_ceiling_landed_market_gbp`
- `demand_ceiling_landed_gbp`
- `final_ceiling_landed_gbp`
- `binding_ceiling_type` (`compliance|eligibility|demand|manual`)
- `ceiling_confidence_overall`
- `ceiling_reason_codes[]`

#### 5.1.10 Portfolio Governor Layer (SKU-level, daily)
Per `SKU`:
- `listing_worth_fighting_score`
- `aggressor_probability`
- `capital_lockup_factor`
- `delivery_competitiveness_factor`
- `portfolio_lane` (`fight`, `defend`, `exploit`, `ignore`)
- `portfolio_gate_status` (`pass`, `restricted`, `fail`)
- `pressure_allowed_flag` (only true if lane=fight and economics justify)

#### 5.1.11 Seller Priority Layer (variant-first, seller-rollup allowed)
Priority exists to allocate ladder density, learning sensitivity, and cadence.

A) Variant priority (recommended default)
Per `SKU + offer_variant_id`:
- `seller_priority_level` (`ignore`, `exploit`, `neutral`, `defend`, `pressure_candidate`)
- `priority_confidence`
- `priority_last_refresh_utc`
- `priority_reason_code`

B) Seller rollup (optional)
Per `SKU + seller_id_canonical`:
- summary of variant priorities (e.g. max severity)
- used for dashboarding

#### 5.1.12 Pressure Strategy Layer (case-level)
Per `pressure_case_id`:
- identity:
  - `sku`
  - `target_seller_id_canonical`
  - `target_offer_variant_id` (preferred targeting key)
  - `case_created_utc`
  - `case_status` (`draft|recommended|approved|active|ended|aborted`)
- qualification inputs:
  - opponent validation fields + thresholds used
  - profit model inputs + outputs
  - resource check inputs + outputs
  - compliance/CPT anchor checks + outputs
- plan:
  - `pressure_start_utc`
  - `pressure_end_utc` (hard stop)
  - `max_pressure_days` (default 5)
  - `pressure_floor_price_gbp` (>= hard floor and >= anchor floor)
  - `max_daily_cut_gbp`
  - `cooldown_days_after` (default 3–7)
  - `exit_triggers[]`
  - `kill_conditions[]`
- economics:
  - `pressure_profit_per_day_est`
  - `expected_post_exit_profit_per_day_est`
  - `probability_of_exit_est`
  - `expected_uplift_days_est`
  - `expected_gain_est_gbp`
- approvals:
  - `supervisor_recommendation_utc`
  - `head_approval_utc`
  - `approval_reason_code`
- outcomes:
  - `ended_reason_code`
  - measured margin and volume deltas
  - whether competitor exited/retreated/returned

#### 5.1.13 Notification Intake Layer (event-led triggers, always-on)
This layer exists to make notifications a **core dependency** of the pricing runtime (not an optional enhancement).

A) **Raw notification event log (append-only)**
Per event:
- `notification_event_id`
- `sku`
- `event_type` (`ANY_OFFER_CHANGED|PRICING_HEALTH|...`)
- `received_utc`
- `dedupe_key` (e.g. `(sku, event_type, bucket_5m)`)
- `raw_payload_json`
- `processed_flag`
- `processing_error_code?`

B) **Per-SKU notification health**
Per `SKU`:
- `notifications_last_seen_utc`
- `event_backlog_age_seconds`
- `event_inbox_depth`
- `missed_notification_suspected_flag`

Rule:
- If notification intake is stale, the SKU must degrade to a safer cadence (heartbeat polling) and/or enter `defensive_hold` depending on risk.

#### 5.1.14 Refresh Orchestration Layer (queue + cooldown + urgency)
This layer decides *what to refresh* and *when* under budget limits.

Per `SKU` refresh queue record:
- `refresh_request_id`
- `sku`
- `refresh_reason` (`ANY_OFFER_CHANGED|PRICING_HEALTH|HEARTBEAT|MANUAL`)
- `refresh_urgency` (`now|soon|defer`)
- `requested_utc`
- `eligible_after_utc` (cooldown gate)
- `executed_utc?`
- `execution_status` (`pending|running|done|dropped|failed`)
- `drop_reason_code?` (e.g. `BUDGET_EXHAUSTED`, `COOLDOWN_ACTIVE`)

Rule:
- PRICING_HEALTH refreshes are always higher priority than ANY_OFFER_CHANGED refreshes.

#### 5.1.15 API Budget + Rate-Limit Layer (global + per-SKU)
Budgets are required to prevent staleness, throttling, and portfolio starvation.

A) **Global budget controls**
- `global_calls_remaining_est`
- `global_near_exhaustion_flag`
- `global_hard_stop_flag`
- `global_budget_last_update_utc`

B) **Per-SKU rolling budgets**
Per `SKU`:
- `api_budget_tier` (from Head)
- `sku_calls_used_24h`
- `sku_budget_limit_24h`
- `sku_budget_exhausted_flag`
- `sku_budget_last_update_utc`

Rule:
- No single SKU may exceed its tier budget.
- Under global constraint, PRICING_HEALTH handling pre-empts routine refresh and duels.


---

### 5.2 Two Operating Cycles

#### A-Cycle (Daily Intelligence Build) — once/day per SKU
- Pull FOEP + CompetitivePriceThreshold.
- Refresh compliance inputs (external reference price if used; policy buffer).
- Update (or carry forward) demand model state (slow cadence; weekly or when enough data).
- Run Portfolio Governor scoring and lane assignment (including pressure-allowed).
- Refresh seller/variant priority levels from behaviour + economics.
- Compute and store baseline ceiling outputs (not snapshot-specific).
- Pressure Analyst may generate *recommendations* (no writes).

#### H-Cycle (Execution / Optimisation) — event-led runtime (notifications first) + heartbeat polling fallback
Triggered by:
- **Notifications (preferred):**
  - `ANY_OFFER_CHANGED` → tactical refresh targeting (only refresh SKUs that actually moved)
  - `PRICING_HEALTH` → risk interrupt (override state + clamp/freeze logic)
- **Heartbeat polling (fallback only):**
  - low-frequency “are we blind?” checks to cover missed notifications or integration outages
  - automatic escalation if `notifications_last_seen_utc` is stale

Execution order (runtime envelope; pre-decision orchestration):
0. **Consume event inbox** → dedupe → apply per-SKU cooldown → create refresh request with urgency (`now|soon|defer`)
1. **Budget gate** (global + per-SKU) → prioritise `PRICING_HEALTH` over routine refresh
2. **Snapshot market offers** (**create snapshot ids**, store raw)
3. **Map each row to an offer variant** (**stable variant ids**)
4. **Compute effective prices** (Delivery Value Engine)
5. **Compute snapshot-specific ceilings** (Ceiling Engine; incl. eligibility ladder output + market-based ceiling)
6. **Resolve Strategy State** (normal vs pressure) and apply any `PRICING_HEALTH` overrides
7. **Decide action**
   - normal: run profit optimisation inside floors/ceilings
   - pressure: follow the approved pressure plan schedule (no optimisation)
8. **Propose/execute action** (approvals + guardrails)
9. **Log + observe + update learning (if stable)** via OAS

Precedence rule (to remove ambiguity):
- §5.2 defines trigger intake, queueing, budget gating, and refresh orchestration.
- Once a refresh is admitted for execution, the decision pipeline must follow **§11 Step 0 -> Step 14** in exact order.
- If wording ever conflicts between §5.2 and §11, **§11 is canonical for per-refresh decision order**.

---


## 6) Core Definitions (Canonical)
- `landed_price_gbp = listing_price_gbp + shipping_gbp`

### Effective price (Delivery Value Engine space)
For any offer **i**:
- `fastest_delivery_days = min(offer.min_delivery_days for offers in snapshot)`
- `delivery_gap_days_i = offer_i.min_delivery_days - fastest_delivery_days`
- `delivery_penalty_gbp_i = DVE_penalty(delivery_gap_days_i) * delivery_penalty_multiplier_sku`
- `effective_price_gbp_i = landed_price_gbp_i + delivery_penalty_gbp_i`

Rules:
- delivery penalty is **non-negative**
- delivery penalty is **0** for the fastest offer(s)

### Ceiling rule (important)
- **Optimisation, learning, and competition comparisons are done in effective-price space.**
- **All ceilings ultimately clamp our landed price** (because Amazon pricing + listing price are landed-price constructs), but:
  - demand ceiling is learned in effective space and translated to landed space per snapshot
  - market-based eligibility is computed in effective space and translated to landed space per snapshot

---

## 7) Delivery Value Engine (DVE)

### 7.1 Why it exists
Price-only logic is incomplete: two sellers at the same visible price are not equal if one delivers tomorrow and one delivers in 3 days.

DVE converts delivery posture into a monetary penalty used in competitiveness comparisons and optimisation.

### 7.2 Layer 1 — Bootstrap Heuristic (Always On)
Default conservative curve (v0):
- gap 0 days → £0.00
- gap 1 day  → £0.15
- gap 2 days → £0.30
- gap 3 days → £0.45
- gap 4+ days → £0.60 (cap)

Implementation:
```text
gap = clamp_int(delivery_gap_days, min=0, max=4)
penalty_base = [0.00, 0.15, 0.30, 0.45, 0.60][gap]
delivery_penalty_gbp = penalty_base * delivery_penalty_multiplier_sku
```

### 7.3 Layer 2 — Eligibility Intelligence Overlay (FOEP + CPT + deterministic fallbacks)
Eligibility intelligence does not write prices. It acts as:
1) **constraint**: clamps candidate price space so the optimiser never “believes in” infeasible Featured/Buy Box pricing
2) **diagnostic**: tells you when you are losing eligibility for structural reasons (not just competition)

Daily persisted fields (see §5.1.6):
- FOEP: `foep_price_gbp`, `foep_status`, `foep_last_refresh_utc`
- CPT: `competitive_price_threshold_gbp`, `cpt_last_refresh_utc`
- ladder output: `eligibility_ceiling_landed_gbp`, `eligibility_source`, `eligibility_confidence`, `eligibility_reason_codes[]`

Core rule:
- FOEP is **optional**. Missing/invalid FOEP must not widen the optimiser’s search space; it must trigger a reason-coded fallback path.

See §8.2 for the full eligibility ceiling ladder and FOEP usability rules.


### 7.4 Layer 3 - Learned Correction (Slow Adaptive Adjustment)
Parameter:
- `delivery_penalty_multiplier_sku` (default 1.00)
- bounds: 0.50 to 2.00

Update only when ALL are true:
- minimum stable events (`min_delivery_events >= N`, start N=20)
- `market_structure_hash` stable during those events (variant-level stability; see §14)
- promo/coupon not suspected
- consistent undercut bias across time and sellers

### 7.5 DVE outputs (must be logged per cycle)
Per offer snapshot row:
- `offer_snapshot_id`
- `offer_variant_id`
- `min_delivery_days`
- `max_delivery_days`
- `delivery_gap_days`
- `delivery_penalty_gbp`
- `effective_price_gbp`

Per SKU per cycle:
- `fastest_delivery_days`
- `delivery_penalty_multiplier_sku`
- `delivery_penalty_curve_version`
- `delivery_penalty_unknown_flag`

---

## 8) Three-Ceiling Model (Canonical)

### 8.1 Compliance Ceiling (Policy / Suppression Safety) — landed-price
Inputs:
- `competitive_price_threshold_gbp` (CPT)
- `external_reference_price_gbp` (optional)
- `policy_buffer_pct` (recommended 0.02–0.05)

Computation:
```text
compliance_anchor = min(competitive_price_threshold_gbp, external_reference_price_gbp?) 
compliance_ceiling_landed_gbp = compliance_anchor * (1 - policy_buffer_pct)
```

Rules:
- Always on.
- Hard clamp (cannot be overridden autonomously).
- If compliance inputs are missing, mark low confidence and fall back in this order:
  - use `competitive_price_threshold_gbp` only (if present)
  - else use last known compliance ceiling
  - else escalate (`FAIL_NO_SAFE_COMPLIANCE_CEILING`)

### 8.2 Eligibility Ceiling (Buy Box / Featured Offer feasibility) — landed-price

**Purpose:** prevent the optimiser from exploring price space that is structurally infeasible to remain Featured/visible, even if margin looks attractive.

Key principle:
- FOEP is **optional intelligence** with explicit failure modes. Missing/invalid FOEP must **not** widen the optimiser’s allowed space; it must trigger a deterministic fallback path with reason codes.

Eligibility ceiling is computed from two independent families:

1) **Signal-based eligibility ceiling (SKU-level, A-cycle, persisted)**
- Derived from FOEP/CPT and deterministic fallbacks.
- Stored as `eligibility_ceiling_landed_gbp` with `eligibility_source`, confidence, and reason codes.

2) **Market-based eligibility ceiling (snapshot-level, H-cycle)**
- Derived from current rivals in *effective-price space* (DVE-adjusted).
- This is usually tighter and more responsive during active competition.

**Runtime rule (H-cycle):**
```text
eligibility_ceiling_landed_h =
  min(
    eligibility_ceiling_landed_signal? ,   # A-cycle stored ladder output
    eligibility_ceiling_landed_market?     # computed from current snapshot
  )
```

If one side is missing, the other may bind — but the missing side must be reason-coded and confidence-adjusted.

---

#### 8.2.1 FOEP usability rules (explicit)
FOEP is considered **usable** only when all are true:
- `foep_price_gbp` is present and > 0
- `foep_status` indicates the ASIN/offer is eligible (not `ASIN_NOT_ELIGIBLE`, not error)
- sanity check passes (starter):
  - FOEP is within plausible bounds vs observed market (e.g. within `[0.5×, 2.0×]` of current best-rival landed price, if rivals exist)
  - otherwise set `foep_status = LOW_CONFIDENCE` and treat as unusable

FOEP is **not usable** when any are true:
- missing/null
- `foep_status = ASIN_NOT_ELIGIBLE`
- endpoint error / stale data beyond threshold
- sanity check fails

Mandatory behaviour when FOEP is not usable:
- set `eligibility_source = <fallback>`
- set `eligibility_reason_codes[]` to include one of:
  - `FOEP_MISSING`
  - `FOEP_INELIGIBLE_ASIN`
  - `FOEP_ERROR`
  - `FOEP_SANITY_FAIL`
- lower `eligibility_confidence`

---

#### 8.2.2 Signal-based eligibility ceiling ladder (A-cycle, strict order)
Compute once per day per SKU (or on demand when stale), and persist:

**Source ladder (strict order):**
1. **FOEP (usable)**  
2. **CPT** (if present)
3. **Manual ceiling** (Head-provided manual cap, reason-coded)  
4. **Historical highest winning effective band** (from admissible wins; converted to landed per snapshot as needed)  
5. **Conservative market proxy** (e.g. `best_rival_effective - heuristic_delta`, or last-known-safe ceiling)

Store:
- `eligibility_ceiling_landed_gbp`
- `eligibility_source` (`FOEP|CPT|MANUAL|HIST_WIN|RIVAL_PLUS_DELTA|LAST_KNOWN_SAFE`)
- `eligibility_confidence`
- `eligibility_reason_codes[]`

Important:
- If multiple signal anchors exist (FOEP + CPT), the signal ceiling may be:
```text
eligibility_ceiling_landed_signal_gbp = min(foep_price_gbp, competitive_price_threshold_gbp)
```
…but you must record *which* inputs were present and which bound was actually binding in `eligibility_reason_codes[]` (auditability).

---

#### 8.2.3 Market-based eligibility ceiling (H-cycle, effective-price game)
This is the snapshot-driven ceiling used during active competition:

1. `best_rival_effective_gbp = min(effective_price_gbp_i excluding ours)`
2. `required_undercut_effective_gbp = f(learned_delta_effective_gbp, confidence, seller mix)`
3. `max_winning_effective_gbp = best_rival_effective_gbp - required_undercut_effective_gbp`
4. Translate to landed for our offer:
```text
eligibility_ceiling_landed_market_gbp = max_winning_effective_gbp - our_delivery_penalty_gbp
```

Fallbacks:
- If rivals absent → market-based ceiling may be null (signal ladder must cover the SKU).
- If delta confidence too low → use conservative heuristic delta and reason-code:
  - `DELTA_CONSUMER_FALLBACK_LOW_CONFIDENCE`

---

#### 8.2.4 Interaction with the three-ceiling clamp
Eligibility ceiling never bypasses:
- compliance ceiling (policy safety)
- demand ceiling (conversion realism)
- hard floor (sacred)

Final clamp remains:
```text
final_ceiling_landed_gbp = min(
  compliance_ceiling_landed_gbp,
  eligibility_ceiling_landed_h,
  demand_ceiling_landed_gbp,
  manual_cap_price_gbp?
)
```


### 8.3 Demand Ceiling (Conversion / Volume Realism) — effective-price first
Demand ceiling is defined in effective-price space:
- `demand_ceiling_effective_gbp`

Translate to landed-price per snapshot:
```text
demand_ceiling_landed_gbp = demand_ceiling_effective_gbp - our_delivery_penalty_gbp
```

### 8.4 Manual Cap (Optional, reason-coded)
```text
final_ceiling_landed_gbp = min(final_ceiling_landed_gbp, manual_cap_price_gbp)
```

### 8.5 Final clamp
```text
final_ceiling_landed_gbp = min(
  compliance_ceiling_landed_gbp,
  eligibility_ceiling_landed_gbp,
  demand_ceiling_landed_gbp,
  manual_cap_price_gbp?
)
hard_floor_price_gbp <= candidate_price_gbp <= final_ceiling_landed_gbp
```

### 8.6 Mode binding (how the same ceilings behave differently)
| Mode | Typical binding ceiling | Why |
|---|---|---|
| `active_competition` | Eligibility | You are constrained by what can win share/BB |
| `low_no_competition` | Demand | You are constrained by customer conversion, not rivals |
| `defensive_hold` | Compliance | Risk-averse behavior, policy safety dominates |

### 8.7 Failure state
If `final_ceiling_landed_gbp < hard_floor_price_gbp`:
- do **not** run optimisation
- escalate with `FAIL_CEILING_BELOW_HARD_FLOOR`

If any ceiling is missing:
- continue only if a safer ceiling exists
- otherwise escalate (`FAIL_NO_SAFE_CEILING`)

---

## 9) Strategy State Machine (Unified)
A **strategy state** determines which engine is allowed to act.

### 9.1 States (canonical set)
- `maximize_profit` (default)
- `low_no_competition` (mandatory when competition is absent)
- `defensive_hold` (risk-minimising)
- `floor_discovery` (bounded experiment)
- `maximize_share` (Supervisor-only)
- `pressure` (manual-only, capital strategy)

### 9.2 State selection rules (high level)
1) If a pressure case is `active` → `state = pressure`
2) Else if competition absent → `state = low_no_competition`
3) Else if volatility / integrity risk high → `state = defensive_hold`
4) Else → `state = maximize_profit`
5) `maximize_share` and `floor_discovery` require Supervisor approval and are time-boxed.

### 9.3 Lane vs State (Portfolio Governor integration)
- If `portfolio_gate_status = fail`:
  - states allowed: `low_no_competition`, `maximize_profit` (restricted), `defensive_hold`
  - states blocked: `pressure`, `floor_discovery`, `maximize_share`
- If `portfolio_gate_status = restricted`:
  - pressure blocked
  - floor discovery restricted to minimal budgets
- Pressure requires:
  - `portfolio_lane = fight`
  - `pressure_allowed_flag = true`
  - Head approval of a pressure case

---

## 10) Pressure State (Nuclear Mode) — Full Integration

### 10.1 What pressure is (strip emotion)
Pressure is:
> A short-term intentional reduction in profit per unit in order to increase long-term expected profit by forcing competitor exit or retreat.

This is **capital allocation**, not routine repricing.

### 10.2 Why it is risky (why we do not automate execution)
Pressure can fail due to:
- fighting the wrong opponent (infinite-capital or structurally-lower-cost sellers)
- CPT/eligibility anchoring risk (you permanently drag the listing’s future ceiling down)
- operational/cashflow strain (higher volume at lower margin)

### 10.3 The only rational case
Pressure is rational only if:

```text
Net_expected_profit_after_exit
>
Profit_during_pressure_period
+
Risk_adjusted_cost
```

Where `Risk_adjusted_cost` includes:
- cashflow strain and stockout risk
- operational load (pick/pack/reorder)
- return/refund exposure
- probability the competitor returns

If you cannot model this, you cannot safely automate pressure.

---

### 10.4 Pressure Qualification Framework (mandatory gates)
A pressure case cannot be approved unless **all** gates pass.

#### Gate 1 — Opponent validation (do not fight structurally stronger sellers)
All must be true (thresholds are configurable, but must be explicit in the case record):
- `persistence_score >= persistence_threshold`
- `reaction_speed_minutes <= reaction_speed_max` (must be “fast chaser”)
- `seller_floor_confidence >= floor_confidence_min`
- `capital_depth_score <= capital_depth_max`
- `opponent_type NOT IN {amazon_retail, brand_direct}` unless explicitly approved with special reason code

If opponent is structurally stronger → **disqualify**.

Opponent-type heuristics (starter):
- **amazon_retail**: seller_id indicates Amazon or channel/brand patterns strongly match
- **brand_direct**: consistent lowest cost behaviour + brand ownership signals + high persistence
- **distributor_clearance**: deep cuts with low persistence + short duration + price not reactive
- **low_stock**: price stays fixed, disappears soon after (needs cautious inference; do not assume)

#### Gate 2 — Profit uplift model (expected gain must be > 0)
Compute:
- `expected_post_exit_profit_per_day`
- `expected_pressure_duration_days`
- `pressure_profit_per_day`
- `probability_of_exit`
- `expected_uplift_days`

Then:
```text
margin_loss_per_day = (baseline_profit_per_day - pressure_profit_per_day)

expected_gain =
(probability_of_exit × expected_uplift_days × uplift_profit_per_day)
-
(expected_pressure_duration_days × margin_loss_per_day)
```

Rule:
- if `expected_gain <= 0` → **abort**
- no emotion allowed

#### Gate 3 — Resource check (you must be able to sustain the campaign)
All must be true:
- `stock_days_cover >= required_pressure_days + buffer_days`
- `cash_buffer_gbp >= cash_buffer_min_gbp`
- `operational_capacity_score >= ops_threshold`

If not → abort.

#### Gate 4 — Compliance + CPT anchor distortion check (protect future ceiling)
Pressure must respect:
- `pressure_price_gbp >= hard_floor_price_gbp` (always)
- `pressure_price_gbp >= price_history_anchor_floor_gbp` (protects future ceiling)
- `pressure_price_gbp >= compliance_floor_gbp` (if you maintain any additional compliance floor)
- if the campaign would create a new “too-low anchor” relative to recent history → abort unless Head overrides with explicit reason code.

**Price-history anchor floor (recommended)**
Maintain:
- `lowest_landed_price_last_30d_gbp`
- `lowest_landed_price_last_90d_gbp`
- `cpt_last_30d_gbp` trend (daily)

Then define:
```text
price_history_anchor_floor_gbp =
max(
  hard_floor_price_gbp,
  lowest_landed_price_last_30d_gbp - anchor_extension_allowance_gbp
)
```

Purpose:
- allow *small* new lows when justified
- block huge step-downs that permanently reset CPT/eligibility anchors

---

### 10.5 What automation is allowed to do (safe scope)
Automation may:
- detect candidate scenarios (aggressor enters; margin collapse; persistent chasing)
- compute a pressure feasibility score (with assumptions declared)
- generate a recommended plan (time box, floor, max daily cut, exit triggers)
- surface “do not fight” warnings with reason codes

Automation may NOT:
- activate pressure
- write pressure prices
- extend a campaign past expiry

### 10.5.1 What should be automated instead (preferred stable gains)
Pressure is high-variance. The system should bias automation effort toward:
- offer-variant continuity + seller delta learning (effective-price space)
- seller classification + opponent typing
- reaction scoring and persistence scoring
- profit-curve optimisation (argmax profit/day inside floors/ceilings)
- eligibility ceiling detection (signal + market-based)
- defensive holds and volatility kill switches
- low/no-competition margin harvesting toward demand ceiling

These produce stable gains. Pressure produces volatile outcomes and must stay gated.

---

### 10.6 Pressure plan behaviour while active
Once approved:

**Time box**
- default `max_pressure_days = 5`
- hard expiry timestamp is mandatory

**Movement rules**
- hard floor never breached
- `max_daily_cut_gbp` enforced
- cooldown enforced after campaign ends

**Exit triggers (predefined)**
Any of the following triggers ends the campaign:
- competitor stockout/disappearance (offer removed)
- competitor delivery deterioration (their effective price rises vs you)
- competitor price retreat (they stop chasing and move up)
- time expiry

**If expiry hits without exit**
- auto-revert to `defensive_hold`
- no extension without review and a new approval record

---

### 10.7 Post-pressure harvest rule (critical)
If competitor exits/retreats:
1) immediately revert to normal state (`maximize_profit` or `low_no_competition`)
2) re-run ceilings (they may have changed)
3) climb via profit-led ladder toward demand ceiling (do **not** instantly jump to ceiling)
4) monitor for competitor re-entry during the first 72 hours

---

### 10.8 Evidence requirement before any “partial automation”
Pressure execution remains manual until:
- **20–30 completed pressure cases** exist
- a clear majority show positive **net** expected gain vs baseline
- CPT anchor damage rate is acceptably low
- operational load impact is quantified and tolerable

Only then can you consider partial automation (still with hard gates).

---

## 11) Decision Flow Per H-Cycle (Mandatory Order)

Scope boundary:
- This section is the canonical decision order **inside an admitted refresh execution**.
- Event intake, dedupe, cooldown, queueing, and budget admission are handled earlier by §5.2 and §18.2-§18.3.
- After admission, run Step 0 -> Step 14 exactly as written below.

### Step 0 — Strategy State Resolution
- If `pressure_case_status = active` → follow pressure plan
- Else choose state using §9 rules

### Step 1 — Portfolio Governor Gate (Mandatory Daily)
Load `portfolio_gate_status` and `portfolio_lane`.

- If `fail`: no duel logic; exploit/ignore behaviour; minimal cadence.
- If `restricted`: narrow ladder, defensive cadence, block pressure.

### Step 2 — Head Boundaries (Hard)
Validate:
- `hard_floor_price_gbp` exists and is sane
- `soft_floor_price_gbp` exists
- inventory constraints (stock days cover)
- state is allowed by gate status

### Step 3 — Market Truth Snapshot (Offer Snapshot Facts)
Capture all offers (do not collapse to one offer per seller).
For each observed row:
- generate `offer_snapshot_id`
- store full raw row in the Offer Snapshot Fact table
- derive `seller_id_canonical`

Detect:
- Buy Box winner + price
- channels and delivery postures
- new variants / exits
- coupons/promos
- offer count changes

### Step 4 — Variant Mapping (Mandatory)
For each snapshot row:
- derive structural fields (channel, condition, shipping template, marketplace)
- compute `offer_variant_id`
- upsert into Offer Variant Dimension (first_seen/last_seen)
- link snapshot row → variant id

If variant mapping fails:
- set `variant_mapping_failed_flag = true`
- block learning updates for this cycle (`SELLER_DELTA_UPDATE_BLOCKED_UNSTABLE_MARKET`)

### Step 5 — Delivery Value Engine Pass
Compute effective price for every snapshot row.

### Step 6 — Ceiling Engine (Snapshot-specific ceilings)
Compute compliance / eligibility / demand ceilings.
Compute final ceiling and binding type.
Log clamp reasons.

### Step 7 — Market-Without-Us Baseline (Mandatory)
Remove our offer and estimate baseline units without us.

### Step 8 — Seller Delta Engine (Variant-level effective-price game)
Maintain delta bounds and confidence per `SKU + offer_variant_id`.
Re-enter learning on drift/unknown.

### Step 9 — Seller Priority Behaviour Weighting
Apply priority (variant-first) to ladder density, cadence, relearn sensitivity.

### Step 10 — Candidate Ladder Construction (Normal states only)
Build ladder between:
- `hard_floor_price_gbp`
- `final_ceiling_landed_gbp`

Rules:
- larger steps near ceiling
- tighter steps near learned competitor thresholds
- include anchors:
  - ceiling anchor
  - current price
  - hard floor anchor
- obey ladder depth limit (`api_budget_tier`)

### Step 11 — Outcome + Profit Estimation (Normal states only)
For each candidate landed price `P`:
- compute our landed and effective price (using current penalty)
- estimate (variant-weighted):
  - win probability vs relevant variants
  - estimated share
  - confidence score
- compute:
  - `expected_units(P) = baseline_units * estimated_total_share(P)`
  - `profit_per_unit(P) = P - cost_per_unit - fees(P) - expected_refund_impact`
  - `expected_profit_per_day(P) = expected_units(P) * profit_per_unit(P)`

Optimisation rule (default):
- choose `argmax(expected_profit_per_day(P))`

Tie-breakers:
1. higher ROI within band
2. lower volatility risk (higher confidence)
3. lower cadence / API burn

If all candidates are negative profit/day:
- escalate for `defensive_hold` / disengage / clearance review

### Step 12 — Guardrails + Risk Caps
- never breach hard floor
- daily downward movement cap
- cooldown between moves
- max step size
- volatility kill switch
- inventory risk cap
- pressure is manual-only

### Step 13 — Approval + Execution
- normal state: Supervisor approves the move, Executioner writes
- pressure state: Executioner writes per the approved plan schedule

### Step 14 — Observe + Update Learning (If Stable)
Update seller delta, delivery multiplier, demand model **only** when the Outcome Admissibility Service (OAS) returns an admissible result for the observation window (`context_quality_score > 0`).
If OAS blocks the update, **still log the outcome** (with contamination reasons) and leave memory unchanged. See §14.
After OAS passes, apply per-engine update gates in section 14.5 (do not skip engine-specific thresholds).

---

## 12) Portfolio Governor (Mandatory Daily Capital Allocation Gate)
Purpose: prevent low-yield duels and enforce capital discipline.

Daily formula:
```text
listing_worth_fighting_score =
  expected_profit_per_day
  * aggressor_probability
  * capital_lockup_factor
  * delivery_competitiveness_factor
```

Lane actions by threshold:
- below ignore threshold -> `ignore`
- between ignore and exploit -> `exploit`
- between exploit and defend -> `defend`
- above defend -> `fight`

Mandatory outputs:
- `listing_worth_fighting_score`
- `portfolio_lane`
- `portfolio_gate_status`
- `portfolio_reason_code`

Pressure allowance rule:
- `pressure_allowed_flag = true` only if:
  - `portfolio_lane = fight`
  - expected profit/day upside is high enough to justify war risk
  - stock/cash/ops buffers are healthy

---

## 13) Seller Priority Behaviour Weight Layer
Priority levels:
- `ignore`, `exploit`, `neutral`, `defend`, `pressure_candidate`

Rules:
- priority affects ladder density, probe sensitivity, cadence, and volatility tolerance
- never bypass floors/ceilings/guardrails
- `pressure_candidate` enables *recommendation generation* only (not execution)
- priority must be computable at variant-level and roll-up to seller-level.

---

## 14) Learning Integrity + Outcome Admissibility (Truth Filter)

**Principle:** the system is allowed to optimise aggressively, but it is **not allowed to learn aggressively**.
Learning must be conditional on outcome quality, otherwise the system becomes a noise amplifier.

This section defines the mandatory truth filter between:
- an observed win/loss (Buy Box / share change)
- and any update to persistent memory (delta, behaviour classifiers, delivery multiplier, demand ceiling).

### 14.1 Two Hashes: Structure vs Posture

To avoid false learning, we separate:
- **Market Structure** (who is present + their structural identity) — should be mostly stable during a probe window.
- **Market Posture** (prices, Buy Box rotation, delivery windows) — can change, but changes may contaminate a probe.

Compute at least these two hashes:

**A) `market_structure_hash` (hard gate)**
Use structural fields only (variant-based, not price-based):
- `sku`, `marketplace_id`
- sorted set of `offer_variant_id` seen in the snapshot (including ours)
- fulfilment-channel distribution (FBA/FBM/Amazon/etc.)
- condition distribution
- shipping-template distribution (or closest stable proxy)
- promo/coupon suspected flags distribution
- offer count

**Rule:** if `market_structure_hash` changes materially between probe start and probe end, the probe outcome is **inadmissible** (`context_quality_score = 0`).

**B) `market_posture_hash` (quality weighting)**
Use dynamic fields that can invalidate causal inference without being a structural change:
- Buy Box holder id (canonical) + channel (optional)
- fastest-delivery-days and delivery distribution buckets
- lowest effective price bucket (not exact price; bucket to avoid hair-trigger invalidation)
- our delivery days bucket

**Rule:** posture drift reduces `context_quality_score`; it does not automatically hard-fail unless it breaches thresholds below.

### 14.2 Outcome Admissibility Service (OAS) — Mandatory for Any Learning Update

OAS is a single shared decision function used by:
- Seller Delta updates (`learned_delta_effective_gbp`, bounds, confidence)
- Behaviour classifier updates (aggressor/persistence/floor inference)
- Delivery multiplier learning (DVE Layer 3)
- Demand-ceiling learning updates

**Input (minimum):**
- `probe_id` (or `learning_window_id`), `sku`, timestamps
- start snapshot + end snapshot (incl. `offer_snapshot_id` set)
- start/end `market_structure_hash` + `market_posture_hash`
- key flags: suppression/pricing-health/eligibility-change, stock status, promo suspicion

**Output (minimum):**
- `admissible_flag` (boolean; true iff `context_quality_score > 0`)
- `context_quality_score ∈ [0,1]`
- `admissibility_reason_codes[]` (why it passed/failed, in plain reason codes)
- `contamination_class` (`none|minor|moderate|major|hard_fail`)

### 14.3 Context Invariants (the actual truth filter)

A probe/learning window is admissible only if all hard invariants pass.
Soft invariants degrade quality rather than binary reject.

#### Hard invariants (any violation ⇒ `context_quality_score = 0`)
1) **Structural drift:** `market_structure_hash` materially changed during the window.
2) **Buy Box suppressed** at any point in the window.
3) **Self stockout / offer not purchasable** at any point in the window.
4) **Pricing health / eligibility event** during the window (CPT/FOEP disqualification, eligibility status change).
5) **Promo/coupon contamination** suspected or detected during the window (including our own unintended promo).
6) **Variant mapping failure** in either start or end snapshot (`variant_mapping_failed_flag = true`).

#### Soft invariants (degrade quality)
1) **Competitor set drift (within stable structure):**
   - offer count change within tolerance, but the set composition changed (new variants appeared / disappeared) inside allowed limits.
2) **Major delivery posture shift (us or key rivals):**
   - delivery window bucket changed beyond `allowed_shift_days` (configurable).
3) **Buy Box rotation noise:**
   - Buy Box holder changes multiple times inside the window without a clear monotonic response to our move.

### 14.4 `context_quality_score` — Scoring (starter, explicit, tunable)

Start at 1.0 and apply multipliers (never exceed [0,1]).

**Hard fails → 0.0 immediately.**

Suggested starter multipliers:
- Minor competitor drift → × 0.7
- Moderate drift → × 0.4
- Delivery posture shift (minor) → × 0.7
- Buy Box rotation noise detected → × 0.6

**Quality bands:**
- `0.85–1.00` = clean (update bounds + estimate)
- `0.40–0.85` = usable but noisy (update estimate; bounds update only if strong evidence)
- `0.01–0.39` = weak (log only; optionally update estimate with very small weight)
- `0.00` = inadmissible (no updates)

### 14.5 Update Rule (Quality-Weighted) — What Actually Changes in Memory

**Rule 1: never update on inadmissible outcomes.**

**Rule 2: do not treat hard bounds and soft estimates as the same thing.**
Blindly "weight-updating" `highest_delta_win` / `lowest_delta_loss` can corrupt the bracket. This plan separates:
- **Hard bracket bounds** (only updated from clean outcomes)
- **Soft delta estimate** (can be exponentially smoothed with quality weights)

Recommended fields:
- `highest_delta_win_effective_gbp` (hard bound; updates only if `context_quality_score ≥ 0.85` and win observed)
- `lowest_delta_loss_effective_gbp` (hard bound; updates only if `context_quality_score ≥ 0.85` and loss observed)
- `learned_delta_effective_gbp` (soft estimate; smoothed update allowed when `context_quality_score > 0`)

Soft estimate update (EWMA style):
```text
alpha = learning_rate * context_quality_score
learned_delta_new = learned_delta_old*(1-alpha) + observed_delta*(alpha)
```

Per-engine gates (mandatory, additive to OAS):
- Seller/variant memory updates only if:
  - confidence threshold met for the target field
  - variant mapping integrity passes (no mapping failures)
  - no promo contamination signal is active for the update window
- Delivery multiplier updates only if:
  - sufficient stable events are present
  - consistent delivery bias evidence is observed
  - variant-level stability is maintained
  - delivery-learning confidence threshold is met
- Demand model updates only if:
  - sufficient clean data points exist across price bands
  - delivery model version is stable during the learning window
  - conversion or velocity inflection is clearly observed in effective-price space

### 14.6 Confidence Management + Learning Consumer Contract (Non-Negotiable)

Delta confidence must reflect evidence quality, not just recency.

Mandatory delta memory fields (see §5.1.4):
- valid vs contaminated test counts
- last valid test timestamp
- delta confidence source

**Consumer contract:**
- If `delta_confidence < min_delta_confidence_to_trust` then:
  - Optimiser must widen uncertainty and/or fall back to a conservative heuristic delta.
  - Executioner must avoid deep ladders and high-cadence duels.
  - Supervisor may force `defensive_hold` if the SKU is volatile.

**Staleness decay (recommended):**
- If `days_since_last_valid_test > stale_days_threshold` then force `SELLER_DELTA_DRIFT_RELEARN` and reduce confidence until a clean probe is recorded.

### 14.7 Seller Delta Learning Loop Protocol (Variant-Level, Effective-Price Space)

Your bracket logic is correct:
- find first win
- find first loss
- narrow bracket
- store `highest_delta_win` / `lowest_delta_loss`
- re-test daily

This plan adds one rule: **the loop only learns from admissible outcomes (OAS).**

Probe window contract (must be logged):
- `probe_id`, start/end timestamps
- start/end snapshot ids + hashes
- intended price move + realised price
- observed win/loss definition
- OAS decision: `context_quality_score`, reason codes

Delta learning state machine (suggested):
- `DELTA_UNKNOWN` (no bracket yet) → seek first win/loss with small safe probes
- `DELTA_BRACKETING` (one side known) → explore until both bounds exist
- `DELTA_BRACKETED` (both bounds exist) → narrow until width ≤ `delta_tolerance_gbp`
- `DELTA_CONFIDENT` (high confidence) → re-test daily or on drift
- `DELTA_DEGRADED` (contamination ratio high / stale) → reduce trust, re-learn

### 14.8 Protection Against False Aggressor Detection (must use OAS)

Aggressor classification and pressure-candidate detection must ignore inadmissible windows.
Otherwise Buy Box rotation, delivery shifts, or suppression events will create phantom aggressors and trigger margin bleed.

---
## 15) Outputs and Logging Requirements (Minimum Set)

Runtime outputs (must exist):
- `out/h_offer_snapshot_facts.csv` (new: includes offer_snapshot_id and offer_variant_id)
- `out/h_offer_variants.csv` (new: variant dimension table export)
- `out/h_offer_variant_mapping_audit.csv` (new: mapping integrity and anomalies)
- `out/h_executioner_action_log.csv`
- `out/h_worker_probe_event_log.csv`
- `out/h_worker_probe_response_log.csv`
- `out/h_seller_profiles.csv` (seller rollups, derived from variants)
- `out/h_seller_variants.csv` (new: variant-level seller memory snapshot)
- `out/h_seller_of_interest.csv`
- `out/h_seller_delta_learning.csv` (must be variant-keyed)
- `out/h_delivery_value_events.csv` (must include snapshot/variant ids)
- `out/h_sku_delivery_model.csv`
- `out/h_eligibility_intel_daily.csv`
- `out/h_compliance_intel_daily.csv`
- `out/h_demand_model.csv`
- `out/h_ceiling_events.csv`
- `out/h_portfolio_governor_daily.csv`
- `out/h_seller_priority_model.csv` (variant-first)
- `out/h_outcome_admissibility_log.csv` (OAS decisions: quality score + reason codes per probe/window)
- `out/h_notification_event_log.csv` (raw event-led triggers ingested)
- `out/h_notification_inbox_state.csv` (per-SKU inbox depth, backlog age, last-seen)
- `out/h_refresh_queue.csv` (refresh requests, urgency, cooldown, drop reasons)
- `out/h_eligibility_source_distribution_daily.csv` (% SKUs by eligibility_source)
- `out/h_eligibility_fallback_audit.csv` (SKUs running on fallback sources + reason codes)
- `out/h_api_budget_usage_by_sku.csv`
- `out/h_api_budget_usage_total.csv`
- `out/h_rate_limit_health.csv`

Pressure-specific outputs:
- `out/a_pressure_recommendations_daily.csv`
- `out/h_pressure_case_log.csv`
- `out/h_pressure_actions.csv`
- `out/h_pressure_outcomes.csv`

Every execution must log:
- snapshot ids used (e.g. `market_snapshot_id`, plus per-offer `offer_snapshot_id`)
- price facts (our/rival/BB; landed/effective)
- delivery facts (min/max days, fastest days, penalties)
- ceiling facts (compliance/eligibility/demand/final, binding ceiling)
- eligibility facts (FOEP/CPT used, confidence)
- behaviour facts (direction, lag, persistence) **variant-level**
- portfolio facts (score, lane, gate)
- priority facts
- decision facts (state, reason codes, confidence, clamps)
- profit facts (estimated profit/day before/after, units/day estimate)

Pressure executions additionally must log:
- `pressure_case_id`
- `target_offer_variant_id`
- `plan_day_index`
- `max_daily_cut_gbp` + whether clamp applied
- exit trigger hit (if any)
- CPT/FOEP trend snapshot (to detect anchor distortion)

---

## 16) Rollout Path (Recommended)
### Stage A — Pilot SKU live learning (controlled)
Implement:
- Dual identity model (snapshot + variant) and mapping audit
- DVE Layer 1 curve
- effective price logging
- seller delta learning in effective space (variant-keyed)
- ceiling event logging (even if demand ceiling is provisional)

### Stage B — Three-ceiling enforcement (hard)
- compliance ceiling with buffer
- eligibility ceiling (signal + market-based)
- demand ceiling safe-mode proxy
- final ceiling clamp drives ladder construction

### Stage C — Profit-led decision layer (default)
Profit engine becomes default selection rule.

### Stage D — Pressure recommendation only (no execution)
- implement opponent classification + pressure scoring (variant-targeted)
- generate daily pressure candidates and scorecards
- collect evidence and refine gates
- **no pressure execution automation**

### Stage E — Manual pressure case workflow (time-boxed)
- execute only with Head approval
- log complete pressure cases and outcomes
- target: 20–30 cases before any discussion of partial automation

### Stage F — Eligibility intelligence (A-cycle)
- FOEP + CPT pulls as daily baseline.

### Stage G — Demand ceiling learning (slow)
- enable demand ceiling model in effective-price space with strict stability gating.

### Stage H — DVE learned correction (multiplier)
- enable multiplier learning with strict evidence rules.

### Stage I — Event-led runtime hardening (pre-expansion, mandatory)
Implement as default architecture (not a later enhancement):
- notification intake + per-SKU inbox + dedupe/storm control (`ANY_OFFER_CHANGED`, `PRICING_HEALTH`)
- refresh orchestration queue (urgency + cooldown + drop reasons)
- PRICING_HEALTH risk interrupt path (override/clamp/freeze + OAS hard-fail for learning windows)
- per-call rate-limit logging + global/per-SKU budgets
- low-frequency heartbeat polling fallback (“are we blind?” checks)

Expansion gate (validation window):
- notifications reliable for pilot SKUs
- per-SKU budgets prevent starvation
- pull volume materially reduced vs baseline polling
- no missed PRICING_HEALTH alerts
- eligibility ceiling coverage complete (no null `eligibility_source`; fallbacks reason-coded)

---

## 17) Appendix — Reason Codes (Starter Set)

### Identity / structural integrity
- `OFFER_SNAPSHOT_CREATED`
- `OFFER_VARIANT_CREATED`
- `OFFER_VARIANT_LINKED`
- `FAIL_VARIANT_MAPPING`
- `BLOCK_LEARNING_VARIANT_MAPPING_FAILED`

### Objective / State
- `STATE_MAX_PROFIT`
- `STATE_LOW_NO_COMPETITION`
- `STATE_DEFENSIVE_HOLD`
- `STATE_FLOOR_DISCOVERY`
- `STATE_MAX_SHARE`
- `STATE_PRESSURE_MANUAL`

### Pressure gating
- `PRESSURE_CANDIDATE_DETECTED`
- `PRESSURE_GATE_FAIL_OPPONENT_STRONG`
- `PRESSURE_GATE_FAIL_EXPECTED_GAIN_NONPOSITIVE`
- `PRESSURE_GATE_FAIL_RESOURCE`
- `PRESSURE_GATE_FAIL_CPT_ANCHOR_RISK`
- `PRESSURE_APPROVED_HEAD`
- `PRESSURE_ABORTED_KILL_CONDITION`
- `PRESSURE_EXIT_COMPETITOR_STOCKOUT`
- `PRESSURE_EXIT_COMPETITOR_RETREAT`
- `PRESSURE_EXIT_DELIVERY_SHIFT`
- `PRESSURE_EXIT_TIME_EXPIRY`
- `PRESSURE_COOLDOWN_ACTIVE`

### Ceilings
- `CEIL_COMPLIANCE_APPLIED`
- `CEIL_ELIG_SIGNAL_APPLIED`
- `CEIL_ELIG_MARKET_APPLIED`
- `CEIL_DEMAND_APPLIED`
- `CEIL_MANUAL_CAP_APPLIED`
- `CEIL_FINAL_BOUND_COMPLIANCE`
- `CEIL_FINAL_BOUND_ELIGIBILITY`
- `CEIL_FINAL_BOUND_DEMAND`
- `ELIG_CEILING_FOEP_USED`
- `ELIG_CEILING_CPT_USED`
- `FOEP_MISSING`
- `FOEP_INELIGIBLE_ASIN`
- `FOEP_ERROR`
- `FOEP_SANITY_FAIL`
- `ELIGIBILITY_FALLBACK_USED`
- `ELIG_CEILING_MIN_APPLIED`
- `ELIG_CEILING_OVERRIDDEN_MANUAL`
- `FAIL_CEILING_BELOW_HARD_FLOOR`

### Guardrails / integrity
- `GUARDRAIL_HARD_FLOOR_CLAMP`
- `GUARDRAIL_MAX_STEP_CLAMP`
- `GUARDRAIL_COOLDOWN_BLOCK`
- `MARKET_STRUCTURE_CHANGED_INVALIDATE`
- `WALK_AWAY_LANE_DOWNGRADE`

### Portfolio Governor
- `PORTFOLIO_GOVERNOR_PASS`
- `PORTFOLIO_GOVERNOR_RESTRICTED`
- `PORTFOLIO_GOVERNOR_FAIL`
- `PORTFOLIO_LANE_CHANGED`

### Notifications / Refresh Orchestration
- `NOTIF_EVENT_INGESTED`
- `NOTIF_EVENT_DEDUPED`
- `NOTIF_INBOX_STALE_DEGRADE`
- `REFRESH_REQUEST_CREATED`
- `REFRESH_DROPPED_BUDGET_EXHAUSTED`
- `REFRESH_DROPPED_COOLDOWN_ACTIVE`

### Seller Priority
- `SELLER_PRIORITY_IGNORE`
- `SELLER_PRIORITY_EXPLOIT`
- `SELLER_PRIORITY_NEUTRAL`
- `SELLER_PRIORITY_DEFEND`
- `SELLER_PRIORITY_PRESSURE_CANDIDATE`

### Delivery Value Engine
- `DVE_BASE_CURVE_APPLIED`
- `DVE_MULTIPLIER_APPLIED`
- `DVE_DELIVERY_UNKNOWN_FALLBACK`
- `DVE_MULTIPLIER_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DVE_MULTIPLIER_UPDATED`

### Learning
- `OAS_ADMISSIBLE`
- `OAS_INADMISSIBLE`
- `OAS_HARD_FAIL_STRUCTURE_DRIFT`
- `OAS_HARD_FAIL_SUPPRESSION`
- `OAS_HARD_FAIL_SELF_STOCKOUT`
- `OAS_HARD_FAIL_PRICING_HEALTH_EVENT`
- `OAS_HARD_FAIL_PROMO_CONTAMINATION`
- `OAS_SOFT_DEGRADE_COMPETITOR_DRIFT`
- `OAS_SOFT_DEGRADE_DELIVERY_SHIFT`
- `OAS_SOFT_DEGRADE_BB_ROTATION_NOISE`
- `DELTA_CONSUMER_FALLBACK_LOW_CONFIDENCE`

- `SELLER_DELTA_DRIFT_RELEARN`
- `SELLER_DELTA_UPDATE_BLOCKED_UNSTABLE_MARKET`
- `DEMAND_MODEL_UPDATE_BLOCKED_LOW_CONFIDENCE`
- `DEMAND_MODEL_UPDATED`

---

## 18) v8 Runtime Hardening Rules (Mandatory)

This section is part of the canonical plan. It groups the hard runtime requirements (event-led scheduling, rate limits/budgets, write contracts, and expansion gates).

### 18.1 Outcome Admissibility Layer (core; see §14)
Outcome admissibility is no longer an add-on. It is specified in **§14 (Learning Integrity + Outcome Admissibility)** and is mandatory for any learning update.
All engines that update memory must call OAS and must log `context_quality_score` + reason codes. Any update without an admissibility record is a hard bug.

### 18.2 Event-Led Runtime Contract (required for scale)

**Core rule:** the scheduler must be **event-led by default**. Polling exists only as a heartbeat fallback.

Notifications are treated as a **core dependency** of pricing correctness:
- without them you drift into over-polling, throttling, stale snapshots, and wrong decisions
- scaling without reliable `PRICING_HEALTH` handling is a suppression/eligibility risk

#### 18.2.1 Always-on notification intake
- ingest notifications continuously
- write to an append-only log
- maintain a per-SKU “event inbox”
- dedupe by `(sku, event_type, short_time_window)` to prevent stampedes

#### 18.2.2 Event → refresh orchestration (Supervisor responsibility)
For each SKU with events, decide urgency:
- `now` (immediate)
- `soon` (batch within 15–30m)
- `defer` (batch later)

Apply storm control:
- per-SKU refresh cooldown (“at most 1 refresh per X minutes unless PRICING_HEALTH”)
- batching across SKUs to smooth API usage

#### 18.2.3 Targeted refresh (Executioner responsibility)
On refresh execution:
- pull only the minimum snapshot needed to decide (offers, BB state, delivery posture)
- run the standard H-cycle decision flow for that SKU only

#### 18.2.4 Heartbeat polling fallback (required)
Low-frequency “are we blind?” checks exist to cover:
- missed notifications
- integration outages
- stale inbox health

Heartbeat cadence is lane/state-derived:
- `parked` / ignore lane → 4–8h
- `monitor` → 1–4h
- `duel` / active fight → 15–60m (still event-led; polling is backup)

#### 18.2.5 Trigger mapping (non-negotiable)
- `PRICING_HEALTH`
  - triggers an immediate refresh (`urgency=now`)
  - sets a risk override (`defensive_hold` and/or `parked` depending on severity)
  - may freeze aggressive tactics until cleared
  - hard-fails learning windows in OAS (`OAS_HARD_FAIL_PRICING_HEALTH_EVENT`)
- `ANY_OFFER_CHANGED`
  - triggers targeted refresh with urgency based on cadence profile:
    - `duel` / `wait_out` → `now`
    - `monitor` → `soon`
    - `parked` → ignore unless seller-of-interest re-entry or explicit rule match

#### 18.2.6 Observability outputs (must exist)
Per SKU:
- `notifications_last_seen_utc`
- `event_backlog_age_seconds`
- `event_inbox_depth`
- `refresh_cooldown_until_utc`
Portfolio:
- backlog depth distribution
- dedupe/storm-drop counts
- missed-notification suspected count


### 18.3 API Budget and Rate-Limit Controls (required)

Scaling fails when “refresh everything” hits rate limits and the system silently becomes stale.

#### 18.3.1 Per-call rate-limit observability (mandatory)
Every API call must log:
- timestamp
- endpoint name
- call cost (if applicable)
- SKU that consumed the budget
- remaining quota / burst capacity (from response headers, if available)
- success/fail + error code

#### 18.3.2 Budget model (two layers)
A) **Global budgets**
- protective hard stop when remaining capacity drops below a safety threshold
- priority order under constraint:
  1. `PRICING_HEALTH` handling
  2. high-value SKUs (`portfolio_lane=fight/defend`)
  3. routine refresh for the rest
- when constrained: widen cooldowns, reduce ladder depth, degrade to heartbeat cadence

B) **Per-SKU rolling budgets**
Each SKU gets a budget tier based on lane + volatility:
- passive/ignore: tiny budget
- managed/defend: moderate
- micro-managed/duel: higher but capped

Rule:
- one chaotic SKU must not starve the rest of the catalogue.

#### 18.3.3 Required health checks
- `global_rate_limit_near_exhaustion_flag`
- `calls_used_today_total` and trend
- `calls_used_today_by_sku` distribution (detect “hog” SKUs)
- starvation detection: high-value SKUs not refreshed despite events


### 18.4 Eligibility Fallback Contract (FOEP gaps)

FOEP is useful only if treated as **optional intelligence** with explicit failure modes.
If FOEP disappears and the system treats that as “no ceiling”, the optimiser will:
- overprice into no-sales, or
- panic undercut due to instability.

#### 18.4.1 Eligibility ladder is mandatory
Every SKU must always have:
- `eligibility_ceiling_landed_gbp`
- `eligibility_source`
- `eligibility_confidence`
- `eligibility_reason_codes[]`

Source ladder (strict order) is defined in §8.2.2:
`FOEP → CPT → MANUAL → HIST_WIN → RIVAL_PLUS_DELTA / LAST_KNOWN_SAFE`

#### 18.4.2 FOEP failure modes must be reason-coded
You must explicitly handle:
- FOEP missing
- `ASIN_NOT_ELIGIBLE`
- FOEP sanity check fail
- FOEP stale beyond threshold
- FOEP conflicts with other ceilings (clamp and log)

Missing/invalid FOEP must:
- lower confidence
- switch eligibility_source to a fallback
- never widen price space

#### 18.4.3 Eligibility health checks (required)
- alert if `eligibility_source` is null (must be zero)
- alert if `eligibility_last_refresh_utc` stale beyond threshold
- alert if `foep_last_refresh_utc` stale > 48h **only for SKUs where FOEP is expected**
- daily distribution report: % SKUs by `eligibility_source`
- alert if too many SKUs run on `LAST_KNOWN_SAFE` (suggests upstream signal outage)


### 18.5 Price Write Contract (no silent writes)
No price write is allowed without:
- reason code set
- driving game context (variant/seller pressure or normal optimization context)
- floor/ceiling clamp notes
- confidence score and expiry timestamp
- action type flag (`probe` vs `normal`)

### 18.6 Lane North-Star Metrics (decision discipline)
Mandatory optimization target by lane:
- managed/micro-managed lanes: contribution profit per day with volatility penalty
- passive lane: margin protection + eligibility safety

This prevents "lowest feasible price" drift when seller set complexity increases.

### 18.7 Additional Outputs (minimum)
These outputs are required and are listed in §15. This subsection exists as a reminder that runtime hardening is not optional.

### 18.8 Additional Health Checks
Add health checks for:
- stale notification intake (`notifications_last_seen_utc`)
- event backlog age (`event_backlog_age_seconds`)
- per-SKU budget starvation
- global rate-limit near exhaustion
- inadmissible-outcome update leakage (must be zero)

### 18.9 Expansion Gate Upgrade (supersedes Stage I minimum)
No SKU expansion unless all are true for validation window:
- notifications are reliable for pilot SKUs
- per-SKU budgets prevent starvation
- pull volume reduced versus baseline polling
- no missed pricing health alerts
