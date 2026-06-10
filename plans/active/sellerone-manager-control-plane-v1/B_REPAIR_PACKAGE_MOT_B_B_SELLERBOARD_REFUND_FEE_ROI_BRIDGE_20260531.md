# B Repair Package - Refund Fee Shipping ROI Proof - 2026-05-31

## Root Cause Summary
- The current B warning is `b_sellerboard_refund_fee_roi_bridge`.
- B order collection is fresh and Sellerboard shipped-order comparison is no longer an active order-recovery failure.
- The remaining B truth gap is money proof: refunds, fees, shipping, and ROI are not fully API-backed or clearly labelled everywhere the manager needs them.
- Sellerboard can be used as outside comparison evidence only. It must not become final ROI or restocking truth.

## Current Evidence
- B MOT status: warning-level, not failed.
- Current bridge warning values include:
  - Sellerboard return orders missing local refund proof: 3
  - local refund orders missing Sellerboard return proof: 1
  - direct fee detail API evidence rows: 0
  - current ROI expected refund non-zero rows: 0
- Fee totals exist in the bridge, but they are labelled as Sellerboard bridge estimates rather than final API truth.

## Allowed Files For A Future Repair Batch
- `sellerone_manager/sellerboard_bridge.py`
- `sellerone_manager/hourly_mot.py`
- `sellerone_manager/multi_flow.py`
- focused B manager tests under `tests/manager/`
- B proof documentation under `plans/active/sellerone-manager-control-plane-v1/`

## Forbidden Files And Actions
- Do not run or restart B.
- Do not edit B locks or maintenance markers.
- Do not write Google Sheets.
- Do not correct token, order, refund, fee, shipping, stock, or ROI data.
- Do not align local DB facts.
- Do not delete outputs.
- Do not merge recovered orders into live data.
- Do not feed Sellerboard bridge values into live ROI or restocking as final truth.
- Do not change prices or queues.
- Do not widen into A, E, H, F, or O.

## Proof Path For A Future Repair
- Add or confirm explicit proof labels for refund evidence:
  - `API proved`
  - `Sellerboard bridge estimate`
  - `not yet proven`
- Add or confirm explicit proof labels for fee and shipping evidence:
  - commission
  - FBA fee
  - shipping income or shipping fee where relevant
- Add or confirm ROI confidence labels so downstream E/O logic can tell the difference between clean API-backed ROI and bridge-only estimates.
- Keep Sellerboard values as outside comparison or bridge evidence only.
- Retest through B independent MOT, not by editing final reports.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow B

## Acceptance Checks
- `b_sellerboard_refund_fee_roi_bridge` is either `ok` because API-backed proof exists, or remains warning-level with exact labelled reasons.
- B management still shows 0 active FAIL rows.
- Sellerboard bridge values are not used as final ROI/restocking truth.
- No B worker run, restart, data correction, Sheet write, DB alignment, output deletion, price change, or queue edit happens during this proof batch.

## Rollback Path
- Use git diff for code rollback.
- Do not rewrite business output files to make the warning disappear.
- If proof labels are wrong, revert the manager proof-label code and rerun the read-only B MOT.

## Stop Condition
- Stop when the manager can clearly say which refund, fee, shipping, and ROI values are API-proved, bridge-only, or not yet proven.
- Stop immediately if the repair would require a protected action: B run, B restart, data correction, local DB alignment, Sheets, output deletion, ROI substitution, prices, queues, or scope widening.
