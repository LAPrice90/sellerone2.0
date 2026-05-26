# Feeder v1 Supplier Converter Guidebook

## Purpose
This guidebook defines the supplier conversion layer that turns raw supplier price lists into a single universal format for feeder.

Key goals:
- keep supplier specific parsing out of the shared manager
- produce a universal layout every supplier must follow
- keep queue state so the scanner resumes where it left off
- avoid data buildup by keeping only current and previous copies

## Core Files
- Configs: `config/feeder/suppliers/*.json`
- Raw supplier snapshots: `out/systems/F/inbox/suppliers/<supplier_id>/raw_current.csv`
- Canonical snapshots: `out/systems/F/inbox/suppliers/<supplier_id>/canonical_current.csv`
- Active run queue: `out/systems/F/inbox/suppliers/<supplier_id>/active_run.csv`
- Per supplier run state: `out/systems/F/inbox/suppliers/<supplier_id>/run_state.csv`
- Aggregated universal output: `out/systems/F/inbox/supplier_price_list_universal_live.csv`
- Aggregated holds: `out/systems/F/inbox/supplier_price_list_universal_holds.csv`
- Aggregated active run: `out/systems/F/inbox/supplier_price_list_active_run.csv`
- Aggregated run state: `out/systems/F/inbox/supplier_price_list_run_state.csv`
- Queue state: `out/systems/F/inbox/supplier_price_list_queue_state.csv`
- Health checks: `out/systems/F/live/supplier_price_list_health.csv`

## Universal Supplier Layout
Required columns in `supplier_price_list_universal_live.csv`:
- `supplier_id`
- `supplier_name`
- `supplier_sku`
- `supplier_title`
- `barcode`
- `unit_cost`
- `currency`
- `vat_rate`
- `source_url`
- `source_file_path`
- `source_seen_at_utc`
- `row_hash`
- `is_valid_source_row`
- `normalized_utc`

Optional columns:
- `brand`
- `pack_size`
- `moq`
- `stock_available`
- `category`
- `notes`

Holds file `supplier_price_list_universal_holds.csv` keeps non usable rows and must include:
- `hold_reason_codes`

## Queue Rules
The scanner must resume where it left off:
- if a supplier run is active and has pending rows, resume that supplier
- if no active run exists, select the next supplier in queue order
- never restart at the first supplier on every boot

Queue state file:
- `out/systems/F/inbox/supplier_price_list_queue_state.csv`

## Cleanup Rules
Keep only what is needed:
- raw_current and raw_previous only
- canonical_current and canonical_previous only
- active_run and run_state only for the current run
- no growing temp or debug dumps unless explicitly enabled

## Run Command
Manual run for one supplier:
```
python -m scripts.flows.F.F005_build_supplier_price_list_universal --supplier shure_cosmetics --refresh
```

Second supplier proof run:
```
python -m scripts.flows.F.F005_build_supplier_price_list_universal --supplier td_synnex --refresh
```

Queue mode (default):
```
python -m scripts.flows.F.F005_build_supplier_price_list_universal
```

## Recovery
If a run is interrupted:
- do not delete `active_run.csv` or `run_state.csv`
- rerun the command and the queue should resume from `next_row_index`

## Current Supplier Adapters
- `shure_cosmetics` -> `scripts/flows/F/suppliers/shure_cosmetics.py`
- `td_synnex` -> `scripts/flows/F/suppliers/td_synnex.py`
