# Feeder v1 Normalization And Classification Guidebook

## Purpose
This guidebook defines the isolated Feeder v1 normalization and first-pass classification process.

The process converts intake-ready feeder rows into one canonical candidate structure, applies first-pass status routing, and keeps all not-ready rows explicit.

This process is local-first and does not run live scheduler ownership.

## Inputs and outputs
- Input contract file:
  - `out/systems/F/live/feeder_candidate_intake_live.csv`
- Output contract files:
  - `out/systems/F/live/feeder_candidate_normalized_live.csv`
  - `out/systems/F/live/feeder_candidate_first_pass_classification_live.csv`
  - `out/systems/F/live/feeder_candidate_first_pass_holds.csv`
  - `out/systems/F/live/feeder_classification_health.csv`

## Run command
```powershell
python scripts/flows/F/F020_build_feeder_candidate_classification.py
```

Optional deterministic timestamp:
```powershell
python scripts/flows/F/F020_build_feeder_candidate_classification.py --classification-utc 2026-04-07T12:10:00Z
```

Optional alternate input path:
```powershell
python scripts/flows/F/F020_build_feeder_candidate_classification.py --input-rel-path tests/fixtures/f_phase1/feeder_candidate_intake_fixture.csv
```

## First-pass routing model
- `ready_for_viability`:
  - candidate is structurally ready for F1C viability and demand checks
- `manual_review`:
  - candidate is not ready for automatic progression and needs review
- `hold`:
  - candidate has hard structural defects and is blocked

Rows not in `ready_for_viability` are written to `feeder_candidate_first_pass_holds.csv` with explicit reason codes.

## Validation and classification rules
Hard hold reasons include:
- missing `candidate_id`
- duplicate `candidate_id`
- missing identity key (no valid ASIN or barcode)
- invalid ASIN format
- invalid barcode format
- missing `brand`
- missing supplier reference (`supplier_id` and `supplier_name` both blank)
- `price_list_status` not `acquired`
- `handoff_ready_flag` not true
- `intake_status` not `intake_ready`

Manual review reasons include:
- both valid ASIN and valid barcode present (`identity_dual_key_review`)
- supplier id present but supplier name missing (`supplier_name_missing`)

## Health checks and alert conditions
The process writes `feeder_classification_health.csv` with:
- `feeder_classification_source_contract`
  - `warn` when intake source file is missing
  - `fail` when required intake columns are missing
- `feeder_classification_quality`
  - `warn` when no rows are processed
  - `warn` when manual-review or hold rows exist
  - `fail` when no rows are classified
  - `fail` when zero rows are ready for viability

## Recovery playbook
If source is missing:
1. Run F010 to regenerate `feeder_candidate_intake_live.csv`.
2. Confirm file path and contract columns.
3. Rerun F020.

If schema fails:
1. Compare source headers to `scripts/flows/F/_schemas.py` for `feeder_candidate_intake_live`.
2. Fix intake writer mapping in F010 boundary.
3. Rerun F020 and confirm source-contract check is `ok`.

If manual-review or hold rows accumulate:
1. Inspect `feeder_candidate_first_pass_holds.csv`.
2. Fix root data defects at intake/supplier boundary.
3. Rerun F010 then rerun F020.
4. Verify rows move to `ready_for_viability` in classification output.
