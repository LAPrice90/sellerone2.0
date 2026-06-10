# B Repair Package - API Refund Fee Shipping ROI Proof - 2026-05-31

## Approved Check
- `b_refund_fee_shipping_roi_api_proof`

## Root Cause Summary
- The current B bridge warning is still active.
- The previous B package proved that the manager can label the gap honestly.
- The next gap is stronger: the manager needs direct API-backed proof for refund, fee, shipping, and ROI ingredients, or clear `not yet proven` labels where API proof is missing.
- Sellerboard is only outside comparison evidence. It must not become live ROI or restocking truth.

## Current Evidence
- B MOT is warning-level, not failed.
- B management is safe to maintain, but B order truth is not financially complete.
- Active B warning values currently include:
  - Sellerboard/local refund mismatch evidence.
  - direct fee detail API evidence rows not yet proven in the manager bridge.
  - ROI refund proof not yet safe for live downstream use.
- This packet is for the next safe proof-building step, not for correcting money data.

## Allowed Files For A Future Repair Batch
- `sellerone_manager/sellerboard_bridge.py`
- `sellerone_manager/hourly_mot.py`
- `sellerone_manager/multi_flow.py`
- `sellerone_manager/b_marketplace_coverage.py`
- focused B manager tests under `tests/manager/`
- B manager proof documentation under `plans/active/sellerone-manager-control-plane-v1/`

## Read-Only Evidence The Worker May Inspect
- `out/financial_events_refunds_official.csv`
- `out/financial_events_refunds.csv`
- `out/fee_detail_ledger_api.csv`
- `out/financial_events_shipments.csv`
- `out/financial_events_level3_official.csv`
- `out/financial_transactions_v2024_raw.csv`
- `out/order_master.csv`
- `out/pnl_daily.csv`
- `out/sku_roi_snapshot.csv`
- `out/systems/M/sellerboard_bridge/b_sellerboard_bridge_summary.csv`
- `out/systems/M/sellerboard_bridge/b_sellerboard_bridge_order_reconciliation.csv`

## Forbidden Files And Actions
- Do not run or restart B.
- Do not edit B locks or maintenance markers.
- Do not write Google Sheets.
- Do not correct order, token, refund, fee, shipping, stock, or ROI data.
- Do not align local DB facts.
- Do not delete outputs.
- Do not merge recovered orders into live data.
- Do not use Sellerboard bridge values as final ROI or restocking truth.
- Do not change prices or queues.
- Do not widen into A, E, H, F, or O.

## Proof Path For A Future Repair
- Read current API-backed proof files from outside the B loop.
- Add or confirm explicit manager/MOT proof labels for refunds:
  - `api_proved`
  - `sellerboard_bridge_only`
  - `not_yet_proven`
- Add or confirm explicit manager/MOT proof labels for fees:
  - commission API proof
  - FBA fee API proof
  - other fee API proof where available
  - `not_yet_proven` where unavailable
- Add or confirm explicit manager/MOT proof labels for shipping:
  - shipping income API proof
  - shipping fee API proof
  - `not_yet_proven` where unavailable
- Add or confirm ROI confidence output so E/O can tell whether ROI is:
  - API-backed and safe
  - bridge-labelled only
  - not yet proven
- Retest through B independent MOT.
- Keep the B warning if API proof is still incomplete. Do not hide it downstream.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow B

## Acceptance Checks
- B MOT still has 0 active FAIL rows.
- The manager can say, in machine-readable output, which refund, fee, shipping, and ROI ingredients are API-proved.
- Any missing API proof remains visible as `not_yet_proven` or warning-level evidence.
- Sellerboard bridge values remain labelled as bridge evidence only.
- No B worker run, B restart, Sheet write, data correction, local DB alignment, output deletion, price change, queue edit, or live ROI substitution happens during this packet.

## Rollback Path
- Use git diff for code rollback.
- Revert only touched manager/MOT proof code or test files if the labels are wrong.
- Do not edit business output files to make the warning disappear.
- Rerun the read-only B MOT after rollback.

## Stop Condition
- Stop when the manager has a clear API-proof map for refund, fee, shipping, and ROI ingredients, or when the missing API proof is explicitly labelled as not proven.
- Stop immediately if the repair would require B live execution, B restart, data correction, local DB alignment, Sheets, output deletion, ROI substitution, prices, queues, or scope widening.
