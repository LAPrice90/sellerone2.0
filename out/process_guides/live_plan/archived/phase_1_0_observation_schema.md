# Phase 1.0 - Observation Schema Lock

Status: Locked v1.0 (2026-02-09)
Phase: 1 - Competition Observation and Behaviour Memory
Owner: Human-defined, Codex-executed
Scope: Schema definition only (no logic, no thresholds)

---

## 1. Purpose

This document defines the observation schema for competitive behaviour memory.

It answers one question only:

What facts about sellers, offers, time, and delivery do we want to remember so future decisions can be explained and improved?

This phase:
- does NOT define thresholds
- does NOT define strategies
- does NOT classify sellers
- does NOT trigger actions

It defines memory only.

---

## 2. Core Rules (Non-Negotiable)

1. Observation only
- No scoring
- No judgement
- No if-X-then-Y rules

2. Symmetric tracking
- All sellers are observed with the same schema
- Includes our own account

3. Append-only mindset
- History is never overwritten
- New facts are added over time

4. Buyer-visible reality
- Record what buyers can see
- Do not store internal assumptions as facts

5. Time is first-class
- Every observation must include timestamp_utc and asof_date
- Duration is measured from observed timestamps, not guessed

---

## 3. Observation Domains and Field Contracts

Field table columns:
- field: canonical field name
- type: storage type
- null: YES or NO
- unit_or_values: measurement unit or allowed values
- notes: contract detail

### 3.1 Time and Presence Signals

Purpose:
Capture when sellers appear, persist, leave, and return.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| timestamp_utc | datetime (ISO-8601 UTC) | NO | UTC timestamp | Capture timestamp for record creation |
| asof_date | date (YYYY-MM-DD) | NO | Date | Daily idempotency key component |
| seller_seen_flag | int | NO | 0 or 1 | 1 when seller appears in offer set |
| first_seen_timestamp | datetime | YES | UTC timestamp | Earliest observed timestamp for seller+sku |
| last_seen_timestamp | datetime | YES | UTC timestamp | Latest observed timestamp for seller+sku |
| continuous_presence_hours | float | YES | hours | Duration since last re-entry |
| absence_gap_hours | float | YES | hours | Gap between prior last_seen and re-entry |
| reentry_after_absence_flag | int | YES | 0 or 1 | 1 when absence gap exists then seller returns |

### 3.2 Seller Price Behaviour

Purpose:
Capture how far sellers move on price over time.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| offer_price_gbp | float | YES | GBP | Seller visible offer price |
| min_price_seen_gbp | float | YES | GBP | Rolling minimum for seller+sku window |
| max_price_seen_gbp | float | YES | GBP | Rolling maximum for seller+sku window |
| median_price_seen_gbp | float | YES | GBP | Rolling median for seller+sku window |
| time_at_min_price_hours | float | YES | hours | Total observed hours at min price |
| time_at_max_price_hours | float | YES | hours | Total observed hours at max price |

### 3.3 Seller Interaction Signals

Purpose:
Capture who moves first and who reacts.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| price_move_initiations | int | YES | count | Number of first moves observed |
| follow_events | int | YES | count | Number of observed follow moves |
| reaction_lag_minutes | float | YES | minutes | Delay from first move to follow move |
| directional_bias | string | YES | up/down/flat | Dominant move direction in window |
| floor_set_events | int | YES | count | Times seller establishes observed low anchor |

### 3.4 Delivery and Fulfilment Signals

Purpose:
Capture non-price competitiveness buyers can see.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| min_delivery_days | int | YES | days | Fastest delivery promise observed |
| max_delivery_days | int | YES | days | Slowest delivery promise observed |
| delivery_range_days | int | YES | days | max minus min |
| is_prime | int | YES | 0 or 1 | Prime badge presence |
| delivery_delta_vs_fastest_days | int | YES | days | Seller promise minus fastest observed |
| fulfilment_channel | string | YES | FBA/FBM/Unknown | Buyer-visible channel |

### 3.5 Market Context Signals (Lightweight)

Purpose:
Provide minimal context without strategy.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| offer_count_total | int | YES | count | offer_count_fba + offer_count_fbm |
| offer_count_fba | int | YES | count | Count of FBA offers |
| offer_count_fbm | int | YES | count | Count of FBM offers |
| buy_box_presence_flag | int | YES | 0 or 1 | 1 if buy box price is present |
| buy_box_channel | string | YES | FBA/FBM/Unknown | Channel of observed buy box |
| volatility_proxy | float | YES | index | Placeholder for observed movement intensity |

### 3.6 Our Own Behaviour Tracking

Purpose:
Ensure future automation is explainable.

| field | type | null | unit_or_values | notes |
|---|---|---|---|---|
| our_price | float | YES | GBP | Our visible offer price |
| our_price_changes | int | YES | count | Number of our price changes in window |
| our_delivery_posture | string | YES | fast/parity/slow | Relative delivery stance |
| manual_interventions | int | YES | count | Human-in-the-loop adjustments |
| intent_notes | string | YES | free text | Context annotation, no judgement |

---

## 4. Source Mapping (Current vs Needed)

Current observed sources:
- `out/listing_offer_snapshot_YYYY-MM-DD.csv`
- `out/listing_offer_history.csv`
- `out/inventory_history.csv`
- `out/inbound_history.csv`
- `out/refund_adjustment_history.csv`

Current script owners:
- `run_api_collection.py`
- `scripts/H001_capture_offer_snapshot.py`
- `scripts/A003_run_inventory_to_sheet.py`
- `scripts/A015_build_system_health_check.py`

Mapping status:

### 4.1 Section 3 Field Status Matrix (explicit lock matrix)

Status values:
- `captured` = direct from upstream collection outputs
- `derived` = computed in Phase 1 aggregation
- `deferred_null` = explicit blank/null contract in Phase 1, reserved for later phases

| field | status | source owner | contract path |
|---|---|---|---|
| timestamp_utc | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| asof_date | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| seller_seen_flag | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| first_seen_timestamp | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| last_seen_timestamp | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| continuous_presence_hours | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| absence_gap_hours | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| reentry_after_absence_flag | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| offer_price_gbp | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| min_price_seen_gbp | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| max_price_seen_gbp | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| median_price_seen_gbp | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| time_at_min_price_hours | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| time_at_max_price_hours | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| price_move_initiations | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| follow_events | deferred_null | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` (blank by contract) |
| reaction_lag_minutes | deferred_null | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` (blank by contract) |
| directional_bias | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| floor_set_events | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| min_delivery_days | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| max_delivery_days | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| delivery_range_days | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| is_prime | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| delivery_delta_vs_fastest_days | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| fulfilment_channel | captured | `run_api_collection.py` | `out/listing_offer_seller_observation_history.csv`, `out/phase1_seller_history.csv` |
| offer_count_total | deferred_null | `run_api_collection.py` + `scripts/H002_build_phase1_seller_history.py` | not yet materialized in Phase 1 output |
| offer_count_fba | captured | `run_api_collection.py` | `out/listing_offer_snapshot_YYYY-MM-DD.csv`, `out/listing_offer_history.csv` |
| offer_count_fbm | captured | `run_api_collection.py` | `out/listing_offer_snapshot_YYYY-MM-DD.csv`, `out/listing_offer_history.csv` |
| buy_box_presence_flag | deferred_null | `run_api_collection.py` + `scripts/H002_build_phase1_seller_history.py` | not yet materialized in Phase 1 output |
| buy_box_channel | captured | `run_api_collection.py` | `out/listing_offer_snapshot_YYYY-MM-DD.csv`, `out/listing_offer_history.csv` |
| volatility_proxy | deferred_null | reserved for later phase | not yet materialized in Phase 1 output |
| our_price | captured | `run_api_collection.py` | `out/listing_offer_history.csv`, `out/phase1_seller_history.csv` |
| our_price_changes | derived | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` |
| our_delivery_posture | deferred_null | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` (blank by contract) |
| manual_interventions | deferred_null | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` (blank by contract) |
| intent_notes | deferred_null | `scripts/H002_build_phase1_seller_history.py` | `out/phase1_seller_history.csv` (blank by contract) |

Root-cause note:
- Missing fields are upstream capture gaps, not formatting gaps. They must be added at data collection and history aggregation layers, not patched in downstream reports.

---

## 5. Explicit Exclusions (Phase Guardrails)

Phase 1.0 explicitly excludes:
- thresholds
- seller role classification
- lane selection
- profit calculations
- buy box probability modelling
- automation actions

Any concept requiring these belongs to later phases.

---

## 6. Completion Criteria (Lock Conditions)

Phase 1.0 is complete when all are true:
- Every field in Section 3 has a named source or explicit "not yet captured" state.
- A015 has schema checks for all new Phase 1.0 outputs (required columns plus type checks).
- Collection and history writes are append-safe and idempotent by `asof_date+sku+marketplace`.
- No Phase 1 field requires Codex to infer meaning from ambiguous names.

Phase 1.0 lock event:
- Status updated to `Locked v1.0`.
- Runbook references updated.
- Evidence run attached in ticket notes before logging.

---

## 7. Lock Evidence (2026-02-09)

Evidence source:
- Existing cycle artifacts only (no ad-hoc A run)

Proof points:
- `out/B_cycle.log` includes `health_gate snapshot FAIL=0 WARN=0` at 2026-02-09T16:06:31Z.
- `out/system_health_checklist.csv` includes:
  - `h_schema_phase1_seller_history,ok,ok`
  - `h_phase1_contract_types,ok,0`
  - `h_phase1_history_idempotent,ok,0`
- Field status matrix in Section 4.1 is complete with explicit `captured`, `derived`, or `deferred_null` state for each Phase 1 field.
- Field names and contracts are explicit in Section 3 and do not require inference.

---

## 8. Open Questions (Deferred to Phase 2+)

- How long must behaviour persist before it matters?
- Which signals correlate most with profit per day?
- How much delivery disadvantage can price advantage offset?
- When does behaviour generalize across SKUs?

These are Phase 2+ questions.
