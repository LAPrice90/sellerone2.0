# Feeder v1 Shared Pass Logic Guidebook

## Purpose
Run shared pass/fail logic against universal supplier rows and keep non-ready rows explicit.

## Inputs
- `out/systems/F/inbox/supplier_price_list_universal_live.csv`

## Outputs
- `out/systems/F/live/feeder_shared_pass_logic_live.csv`
- `out/systems/F/live/feeder_shared_pass_logic_holds.csv`
- `out/systems/F/live/feeder_shared_pass_logic_health.csv`

## Run Command
```
python -m scripts.flows.F.F030_build_shared_feeder_pass_logic
```

## Current Decision Rules
- `NOCOST` -> `hold` (`FAIL`)
- `NOIDENTITY` (no barcode and no title) -> `hold` (`FAIL`)
- legacy precheck identity mode:
  - `barcode` + `BARCODE_PRESENT` -> precheck `pass`
  - `title_only` + strong title and SKU -> `TITLE_ONLY_PRECHECK_PASS` -> precheck `pass`
  - `title_only` + weak title or missing SKU -> precheck `review`
  - `none` (no barcode and no title) -> precheck `fail`
- `MISSING_BARCODE_TITLE_ONLY` -> `manual_review` (`REVIEW`) only when title-only precheck is not pass
- `WEAK_TITLE` -> `manual_review` (`REVIEW`)
- `COST_OUTLIER` -> `manual_review` (`REVIEW`)
- no reasons -> `ready_for_amazon_checks` (`PASS`)

## Notes
- Holds and manual-review rows are always written explicitly.
- Legacy precheck fields now publish in live and holds output:
  - `legacy_precheck_identity_mode`
  - `legacy_precheck_result`
  - `legacy_precheck_reason_codes`
- This stage is isolated proof only. It does not claim live-loop completion.
