# Feeder v1 Intake Guidebook

## Purpose
This guidebook defines the isolated Feeder v1 intake process for converting Supplier Discovery handoff rows into a feeder-ready intake set with explicit holds and health checks.

This process is local-first and does not run live scheduler ownership.

## Inputs and outputs
- Input contract file:
  - `out/systems/F/inbox/supplier_discovery_handoff.csv`
- Output contract files:
  - `out/systems/F/live/feeder_candidate_intake_live.csv`
  - `out/systems/F/live/feeder_candidate_intake_holds.csv`
  - `out/systems/F/live/feeder_intake_health.csv`

## Run command
```powershell
python scripts/flows/F/F010_build_feeder_candidate_intake.py
```

Optional deterministic timestamp:
```powershell
python scripts/flows/F/F010_build_feeder_candidate_intake.py --intake-utc 2026-04-07T12:00:00Z
```

Optional alternate input path:
```powershell
python scripts/flows/F/F010_build_feeder_candidate_intake.py --input-rel-path tests/fixtures/f_phase1/supplier_discovery_handoff_fixture.csv
```

## Validation rules
Rows are held when any of these fail:
- missing `discovery_candidate_id`
- duplicate `discovery_candidate_id` in same run
- `handoff_ready_flag` is not true
- `price_list_status` is not `acquired`
- missing `price_list_artifact_path`
- both `asin` and `barcode` missing
- missing `brand`
- missing supplier reference (`chosen_supplier_id` and `chosen_supplier_name` both blank)

## Health checks and alert conditions
The process writes `feeder_intake_health.csv` with:
- `feeder_intake_source_contract`
  - `warn` when source file is missing
  - `fail` when required source columns are missing
- `feeder_intake_quality`
  - `warn` when no rows are processed
  - `warn` when some rows are held
  - `fail` when all rows are held after processing

## Recovery playbook
If source is missing:
1. Confirm Supplier Discovery handoff export path and filename.
2. Restore the latest valid handoff artifact into `out/systems/F/inbox/`.
3. Rerun F010.

If schema fails:
1. Compare source headers to `scripts/flows/F/_source_contracts.py`.
2. Correct source export mapping at Supplier Discovery boundary.
3. Rerun F010 and confirm source-contract check is `ok`.

If all rows are held:
1. Inspect `feeder_candidate_intake_holds.csv`.
2. Fix root data defects in handoff artifact.
3. Rerun F010 and verify accepted rows appear in `feeder_candidate_intake_live.csv`.
