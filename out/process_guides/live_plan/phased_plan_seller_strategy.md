# Repricing Engine - Phased Plan (Current -> Seller-Specific Strategy + Safe Autonomy)

Date: 2026-02-14

## Purpose
Deliver a repricer that can run unattended (weekends) and then scale to ~300 SKUs, without rule spillover when conditions change.

Core architecture:
- Listing-level scenario gate decides if the engine is allowed to act.
- Seller/variant-level modelling decides how we act (each competitor is its own behavioural entity).

---

## A) Current state (as of 2026-02-14)

1) Scope
- Single pilot SKU (JB-RGB6-LZOJ) via config/pilot_sku.yaml.
- Decisioning is mostly listing-level; seller-specific policies are not wired yet.

2) Data
- Per-offer snapshots exist (append-only): data/offer_snapshot_facts.csv.
- Execution audit exists: data/execution_log.csv.
- Daily intel refresh exists: scripts/A016_refresh_phase1_daily_intel.py -> data/sku_daily_intel.csv.
- Ceiling events exist: data/sku_ceiling_events.csv.

3) Engine
- State machine: scripts/phase1_probe_engine.py.
- States: HOLD_OBSERVE, REGAIN, RAISE_FIND_LOSS, BRACKET_NARROW, STABLE_WIN.
- Live writes currently OFF (enabled_live_writes=false).

4) Known gaps discovered
- Buy Box suppression can be misclassified as “not ours” if outcome is missing.
- Delivery days may be missing for winner rows; missing must never be treated as 0.

---

## Z) Target end state (portfolio-grade)

Required to call this “production repricer”:
1. A015/A-gate blocks publish on FAIL.
2. Staged publish with verify-after-write; no partial writes.
3. 0 FAIL for 10 consecutive runs.
4. WARN=0 except an explicit exception list (versioned).
5. Rollback support: retain last 3 publish snapshots per SKU.
6. Multi-SKU config model (no hard-coded pricing rules).
7. Seller-specific strategy layer on top of stable scenario gating.

---

## Non-negotiable build order (to avoid corruption)
1) Fix truth signals (suppression/outcome/delivery unknown).
2) Add scenario gate (unknown territory => HOLD).
3) Only then expand learning dimensions (per seller/variant).
4) Only then enable demand-cap learning and multi-SKU rollout.

---

## Design: Scenario Gate (listing-level, data-derived)

The scenario gate must use ONLY existing logged signals (no guesswork). Minimum fields available today:

- buy_box_present:
  - 1 if buy_box_missing_flag == 0 OR buy_box_price is present
  - 0 otherwise

- outcome_known:
  - 1 if unknown_outcome_flag == 0 AND (winner id present OR any row has is_featured_offer_winner==1)
  - 0 otherwise

- we_present:
  - 1 if any row has is_our_offer==1
  - 0 otherwise

- rivals_present:
  - 1 if any row has is_our_offer==0
  - 0 otherwise

Optional (only if reliable in your feed):
- winner_delivery_known:
  - 1 if winner row min_delivery_days is present
  - 0 otherwise

Scenario code (example):
- CODE = buy_box_present outcome_known we_present rivals_present winner_delivery_known
- Stored as a short string, e.g. "11011".
- If you skip winner_delivery_known, CODE is 4 bits, e.g. "1101".

Registry (allow-list):
- config/scenario_registry.yaml mapping CODE -> action_policy.
- Default policy for unknown codes: HOLD (no write, no learning).

---

## Design: Seller/Variant Modelling (per competitor)

Your intended modelling unit is:
- SKU + offer_variant_id (seller_id_canonical + fulfilment_channel + condition + shipping_template proxy)

Minimum seller/variant outputs per cycle:
- direct_competitor_currently (1 for the best rival, else 0)
- best_rival_effective_price, best_rival_landed_price
- per-variant delta bracket memory (when enabled later)

Rule:
- Scenario gate controls whether we act.
- Seller modelling controls how we treat the direct competitor.
- No seller should inherit another seller’s learned bracket.

---

# Phase Ladder (A -> Z)

## Phase 0 (Now): Stabilise truth + safety (no new strategy)

Objective:
- Make the current pilot safe and logically correct before any new tactics.

Work items:
1) Suppression/outcome correctness:
   - If Buy Box is missing (buy_box_missing_flag=1 OR unknown_outcome_flag=1), outcome must be UNKNOWN.
   - UNKNOWN outcome must route to HOLD_OBSERVE (not REGAIN).
   - Learning must be blocked in these windows.

2) Delivery unknown correctness:
   - Missing min_delivery_days must remain NULL/unknown (never 0).
   - If winner delivery is unknown, DVE should go neutral for the cycle (effective=landed), or the cycle should HOLD. Pick one and log it.

3) Health hygiene:
   - FAIL must be 0 before enabling writes.
   - WARN must be reviewed and either fixed or placed on a short explicit exception list.

Deliverables:
- Execution log shows reason codes like OUTCOME_UNKNOWN_HOLD when suppression/outcome missing.
- No delta updates occur during suppression.

Exit criteria:
- 10 consecutive pilot runs with FAIL=0.
- At least 1 suppression period correctly classified as UNKNOWN/HOLD.

---

## Phase 1: Scenario Gate (unknown territory => HOLD)

Objective:
- Stop rules from spilling across conditions by introducing a hard allow-list.

Work items:
1) Implement scenario code generation per snapshot.
2) Add config/scenario_registry.yaml with an allow-list.
3) Enforce:
   - If CODE is not allow-listed: HOLD (no write, no learning).
4) Log per cycle:
   - scenario_code
   - scenario_policy (ALLOWED/HOLD_UNKNOWN)
   - scenario_block_reason (if held)
5) Temporary day guideline (Phase 1 ceiling/floor policy):
   - Temporary ceiling:
     - `temp_ceiling_gbp = min(cpt_gbp * 1.20, max_sold_price_gbp)`
     - `max_sold_price_gbp` must be GBP-only and same marketplace.
   - Temporary floor:
     - `temp_floor_gbp = all_costs_gbp + (cogs_gbp * 0.10)`
     - Equivalent to a 10% ROI on COG for day-level protection.
   - Enforcement:
     - If CPT is missing, HOLD (no write).
     - If `temp_ceiling_gbp < temp_floor_gbp`, HOLD and log reason.
   - Scope:
     - This is a temporary Phase 1 policy for current operations and must be replaced by the planned demand/seller-model logic in later phases.

Recommended starting allow-list (very conservative):
- Only allow “normal competition with measurable outcome”:
  - buy_box_present=1, outcome_known=1, we_present=1, rivals_present=1 (and winner_delivery_known=1 if used)
- Everything else holds.

Deliverables:
- New log column(s) in execution_log.csv (or a sidecar table) summarising scenario gating.
- A daily rollup: out/scenario_code_distribution.csv.

Exit criteria:
- Unknown scenario codes do not cause writes or learning.
- You can point to the top 5 scenario codes by frequency.

---

## Phase 1.5: Suppression Telemetry (reporting, not recovery)

Objective:
- Treat suppression as a ceiling observation input for Head, without mixing it into competitor learning.

Work items:
1) Add data/suppression_events.csv with:
   - suppression_start_ts, suppression_end_ts (if observed)
   - trigger_price (our price at start)
   - clear_price (first price where buy box returns, if writes enabled)
   - snapshot ids used
2) Add out/suppression_daily_summary.csv for Head:
   - last suppression event time
   - last clear_price (if known)
   - suggested cap warning band

Rule:
- Suppression events never update delta brackets.

Exit criteria:
- Suppression is visible as data, not guessed from UI screenshots.

---

## Phase 2: Seller Identity Layer (data only)

Objective:
- Start treating each competitor as its own entity without changing tactics yet.

Work items:
1) Ensure offer_variant_id stability (variant mapping audit).
2) Create/extend a table (choose one):
   - data/offer_variants.csv (extend with “profile” columns), OR
   - data/seller_variant_profiles.csv (new).
3) Populate per variant:
   - seller_id_canonical, fulfilment_channel, first_seen, last_seen
   - delivery median/typical (if available)
   - promo suspected flag
   - direct_competitor_currently flag (best rival in this snapshot)

Exit criteria:
- For each H-cycle, exactly one rival variant is flagged direct_competitor_currently (when rivals exist).
- Profiles update without breaking snapshot append-only rules.

---

## Phase 3: Per-Seller Delta Learning + Basic Tactics (bounded)

Objective:
- Learn delta per competitor variant, while keeping decision logic simple.

Work items:
1) Change delta memory key from BEST_RIVAL to offer_variant_id (direct competitor at probe start).
2) Only update the delta bracket for that offer_variant_id when OAS admissible + outcome known.
3) Add basic seller tags (derived, not manual):
   - fast_chaser vs slow_chaser vs non_reactive (based on observed reaction time)
4) Use tags only to adjust guardrails (not objectives yet):
   - step sizes
   - cooldown length
   - probe window length

Exit criteria:
- Brackets converge for at least 1 competitor variant.
- No cross-variant contamination (one seller’s bracket does not move when another seller is the direct competitor).

---

## Phase 4: Demand Cap Learning (replace manual “Head cap” gradually)

Objective:
- Start removing the human ceiling safely.

Work items:
1) Add a demand model table (data/demand_model.csv):
   - demand_ceiling_effective_gbp
   - demand_confidence
   - model_version
2) Add SKU autonomy states:
   - BOOTSTRAP -> LEARNING -> AUTONOMOUS
3) Use SNL vs STANDARD segmentation before expanding beyond pilot cohort.
4) Incorporate suppression telemetry as a confidence brake:
   - repeated suppression above X lowers cap confidence and pulls ceiling down.

Exit criteria:
- At least a small set of SKUs (high volume) reaches LEARNING with stable behaviour.
- Manual cap remains as a safety belt until confidence threshold.

---

## Phase 5: Multi-SKU Rollout + Production Controls

Objective:
- Scale safely: 1 -> 10 -> 50 -> 300.

Work items:
1) Multi-SKU config model (per-SKU boundaries + segmentation tag).
2) Budgets + cooldowns enforced per SKU.
3) Staged publish + verify-after-write + rollback snapshots.
4) Expansion gate:
   - 10 clean runs (FAIL=0) in the current cohort before adding more SKUs.

Exit criteria:
- Meets all “Target end state” items (Z).
- Rollback drill proven.

---

## Weekend-safe operating mode (if you need to run unattended early)
- Scenario gate allow-list is strict (unknown => HOLD).
- enabled_live_writes can stay false until Phase 0 + Phase 1 are clean.
- If enabling writes for the pilot:
  - max_writes_per_day low
  - verify-after-write mandatory
  - auto-switch to HOLD on any verify mismatch or suppression/outcome unknown.
