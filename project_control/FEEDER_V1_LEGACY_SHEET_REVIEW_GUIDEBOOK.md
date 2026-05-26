# Feeder v1 Legacy Sheet Review Guidebook

## Purpose
Recreate local review views that mirror the old Google Sheet workflow tabs:
- First Checks
- Second Checks
- Bot Status

This stage is supplier-scoped and should run one supplier at a time.

## Inputs
- `out/systems/F/live/feeder_candidate_recommendations_live.csv`
- `out/systems/F/history/feeder_approval_decisions_log.csv`

## Outputs
- `out/systems/F/live/feeder_legacy_first_checks_live.csv`
- `out/systems/F/live/feeder_legacy_second_checks_live.csv`
- `out/systems/F/live/feeder_legacy_bot_status_live.csv`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`

## Run Command (Shure only)
```bash
python -m scripts.flows.F.F060_build_legacy_sheet_review_pack --supplier-id shure_cosmetics
```

## Operating Rule
- Do not mix suppliers in review runs.
- Complete user review for current supplier before moving to next supplier.

## Health Checks
- `feeder_legacy_sheet_source_contract`
- `feeder_legacy_sheet_quality`
- `feeder_legacy_sheet_send_ready`
