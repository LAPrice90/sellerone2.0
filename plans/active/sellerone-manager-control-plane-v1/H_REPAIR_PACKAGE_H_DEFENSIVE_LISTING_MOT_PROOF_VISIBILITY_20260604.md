# H Repair Package - Defensive Listing MOT Proof Visibility - 2026-06-04

## Task ID
`h_defensive_listing_mot_proof_visibility`

## Manager Task
- Source proof: B06 defensive action and daily proof files exist, but the H MOT still reports `live_enabled_waiting_proof`.
- This package belongs to H, not F.
- The goal is to make the manager inspector read the actual B06 defensive proof row correctly without running H.

## Current Evidence
- `h_defensive_listing_action_log.csv` has a B06 proof row for run `20260604T104846Z`.
- `h_defensive_listing_daily.csv` has a B06 daily proof row for 2026-06-04.
- The read-only H MOT still says the defensive listing live mode is waiting for proof.

Plain English:
- The proof exists, but the manager check is not recognizing it.
- That makes the board look behind the real H evidence.

## Allowed Files For A Future Repair Batch
Future work may inspect and edit only manager proof recognition:
- `sellerone_manager/hourly_mot.py`
- `tests/manager/test_h_hourly_mot.py`
- read-only proof files under `out/h_defensive_listing_action_log.csv` and `out/h_defensive_listing_daily.csv`
- the H expectation file only if wording needs to reflect the proven proof surface

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
- Do not change defensive listing strategy logic in this proof-visibility package.
- Do not widen into F, A, B, E, O, Product DB, scanner, supplier, or finance logic.

## Proof Path For A Future Repair
- Add or update H MOT tests so existing action/daily proof rows clear `live_enabled_waiting_proof`.
- Confirm MOT reports B06 proof rows and live mode visibility accurately.
- Retest with the read-only H MOT.
- Success means the manager can see B06 defensive proof without relying on chat or raw file inspection.

## Retest Command
```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

## Rollback Path
- Use git diff to revert only manager proof recognition and focused tests touched by this repair.
- Do not edit H outputs, action logs, daily proof, or live price data as rollback.

## Stop Condition
Stop immediately if the repair would require a live H run, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, worker restart, defensive strategy change, or scope widening.
