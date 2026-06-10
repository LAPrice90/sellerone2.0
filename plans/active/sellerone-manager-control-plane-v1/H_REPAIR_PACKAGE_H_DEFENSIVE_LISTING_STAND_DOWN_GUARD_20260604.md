# H Repair Package - Defensive Listing Stand-Down Guard - 2026-06-04

## Task ID
`h_defensive_listing_stand_down_guard`

## Manager Task
- Source proof: B06 defensive listing proof row showed a live write from 6.98 to 6.97 while the recorded current price and lowest rival price were both 6.98.
- This package belongs to H, not F.
- The goal is to enforce the intended defensive strategy: only undercut when a rival is strictly below us before the undercut is calculated.

## Current Evidence
- SKU `6V-EEC1-2S9Z` / ASIN `B06WW79DX5` has live defensive listing enabled.
- The live proof row showed `current_price_gbp=6.98`, `lowest_rival_price_gbp=6.98`, `target_price_gbp=6.97`, and `write_status=APPLIED`.
- The intended rule says equal, above, or gone must stand down and leave normal H repricing in control.
- The current code checks whether the target is below current after subtracting the 1p undercut, so equal rival price can still trigger a write.

Plain English:
- The guard was meant to frustrate a rival only when they are actually under us.
- It instead undercut when the rival was level with us.
- That is an H repricing-rule problem and must be repaired inside H ownership.

## Allowed Files For A Future Repair Batch
Future work may inspect and edit only the defensive-listing guard and manager proof:
- `config/h_defensive_listing_protection.csv`, only for the B06 defensive-listing toggle fields approved in this package
- `scripts/phase1/phase1_defensive_listing.py`
- `scripts/phase1/phase1_main_loop.py`, only if the caller passes the wrong rival/current proof into the guard
- `tests/test_phase1_defensive_listing.py`
- `tests/test_phase1_main_loop.py`
- `sellerone_manager/hourly_mot.py`, only if MOT proof visibility needs updating for this guard
- focused H manager tests under `tests/manager/`

## Forbidden Files And Actions
- Do not run H manually.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align or edit local DB data.
- Do not delete outputs.
- Do not restart workers.
- Do not widen into F, A, B, E, O, Product DB, scanner, supplier, or finance logic.

## Proof Path For A Future Repair
- Add a test proving equal rival price returns normal H control with no write.
- Add a test proving rival above us returns normal H control with no write.
- Keep the existing test proving a rival strictly below us can undercut by 1p inside floor and ceiling.
- Run focused defensive-listing tests.
- Run focused H manager tests if MOT proof visibility changes.
- Retest with the read-only H MOT.
- Success means B06 defensive mode only writes when the rival is strictly below us, and equal/above/gone states produce normal H control proof.

## Retest Command
```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

## Rollback Path
- Use git diff to revert only the defensive-listing guard and focused tests touched by this repair.
- Do not edit H outputs, action logs, daily proof, or live price data as rollback.

## Stop Condition
Stop immediately if the repair would require a live H run, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, worker restart, or scope widening.
