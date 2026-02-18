# Phase 1 Execution Spec (Repaired and Pinned)

Status: Draft for implementation
Date: 2026-02-13
Scope: Documentation repair and implementation pinning only

## 1) Scope / Goals
Phase 1 builds a single-SKU live repricing lab that can:
- Write real price changes.
- Observe market reaction.
- Learn a bracket for effective-price delta needed to win featured offer.
- Hold the highest known winning price inside floor and ceiling clamps.
- Log every decision with reason codes and OAS outcome.

Phase 1 is intentionally limited. It does not include portfolio scaling, notification-led runtime, pressure execution, or advanced demand learning.

In scope:
- single writer enforcement
- append-only snapshots
- stable variant identity
- DVE v0 effective price
- compliance + eligibility + manual demand proxy ceilings
- probe state machine and bracket learning
- minimal strict OAS hard-fails
- price write and deterministic write verification

Out of scope:
- notification intake and API budget orchestration
- DVE multiplier learning
- demand model learning
- portfolio governor lane logic
- pressure mode execution

## 2) Preconditions / Safety (single writer)
Pilot SKU preconditions:
- stable stock and no expected stockout during probe windows
- no known MAP or policy constraints that block repricing
- active competition present often enough to observe outcomes

Writer lock is mandatory:
- `pricing_writer_mode` must be `CODEX_H` for pilot SKU.
- PPP must not write this SKU while Phase 1 runs.
- If writer mode is not `CODEX_H`, H-cycle exits immediately and logs `WRITER_LOCK_BLOCK`.

Failsafe:
- `enabled_live_writes=false` forces read-only operation.
- Any repeated invariant failure can auto-switch to read-only.

## 3) SP-API endpoints (pinned choices)
### 3.1 Primary market snapshot source
Pinned primary source: Product Pricing API `getCompetitiveSummary`.

Required extracted fields per offer row:
- `seller_id_raw`
- `fulfilment_channel` (FBA/FBM/Amazon where available)
- `listing_price_gbp`
- `shipping_gbp`
- `landed_price_gbp` (computed if source does not provide it)
- `min_delivery_days`
- `max_delivery_days`
- `condition`
- `is_prime` (nullable)
- `is_featured_offer_winner` (nullable)
- `is_our_offer`

Required outcome fields:
- `featured_offer_winner_seller_id` (nullable)
- `featured_offer_price_gbp` (nullable)

Fallback handling for missing fields:
- set field to `null`
- set corresponding `unknown_*` flag(s)
- if featured outcome fields are missing, do not run learning update for that window

### 3.2 Daily intelligence reads
- FOEP and CPT are pulled daily (A-cycle) from SP-API pricing intelligence endpoints.
- CPT source is Product Pricing API v2022-05-01 competitive summary response reference prices.
- CPT is nullable and reason-coded (`cpt_status` and reason codes in daily intel row).
- CPT is never derived from buy box price and never taken from YAML fallback values.
- Eligibility source ladder is always resolved and stored.

### 3.3 Write endpoint (pinned)
Pinned write method for Phase 1: Listings Items API `patchListingsItem`.

High-level payload contract:
- target: one SKU, one marketplace
- patch operation updates the listing price attribute only
- include schedule/price object required by current Listings schema

Success criteria:
- HTTP/API response accepted
- then separate verification check confirms applied price (Section 9)

Failure criteria:
- request rejected, timeout, or schema error
- response accepted but verification fails (`WRITE_NOT_APPLIED`)

## 4) Config schema
Minimum config for Phase 1:

```yaml
sku: "YOUR_SKU"
asin: "YOUR_ASIN"
marketplace_id: "YOUR_MARKETPLACE_ID"
seller_id: "YOUR_SELLER_ID"

pricing_writer_mode: "CODEX_H"
enabled_live_writes: true

economics:
  unit_cost_gbp: 0.00
  fees_gbp: 0.00
  refund_buffer_gbp: 0.00

boundaries:
  hard_floor_gbp: 0.00
  soft_floor_gbp: 0.00
  manual_cap_gbp: 9999.99
  policy_buffer_pct: 0.03

cadence:
  h_cycle_minutes: 15
  probe_window_minutes: 20
  post_write_settle_minutes: 5
  cooldown_minutes: 30
  max_writes_per_day: 6

guardrails:
  max_step_down_gbp: 0.20
  max_step_up_gbp: 0.20
  max_daily_drop_gbp: 0.60
  price_apply_tolerance_gbp: 0.01

dve:
  curve_version: "v0"
  penalty_by_gap_days: [0.00, 0.15, 0.30, 0.45, 0.60]

eligibility:
  foep_refresh_hours: 24
  foep_stale_hours: 48
  foep_sanity_min_mult: 0.50
  foep_sanity_max_mult: 2.00

learning:
  delta_tolerance_gbp: 0.02
  stable_buffer_gbp: 0.02
  min_clean_tests_for_confidence: 5
```

## 5) Data model (CSV tables)
Each table is required. Snapshot data is append-only.

### 5.1 offer_snapshot_facts
Purpose: raw per-offer snapshot facts at each observed timestamp.

Minimum columns:
- `offer_snapshot_id` TEXT PRIMARY KEY
- `snapshot_ts_utc` TEXT
- `sku` TEXT
- `asin` TEXT
- `marketplace_id` TEXT
- `seller_id_raw` TEXT
- `seller_id_canonical` TEXT
- `offer_variant_id` TEXT
- `fulfilment_channel` TEXT NULL
- `condition` TEXT NULL
- `listing_price_gbp` REAL NULL
- `shipping_gbp` REAL NULL
- `landed_price_gbp` REAL NULL
- `min_delivery_days` INTEGER NULL
- `max_delivery_days` INTEGER NULL
- `is_prime` INTEGER NULL
- `is_featured_offer_winner` INTEGER NULL
- `is_our_offer` INTEGER NOT NULL
- `promo_suspected_flag` INTEGER NOT NULL DEFAULT 0
- `unknown_outcome_flag` INTEGER NOT NULL DEFAULT 0

### 5.2 offer_variants
Purpose: stable structural offer identity.

Minimum columns:
- `offer_variant_id` TEXT PRIMARY KEY
- `sku` TEXT
- `seller_id_canonical` TEXT
- `fulfilment_channel` TEXT NULL
- `condition` TEXT NULL
- `shipping_template` TEXT
- `variant_first_seen_utc` TEXT
- `variant_last_seen_utc` TEXT
- `variant_active_flag` INTEGER NOT NULL DEFAULT 1

### 5.3 sku_daily_intel
Purpose: daily A-cycle intelligence for ceilings.

Minimum columns:
- `date_utc` TEXT
- `sku` TEXT
- `foep_price_gbp` REAL NULL
- `foep_status` TEXT
- `foep_last_refresh_utc` TEXT NULL
- `cpt_gbp` REAL NULL
- `cpt_last_refresh_utc` TEXT NULL
- `cpt_status` TEXT
- `eligibility_ceiling_landed_gbp` REAL
- `eligibility_source` TEXT
- `eligibility_confidence` REAL
- `eligibility_reason_codes_json` TEXT
- `compliance_ceiling_landed_gbp` REAL
- `compliance_confidence` REAL
- PRIMARY KEY (`date_utc`, `sku`)

### 5.4 sku_ceiling_events
Purpose: per H-cycle ceiling computation trace.

Minimum columns:
- `event_ts_utc` TEXT
- `sku` TEXT
- `our_delivery_penalty_gbp` REAL
- `compliance_ceiling_landed_gbp` REAL
- `eligibility_ceiling_landed_gbp` REAL
- `demand_ceiling_landed_gbp` REAL
- `final_ceiling_landed_gbp` REAL
- `binding_ceiling_type` TEXT
- `ceiling_reason_codes_json` TEXT

### 5.5 variant_delta_memory
Purpose: learned bracket memory in effective-price space.

Phase 1 keying rule:
- Keep one learning memory object per SKU against the current best rival.
- Use fixed key `rival_key="BEST_RIVAL"` for all Phase 1 updates.
- Do not key Phase 1 delta memory by every observed `offer_variant_id`.
- Variant-level delta learning is deferred to later phases.

Minimum columns:
- `sku` TEXT
- `rival_key` TEXT
- `learned_delta_effective_gbp` REAL NULL
- `highest_delta_win_effective_gbp` REAL NULL
- `lowest_delta_loss_effective_gbp` REAL NULL
- `delta_confidence` REAL
- `valid_test_count` INTEGER
- `contaminated_test_count` INTEGER
- `last_valid_test_utc` TEXT NULL
- PRIMARY KEY (`sku`, `rival_key`)

### 5.6 execution_log
Purpose: decision and write audit trail.

Minimum columns:
- `event_ts_utc` TEXT
- `sku` TEXT
- `state` TEXT
- `old_price_gbp` REAL NULL
- `new_price_gbp` REAL NULL
- `write_status` TEXT
- `write_error` TEXT NULL
- `final_ceiling_landed_gbp` REAL
- `hard_floor_gbp` REAL
- `reason_codes_json` TEXT

### 5.7 probe_windows
Purpose: action-reaction windows and outcomes.

Minimum columns:
- `probe_id` TEXT PRIMARY KEY
- `sku` TEXT
- `state_at_start` TEXT
- `start_ts_utc` TEXT
- `end_ts_utc` TEXT NULL
- `start_snapshot_id` TEXT
- `end_snapshot_id` TEXT NULL
- `start_featured_seller_id` TEXT NULL
- `end_featured_seller_id` TEXT NULL
- `observed_outcome` TEXT NULL
- `market_structure_hash_start` TEXT
- `market_structure_hash_end` TEXT NULL
- `oas_result` TEXT

### 5.8 oas_log
Purpose: explicit admissibility decision per probe window.

Minimum columns:
- `event_ts_utc` TEXT
- `probe_id` TEXT
- `sku` TEXT
- `context_quality_score` REAL
- `admissible_flag` INTEGER
- `hard_fail_reason_codes_json` TEXT
- `notes` TEXT NULL

## 6) Runtime loops (A-cycle + H-cycle)
### 6.1 A-cycle (daily)
Steps:
1. Pull FOEP and CPT.
2. Compute compliance ceiling.
3. Resolve eligibility source ladder:
   `FOEP -> CPT -> MANUAL -> LAST_KNOWN_SAFE`.
4. Persist `sku_daily_intel`.
5. Assert `eligibility_source` is never null.

If FOEP is missing or invalid:
- lower confidence
- reason-code fallback
- do not widen price space

### 6.2 H-cycle (every 15 minutes)
Steps:
1. Enforce writer lock. If not `CODEX_H`, exit.
2. Snapshot market using pinned source.
3. Build/refresh `offer_variant_id` and save append-only rows.
4. Compute DVE v0 effective prices.
5. Compute per-cycle final ceiling:
   `min(compliance, eligibility, demand_proxy_manual_cap)`.
6. Resolve probe state (Section 7).
7. If write needed and allowed, execute write.
8. Verify write applied (Section 9).
9. After probe window, resnapshot and run OAS (Section 8).
10. Update `variant_delta_memory` only if OAS admissible and outcome measurable.

Rule for missing featured-offer outcome:
- move to `HOLD_OBSERVE`
- block learning update

## 7) Probe engine (state machine + transitions)
States:
- `HOLD_OBSERVE`
- `REGAIN`
- `RAISE_FIND_LOSS`
- `BRACKET_NARROW`
- `STABLE_WIN`

Best rival definition (Phase 1):
- `best_rival_effective_price_gbp = min(effective_price_gbp_i for offers where is_our_offer=0)`.
- If no rival offer exists in the snapshot, move to `HOLD_OBSERVE`, do not probe, and do not update delta memory.

Featured-offer ownership evaluation:
- `featured_is_ours = (featured_offer_winner_seller_id == our_seller_id) OR (exists row where is_our_offer=1 and is_featured_offer_winner=1)`.
- If both sources are missing or null, outcome is `unknown`.
- If outcome is `unknown`, force `HOLD_OBSERVE` and block learning update.

Transition rules:
- if featured offer is not ours: `REGAIN`
- if featured offer is ours and no loss bound exists: `RAISE_FIND_LOSS`
- if both bounds exist and `(lowest_loss - highest_win) > delta_tolerance`: `BRACKET_NARROW`
- if both bounds exist and `(lowest_loss - highest_win) <= delta_tolerance`: `STABLE_WIN`
- if featured outcome unknown at any step: `HOLD_OBSERVE` and block learning update

Step rules:
- `REGAIN`: decrease price by up to `max_step_down_gbp` while respecting floor and daily drop cap.
- `RAISE_FIND_LOSS`: increase price by up to `max_step_up_gbp` while respecting ceiling.
- `BRACKET_NARROW`: binary midpoint between bounds.
- `STABLE_WIN`: hold at `highest_delta_win - stable_buffer_gbp`.

Cadence rules:
- enforce `cooldown_minutes` between writes
- enforce `max_writes_per_day`
- no second write in same cycle if previous write failed verification

## 8) OAS (Phase 1 hard-fail invariants)
### 8.1 Hard fail list (context_quality_score = 0)
Phase 1 hard-fail conditions:
- market structure changed materially between probe start and end
- our offer not purchasable, but only when `our_purchasable_flag` is reliably available
- pricing health or suppression detected (if detectable)
- promo/coupon suspected flag active (if detectable)
- writer conflict detected (external or PPP write)
- featured outcome measurement missing

Writer conflict detector for Phase 1:
- If we did not submit a write in the last cycle, and verified our price changed, set `writer_conflict_flag=1`.
- Allowlist exception: if the change matches an approved manual override list, do not set conflict.
- If `writer_conflict_flag=1`, OAS hard-fail applies and learning is blocked.

Purchasable/stockout detector for Phase 1:
- If Listings read can provide a reliable purchasable/active signal, map it to `our_purchasable_flag`.
- If `our_purchasable_flag` is not available reliably, disable this hard-fail check in Phase 1 (do not guess stockout).

If any hard fail is true:
- `admissible_flag = 0`
- no learning update

### 8.2 market_structure_hash definition
Use only:
- set of `offer_variant_id` present in snapshot (including ours)
- `offer_count`
- fulfilment distribution (if available)

Explicitly exclude:
- prices
- promo flags
- featured winner identity

## 9) Price write + verification
Verification source of truth order:
1. Wait `post_write_settle_minutes`.
2. Primary verification: Listings Items read for our SKU and marketplace.
3. Fallback verification: detect our offer in latest market snapshot and read our landed/listing price.

Pre-write hard-floor reassertion:
- Before every write, if `proposed_price_gbp < hard_floor_gbp`, set `proposed_price_gbp = hard_floor_gbp`.
- Add reason code `GUARDRAIL_HARD_FLOOR_CLAMP` when this clamp is applied.

Applied criteria:
- `abs(observed_price_gbp - intended_price_gbp) <= price_apply_tolerance_gbp`

If not applied:
- log `WRITE_NOT_APPLIED`
- mark probe as not started
- block additional writes until next cycle cooldown point

If applied:
- open probe window and proceed to reaction observation

## 10) Storage and outputs
Storage boundary (Phase 1):
- Persistent operational tables are stored in `data/` as CSV files.
- `data/` is the durable source of truth for reruns and learning state.

Required persistent CSV tables (`data/`):
- `data/offer_snapshot_facts.csv`
- `data/offer_variants.csv`
- `data/daily_intel.csv`
- `data/ceiling_events.csv`
- `data/variant_delta_memory.csv`
- `data/execution_log.csv`
- `data/probe_windows.csv`
- `data/oas_log.csv`

Optional report/export CSV outputs (`out/`):
- `out/` is for shareable summaries and study outputs.
- Export files in `out/` must be derived from `data/`, not treated as the operational source of truth.

## 11) Definition of Done / Acceptance Criteria
Phase 1 is done only when all are true:
1. Single writer enforcement is active for pilot SKU.
2. Snapshot rows are append-only and variant IDs remain stable.
3. Effective price is computed each H-cycle with DVE v0.
4. Ceilings are computed and clamped each cycle.
5. System can perform a controlled write, verify apply, then observe reaction.
6. Probe windows are logged with start/end snapshots and OAS decision.
7. Delta bracket converges, or learning is correctly blocked when outcomes are unavailable.
8. No floor breach, no write storm, and no uncontrolled downward moves.

Implementation gate:
- Do not begin coding until this document is accepted as the Phase 1 execution source.
