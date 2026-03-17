# Repricer Runtime Contract

## Purpose

This document is the canonical description of the repricer as it actually runs today.

It exists to define:
- current live repricer behavior
- the current runtime decision contract
- the current data and config boundaries
- the current points of known document-versus-code drift

This file describes the live runtime system, not the target future architecture.

Related governance:
- Current live contract lineage reference: `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- Target architecture reference: `out/process_guides/repricing_tool/master plans/masterplan_v10.md`
- Historical implementation reference: `out/process_guides/repricing_tool/master plans/Phased execution/phase_1.md`

## Runtime Architecture

The live repricer runs inside H flow and uses A flow to prepare daily repricer inputs.

Primary implementation files:
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/flows/A/A018_build_phase1_floor_table.py`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_phase_engine.py`
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_ceilings.py`
- `scripts/phase1/phase1_write_gate.py`
- `scripts/phase1/phase1_sku_scope.py`
- `scripts/phase1/phase1_storage.py`

Operational model:
- A flow prepares daily repricer intelligence and floor data.
- H flow loads the current canonical SKU scope.
- H flow filters scope to active, in-stock, non-parked targets.
- H flow collects market and own-offer context for each target SKU.
- H flow runs the phase-aware pricing decision path.
- H flow applies live write gating before any Amazon price write.
- H flow records decision, execution, ceiling, probe, phase, and suppression state.
- H flow builds and publishes the repricer observation view.

The repricer is therefore not a separate microservice. It is an H-owned runtime subsystem with A-owned preparation steps.

## Execution Model

### A-Cycle Preparation

The A-side repricer preparation is built primarily by:
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/flows/A/A018_build_phase1_floor_table.py`

A preparation behavior:
- refreshes or rebuilds `sku_daily_intel`
- computes daily repricer ceilings and stores ceiling-source diagnostics
- builds the latest floor table and runtime floor snapshots used by H
- uses current scope and stock-aware inputs rather than a single-SKU-only path

Important input families used by A-side repricer prep include:
- `out/inventory_summaries.csv`
- latest `out/inventory_snapshot_*.csv`
- `out/parking/stock_snapshot_latest.csv`
- listing and market snapshots
- floor and fee inputs

### H-Cycle Execution

The H-side repricer execution path is built primarily by:
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `scripts/phase1/phase1_main_loop.py`

H execution behavior:
- loads canonical scope from `out/phase1_sku_scope.csv`
- resolves stock candidates and filters non-target rows
- enriches rows with floor, market, inventory, and seller context
- runs the phase-aware decision engine in `phase1_main_loop.py`
- evaluates write permission through `phase1_write_gate.py`
- writes decision and execution artifacts
- emits suppression truth and observation outputs

### Runtime Decision Chain

The live decision chain is:
1. A-side daily intel and floor data are available for the SKU.
2. H loads the canonical scope row for the SKU.
3. H confirms the SKU is in-scope, active enough to monitor, and not parked out of stock.
4. H collects market snapshot rows, our own offer state, floor truth, and stock context.
5. `phase1_main_loop.py` evaluates daily-intel freshness.
6. `phase1_main_loop.py` resolves compliance, eligibility, suppression, and final ceilings.
7. `phase1_main_loop.py` evaluates phase state and phase behavior profile.
8. `phase1_probe_engine.py` selects the decision state and next-price behavior.
9. `phase1_write_gate.py` evaluates whether live writing is allowed.
10. `phase1_main_loop.py` applies an additional writer lock requiring `CODEX_H`.
11. If still allowed, H attempts the listing price write and post-write verification.
12. H persists runtime logs and dashboard outputs.

## SKU Scope Model

### How SKUs Enter Scope

Canonical scope is built by `scripts/phase1/phase1_sku_scope.py` and written to:
- `out/phase1_sku_scope.csv`

Scope is built from the union of:
- `out/product_db_preview.csv`
- `out/merchant_listings_latest.csv`
- latest `out/listing_offer_snapshot_*.csv`

The live target-universe configuration in `config/pilot_sku.yaml` currently uses:
- `target_universe_mode: active_merchant`

Supported target-universe modes in code include:
- `active_merchant`
- `scope_non_parked`
- `lab_cohort`
- `single_sku`

The live system is therefore multi-SKU, not single-SKU.

### How SKUs Become Write-Enabled

Scope rows include:
- `repricing_enabled`
- `observe_enabled`
- `write_enabled`
- `observe_effective`
- `write_effective`
- `writer_mode`
- `parked_flag`
- `park_reason_codes`
- `cpt_tier`

Write behavior in scope building:
- `write_effective = 1` only if `write_enabled = 1` and `repricing_enabled = 1`
- `writer_mode = CODEX_H` only if `write_effective = 1`
- otherwise `writer_mode = READ_ONLY`

### How Parked SKUs Are Treated

Parked semantics in current code are stock-led.

Current parked behavior:
- no listing row or no live in-stock listing signal leads to parked treatment
- parked SKUs are marked with parked reason codes such as `PARK_OUT_OF_STOCK`
- parked SKUs become `repricing_enabled = 0`
- parked SKUs become `write_effective = 0`
- parked SKUs are excluded from active H pricing targets

Merchant sale status does not park a SKU by itself. Stock absence is the primary parked trigger in the current scope builder.

## Ceiling System

Primary ceiling logic lives in:
- `scripts/phase1/phase1_ceilings.py`

### Compliance Ceiling

Current compliance behavior:
- CPT does not clamp the compliance ceiling
- CPT is recorded as telemetry only
- if a compliance anchor exists, it becomes the compliance ceiling
- if no compliance anchor exists but a manual cap exists, manual cap becomes the fallback compliance ceiling
- otherwise compliance is unavailable

Current compliance reason-code behavior includes:
- `COMPLIANCE_CPT_TELEMETRY_ONLY`
- `COMPLIANCE_ANCHOR_FALLBACK`
- `COMPLIANCE_MANUAL_CAP_FALLBACK`
- `COMPLIANCE_UNAVAILABLE`

### Eligibility Ceiling

Current eligibility ladder in code is:
- FOEP
- MANUAL
- LAST_KNOWN_SAFE

Current code behavior:
- FOEP is used only if present, fresh enough, sane enough, and not error-flagged
- CPT is not used as the eligibility ceiling
- if CPT exists, code records `CPT_TELEMETRY_ONLY`
- if FOEP is unusable and manual cap exists, manual cap becomes the eligibility ceiling
- if manual cap is absent and last-known-safe exists, last-known-safe becomes the eligibility ceiling

### Suppression Ceiling

Current suppression-reactivation targeting order is:
- CPT
- COMPETITIVE_PRICE
- AVERAGE_SELLING_PRICE
- FOEP
- PROBE_BRACKET

If none of those are available:
- the system can infer an upper bound from the lowest competitor price when Buy Box is suppressed and no Buy Box offer is present
- otherwise the system can use a probe-ceiling candidate
- otherwise it can carry forward an existing temporary suppression ceiling if still active

### Final Ceiling Application

The current final-ceiling candidates are:
- compliance ceiling
- eligibility ceiling
- temporary suppression ceiling
- manual cap

The binding ceiling is the lowest valid candidate, with tie-breaking order favoring:
- `COMPLIANCE`
- `MANUAL_CAP`
- `SUPPRESSION_TEMP`
- `ELIGIBILITY`

Ceiling events are persisted in `sku_ceiling_events`.

## Phase Engine Behavior

Primary phase logic lives in:
- `scripts/phase1/phase1_phase_engine.py`

### Defined Phases

Current code defines phases:
- phase 0
- phase 1
- phase 2
- phase 3
- phase 4

### Persisted Phase State

Current phase persistence uses:
- `sku_phase_state`
- `sku_phase_transition_log`

Tracked fields include:
- current phase
- phase entered time
- strategy start date
- phase lock timing
- below-floor streak days
- recovery streak days

### Current Transition Rules

Current code includes these major transition controls:
- initial Phase 1 bootstrap behavior
- grace-period escalation block
- out-of-stock phase freeze
- below-floor fast-track to at least Phase 3
- time-based trigger escalation
- competitive-test lock to Phase 1
- limited inventory-pressure acceleration
- recovery downgrade after sustained recovery and minimum phase duration
- go-live reseed behavior using `H_STRATEGY_GO_LIVE_UTC`

### What Actually Changes By Phase

Current phase behavior profile changes:
- Phase 1
- minimum undercut bias of 0.05 GBP
- no explicit step-down cap
- soft-floor relaxation of 0.30
- Phase 2
- undercut bias 0.10 GBP
- max step down 0.20 GBP
- Phase 3
- undercut bias 0.15 GBP
- max step down 0.30 GBP
- can switch active floor to exit floor
- Phase 4
- undercut bias 0.20 GBP
- max step down 0.40 GBP
- can switch active floor to exit floor

Important runtime note:
- the live repricer is phase-aware
- but the runtime decision path still primarily flows through the probe engine and Phase 1 style pricing states, with phase behavior acting as an adjustment layer rather than a fully separate per-phase strategy engine

## Write Gate

Primary write-gate logic lives in:
- `scripts/phase1/phase1_write_gate.py`

### Write Eligibility

Current write-gate requirements are:
- `writer_mode` must be `CODEX_H`
- the SKU must not be excluded
- if phase live writes are enabled, phase engine must be enabled, phase behavior must be enabled, and the SKU must be in cohort
- if phase live writes are not enabled, `CODEX_H` alone can still allow write eligibility

Current allow reason:
- `PHASE_LIVE_WRITE_ALLOWED`

Current block reasons include:
- blocked writer mode
- excluded SKU
- required phase flags off
- SKU not in cohort

### Additional Writer Lock

`scripts/phase1/phase1_main_loop.py` applies an additional runtime writer lock:
- invalid writer modes are blocked
- any mode other than `CODEX_H` is blocked from live write

This means live write permission is not controlled by one signal only. The runtime requires both:
- a scope row that resolves to `CODEX_H`
- a successful live-write-gate result

### Config Authority

Current write-enable authority is:
- `config/h_sku_switches.csv`

Current legacy fallback is:
- `config/phase1_writer_modes.csv`

Actual code behavior in `phase1_sku_scope.py`:
- load `config/h_sku_switches.csv` first
- if it does not exist, or if it is legacy-shaped, fall back to `config/phase1_writer_modes.csv`

Current contract statement:
- `config/h_sku_switches.csv` is the true active authority for write enablement
- `config/phase1_writer_modes.csv` is legacy compatibility input only

## Suppression Handling

Suppression behavior is implemented across:
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_ceilings.py`
- `scripts/h/h_suppression_truth.py`

### Suppression Detection

Current suppression-active states include:
- `SUPPRESSED_ASIN`
- `DISQUALIFIED_SELF_PRICE`

### Suppression Memory

Current suppression memory persists:
- highest eligible price
- lowest ineligible price
- threshold estimate
- confidence
- last validated timestamp
- anchor floor
- temporary suppression ceiling
- last Buy Box state

Primary persistent table:
- `suppression_threshold_memory`

Operational mirror outputs:
- `out/h_suppression_cases.csv`
- `out/h_suppression_threshold_memory.csv`
- `out/h_suppression_reactivation_log.csv`

### Reactivation Behavior

Current suppression-reactivation behavior includes:
- direct target selection from the suppression target ladder
- threshold-estimate guided reactivation
- lowest-competitor upper-bound inference when Buy Box is suppressed and no Buy Box offer is present
- temporary suppression ceiling expiry handling
- dedicated suppression reactivation runtime state in the probe engine

### Existing Fallback Today

Current code does already contain real fallback behavior for suppressed cases.

What exists today:
- direct target ladder
- inferred upper bound from lowest competitor
- probe-bracket fallback
- carry-forward temporary ceiling behavior

What is still not fully settled at governance level:
- earlier plan wording around suppressed Buy Box fallback has not fully caught up with current code behavior

## Data Model

Primary persistence registry lives in:
- `scripts/phase1/phase1_storage.py`

### Persistent Runtime Tables

Current runtime tables in `data/` are:
- `offer_snapshot_facts.csv`
- `offer_variants.csv`
- `sku_daily_intel.csv`
- `sku_ceiling_events.csv`
- `variant_delta_memory.csv`
- `execution_log.csv`
- `decision_log.csv`
- `scenario_rollup.csv`
- `probe_windows.csv`
- `oas_log.csv`
- `daily_intel_refresh_attempts.csv`
- `sku_phase_state.csv`
- `suppression_threshold_memory.csv`
- `sku_phase_transition_log.csv`

### Runtime Output Files

Current repricer-related runtime outputs in `out/` include:
- `out/phase1_sku_scope.csv`
- `out/phase1_floor_table_latest.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/h_suppression_cases.csv`
- `out/h_suppression_threshold_memory.csv`
- `out/h_suppression_reactivation_log.csv`
- `out/analysis_reports/phase1_observation_combined_YYYY-MM-DD.csv`

## Dashboard And Observation Layer

Primary observation builder:
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`

### How The Observation View Is Built

The observation builder combines:
- canonical scope
- runtime floor snapshot
- floor table
- daily intel
- offer snapshot facts
- product database preview
- inventory data
- order master
- scan state
- execution log
- suppression truth

It builds combined observation outputs locally and can publish them to the configured Google Sheet view tab.

Default live view tab:
- `PRICING_DASHBOARD`

### Current Exported Truth Signals

Current observation output includes truth and status signals such as:
- write capability derived from `write_effective` and `writer_mode`
- automation and capability status columns
- scope and stock visibility
- suppression truth columns
- probe-state visibility
- floor and ROI context
- last scan timing

Current authoritative write-capable logic in the observation layer is:
- `write_effective == 1` or `writer_mode == CODEX_H`

## Document Versus Code Differences

These are the current known document-versus-code differences that matter for governance and drift detection.

### CPT Ladder Position

Older repricer plan wording says:
- FOEP -> CPT -> MANUAL -> LAST_KNOWN_SAFE

Current code says:
- FOEP -> MANUAL -> LAST_KNOWN_SAFE

Current CPT behavior:
- telemetry-only in compliance and eligibility ceiling resolution
- still used in suppression-reactivation targeting

### Stock-Source Order

Older repricer plan wording says:
- `inventory_summaries.csv` -> latest `inventory_snapshot_*.csv` -> `stock_snapshot_latest.csv`

Current H runtime code says:
- latest `inventory_snapshot_*.csv` first
- then `inventory_summaries.csv`
- then parking stock snapshot fallback

### Single-SKU Versus Multi-SKU

Older Phase 1 documents describe:
- a single-SKU live lab

Current live runtime uses:
- active-merchant target-universe mode
- canonical multi-SKU scope
- parked and stock filtering
- multiple write-capable SKUs

### Naming Differences

Older planning names include:
- `daily_intel.csv`
- `ceiling_events.csv`

Current runtime tables are:
- `sku_daily_intel.csv`
- `sku_ceiling_events.csv`

### Config Authority Confusion

Older planning and legacy config imply:
- `config/phase1_writer_modes.csv` controls writer mode

Current code actually uses:
- `config/h_sku_switches.csv` as the primary authority
- `config/phase1_writer_modes.csv` only as a fallback compatibility source

### Governance Split

Current project governance now separates:
- current live runtime contract
- target future architecture
- historical implementation references

This file is the operationally authoritative runtime contract for drift detection against current code.

## Contract Boundaries

This runtime contract does not define:
- target portfolio governor behavior
- notification-led repricer orchestration
- demand-learning architecture
- pressure-system architecture

Those belong to target-architecture planning, not to the live runtime contract.
