Task 1 - Storage adapter - DONE (2026-02-13 11:25 UTC)

Implement:

CSV storage with atomic writes

Append-only tables

Upserts for memory/dimensions

Read helpers

Deliverable:

A module with unit tests

No pricing logic yet

Task 2 - Market snapshot processor - DONE (2026-02-13 11:35 UTC)

Implement:

Adapter for getCompetitiveSummary

Normalised offer rows

Variant mapping

Deliverable:

Function that returns clean snapshot rows

All IDs consistent

Completion proof:

- Implemented: scripts/phase1_market_snapshot_processor.py
- Tests added: tests/test_phase1_market_snapshot_processor.py
- Validation run: python -m unittest tests.test_phase1_market_snapshot_processor -v
- Result: Ran 3 tests ... OK
- Consistency proof: deterministic offer_variant_id mapping for same structural key, unique offer_snapshot_id per row

Task 3 - DVE layer - DONE (2026-02-13 12:26 UTC)

Implement:

Effective price calc

Delivery penalty

Penalty curve v0

Deliverable:

Verified output compared to expected values

Completion proof:

- Implemented: scripts/phase1_dve.py
- Tests added: tests/test_phase1_dve.py
- Validation run: python -m unittest tests.test_phase1_dve -v
- Result: Ran 3 tests ... OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve -v
- Result: Ran 12 tests ... OK
- Expected-value proof:
- gap 0 -> penalty 0.00
- gap 1 -> penalty 0.15
- gap 2 -> penalty 0.30
- gap 3 -> penalty 0.45
- gap 4+ -> penalty 0.60 (cap)

Task 4 - Ceilings - DONE (2026-02-13 12:50 UTC)

Implement:

Compliance & fallback

Eligibility ladder

Manual cap

Deliverable:

Verified ceiling outputs

Completion proof:

- Implemented: scripts/phase1_ceilings.py
- Tests added: tests/test_phase1_ceilings.py
- Validation run: python -m unittest tests.test_phase1_ceilings -v
- Result: Ran 7 tests ... OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings -v
- Result: Ran 19 tests ... OK
- Expected-value proof:
- compliance anchor 20.00 with 3% buffer -> 19.40
- FOEP missing + CPT 11.89 -> eligibility_source CPT, eligibility_ceiling 11.89
- FOEP ASIN_NOT_ELIGIBLE + no CPT + manual 12.10 -> eligibility_source MANUAL, eligibility_ceiling 12.10
- final ceiling min(19.40, 18.90, 18.50) -> 18.50 with binding_ceiling_type MANUAL_CAP

Task 5 - Probe engine - DONE (2026-02-13 13:00 UTC)

Implement:

State machine transitions

Best rival definition

Bracket logic

Delta memory

Deliverable:

Functions that choose next price

Completion proof:

- Implemented: scripts/phase1_probe_engine.py
- Tests added: tests/test_phase1_probe_engine.py
- Validation run: python -m unittest tests.test_phase1_probe_engine -v
- Result: Ran 4 tests ... OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine -v
- Result: Ran 23 tests ... OK
- Expected-value proof:
- best rival selection ignores our offer and returns minimum rival effective price
- transition routing verified for REGAIN, RAISE_FIND_LOSS, BRACKET_NARROW, STABLE_WIN, HOLD_OBSERVE
- bracket midpoint example: best_rival=10.10 with bounds [-0.04,0.10] -> target 10.13
- delta memory example: WIN -0.05 then LOSS 0.08 -> learned_delta 0.02, valid_test_count 2

Task 6 - Write + Verify - DONE (2026-02-13 13:04 UTC)

Implement:

patchListingsItem write

verification logic

probe window initiation

Deliverable:

Confirmed writes

Completion proof:

- Implemented: scripts/phase1_write_verify.py
- Tests added: tests/test_phase1_write_verify.py
- Validation run: python -m unittest tests.test_phase1_write_verify -v
- Result: Ran 5 tests ... OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine tests.test_phase1_write_verify -v
- Result: Ran 28 tests ... OK
- Write + verify proof:
- accepted write + Listings read match -> APPLIED and probe window started
- accepted write + snapshot fallback match -> APPLIED and probe window started
- accepted write + mismatch -> WRITE_NOT_APPLIED and probe window not started
- rejected write -> WRITE_REJECTED and probe window not started
- proposed below floor -> GUARDRAIL_HARD_FLOOR_CLAMP applied before submit

Task 7 - OAS - DONE (2026-02-13 13:08 UTC)

Implement:

Hard-fail checks

Deliverable:

Verified quality filtering

Completion proof:

- Implemented: scripts/phase1_oas.py
- Tests added: tests/test_phase1_oas.py
- Validation run: python -m unittest tests.test_phase1_oas -v
- Result: Ran 6 tests ... OK
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine tests.test_phase1_write_verify tests.test_phase1_oas -v
- Result: Ran 34 tests ... OK
- Quality filtering proof:
- market_structure_hash excludes price and featured winner identity (stable hash when only those change)
- market structure change, unknown featured outcome, writer conflict, suppression, and reliable non-purchasable each trigger OAS hard-fail
- allowlisted manual override price change does not trigger writer conflict fail

Task 8 - Main loop wiring - DONE (2026-02-13 13:19 UTC)

Tie A-cycle + H-cycle + logging.

Deliverable:

Running script

Each of these has a clear input/output contract so you can test it.

Completion proof:

- Implemented: scripts/phase1_main_loop.py
- Tests added: tests/test_phase1_main_loop.py
- Validation run: python -m unittest tests.test_phase1_main_loop -v
- Result: Ran 4 tests ... OK
- Runnable proof: python scripts/phase1_main_loop.py --demo
- Result: A-cycle + H-cycle JSON output returned with state, write_status, ceiling, and reason_codes
- Regression run: python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine tests.test_phase1_write_verify tests.test_phase1_oas tests.test_phase1_main_loop -v
- Result: Ran 38 tests ... OK
- Contract proof:
- A-cycle persists sku_daily_intel with non-empty eligibility_source
- H-cycle enforces writer lock (WRITER_LOCK_BLOCK path)
- H-cycle writes snapshot, variant dimensions, ceiling events, execution log
- Probe close path writes oas_log and updates variant_delta_memory

Plan update - CPT handling (pin + observe, not a ceiling yet) - 2026-02-14

What we learned:
- CPT is not a usable max-price ceiling for profit optimization.
- CPT is an external-competition anchor and can be below the live Buy Box.
- Being above CPT can increase Featured/Buy Box ineligibility risk, but there is no deterministic published "CPT + X" safe buffer.

Immediate Phase 1 change:
- Stop using CPT to clamp max price (except as a policy-risk indicator).
- Keep daily CPT logging per SKU and compare against:
- current Buy Box and average sold price
- whether Featured is present/suppressed
- volatility and downward drift
- Treat CPT as a classifier: higher risk when CPT is far below clearing price.

Future only if data supports:
- Define learned tolerance by parameter:
- `cpt_tolerance_gbp` (example +0.30)
- or `cpt_multiplier` (example x1.08)
- Optional CPT-derived risk ceiling (disabled by default):
- `cpt_risk_ceiling = CPT + tolerance` or `CPT * multiplier`
- This is empirical and must be learned, not assumed.

Operational guidance:
- Three-ceiling system remains:
- Eligibility ceiling = market-based (best rival effective + learned delta)
- Demand ceiling = conversion realism / manual cap proxy for now
- Compliance/CPT = risk signal only until proven useful
- If `hard_floor > CPT`, classify SKU as CPT-incompatible and expect possible eligibility/suppression risk.
- Do not force repricing to CPT; log and classify.

Plan update - A-cycle consolidation and parked rollout - 2026-02-17

Implemented:
- New shared scope builder: `scripts/phase1_sku_scope.py`.
- New artifact: `out/phase1_sku_scope.csv` with strict parked rule and CPT tier.
- New writer mode config: `config/phase1_writer_modes.csv`.
- A016 moved to full DB default with:
- `--scope full_db|single_sku`
- `--sku`
- `--max-skus`
- `--dry-run`
- Compliance ceiling now ignores CPT in `scripts/phase1_ceilings.py` (CPT telemetry only).
- H-cycle now enforces:
- parked -> `DEFENSIVE_HOLD` / `PARKED_NO_ACTION`
- CPT risk `HIGH` -> block upward actions
- CPT risk `UNKNOWN` -> conservative non-raise
- H pilot now reads scope and excludes parked SKUs.
- Legacy H path removed CPT fetch and `cpt_x_1.2` clamp candidate.
- A015 now includes rollout checks:
- `a_daily_intel_coverage_non_parked`
- `a_daily_intel_compliance_nonempty_non_parked`
- `h_no_cpt_calls_in_h_cycle`
- `h_parked_sku_write_attempts`
- `h_scope_non_parked_matches_targets`

Validation proof:
- `python -m unittest tests.test_phase1_sku_scope tests.test_a016_daily_intel_scheduler tests.test_phase1_ceilings tests.test_phase1_main_loop tests.test_phase1_storage -v`
- `python -m unittest tests.test_phase1_storage tests.test_phase1_market_snapshot_processor tests.test_phase1_dve tests.test_phase1_ceilings tests.test_phase1_probe_engine tests.test_phase1_write_verify tests.test_phase1_oas tests.test_phase1_main_loop -v`
- `python scripts/phase1_sku_scope.py`
- `python scripts/A016_refresh_phase1_daily_intel.py --dry-run --scope full_db --max-skus 200`

Plan update - Phase 1 recovery: active-merchant scan with single-writer gate - 2026-02-17

Implemented:
- New shared target resolver: `scripts/phase1_target_universe.py`.
- Explicit target mode in config:
- `target_universe_mode: active_merchant|scope_non_parked|lab_cohort|single_sku`
- `config/pilot_sku.yaml` default set to `active_merchant`.
- H pilot (`scripts/H110_run_phase1_h_pilot.py`) now uses shared resolver and records target-universe diagnostics in state output.
- A016 (`scripts/A016_refresh_phase1_daily_intel.py`) now uses the same shared resolver as H so intel and execution use one SKU universe.
- H orchestrator (`scripts/run_H_pricing_cycle.py`) now runs once-daily pre-H intel alignment for the configured universe and records alignment status in `out/h_pricing_cycle_state.json`.
- Live writer gate remains strict allowlist:
- `enabled_live_writes: true` with `live_sku_allowlist` controlling which SKUs can submit live writes.
- Non-allowlisted SKUs run read-only H logic.
- Per-SKU cadence set via config:
- `scan_cooldown_minutes: 15`
- `max_skus_per_run: 0` means process all due SKUs.
- New runtime floor truth artifact:
- `out/phase1_runtime_floor_snapshot_latest.csv`
- built from live `data/execution_log.csv` plus `out/h_floor_truth_trace.csv`.

Operational truth vs historical diagnostics:
- Runtime truth for current floor and ceiling behavior:
- `data/execution_log.csv`
- `out/h_floor_truth_trace.csv`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- Historical analysis only (not authoritative for live decisions):
- `out/phase1_temp_floor_ceiling_breakdown_active10.csv`
- `out/cpt_vs_our_live_price_active10.csv`

Operating note:
- If `daily_intel missing for today` appears in `out/H_cycle.log`, treat as active alert and fix A016 alignment timing/universe first.
- Do not patch downstream H outputs to hide missing-intel causes.
